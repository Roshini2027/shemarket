from flask import Blueprint, render_template, request, abort, jsonify
from flask_login import current_user
from sqlalchemy import func
from app import db
from app.models.product import Product, ProductStatus, PRODUCT_CATEGORIES
from app.models.business import Business, BusinessStatus
from app.models.review import Review
from app.services.recommendation_service import get_recommendations

main_bp = Blueprint("main", __name__)

PER_PAGE = 12


# ── Avg-rating subquery (reusable) ────────────────────────────────────────────
def _avg_rating_subq():
    return (
        db.session.query(
            Review.product_id,
            func.avg(Review.rating).label("avg_rating"),
            func.count(Review.id).label("review_count"),
        )
        .group_by(Review.product_id)
        .subquery()
    )


# ── Homepage ──────────────────────────────────────────────────────────────────
@main_bp.route("/")
def index():
    featured = (
        Product.query
        .join(Product.business)
        .filter(Product.status == ProductStatus.active, Product.stock_qty > 0)
        .order_by(Product.created_at.desc())
        .limit(8).all()
    )
    uid = current_user.id if current_user.is_authenticated else None
    recs = get_recommendations(uid)
    return render_template("main/index.html", featured=featured, recs=recs)


# ── Catalog ───────────────────────────────────────────────────────────────────
@main_bp.route("/catalog")
def catalog():
    q          = request.args.get("q", "").strip()
    seller_q   = request.args.get("seller", "").strip()
    category   = request.args.get("category", "")
    verified   = request.args.get("verified", "")
    sort       = request.args.get("sort", "newest")
    page       = request.args.get("page", 1, type=int)
    price_min  = request.args.get("price_min", "", type=str).strip()
    price_max  = request.args.get("price_max", "", type=str).strip()
    rating_min = request.args.get("rating", "", type=str).strip()

    avg_subq = _avg_rating_subq()

    query = (
        Product.query
        .join(Product.business)
        .outerjoin(avg_subq, avg_subq.c.product_id == Product.id)
        .filter(Product.status == ProductStatus.active, Product.stock_qty > 0)
        .add_columns(
            func.coalesce(avg_subq.c.avg_rating, 0).label("avg_rating"),
            func.coalesce(avg_subq.c.review_count, 0).label("review_count"),
        )
    )

    # ── Search: name, description, category, seller name
    if q:
        like = f"%{q}%"
        query = query.filter(
            Product.name.ilike(like)
            | Product.description.ilike(like)
            | Product.category.ilike(like)
        )

    if seller_q:
        query = query.filter(Business.name.ilike(f"%{seller_q}%"))

    if category and category in PRODUCT_CATEGORIES:
        query = query.filter(Product.category == category)

    if verified == "1":
        query = query.filter(Business.status == BusinessStatus.verified)

    try:
        if price_min:
            query = query.filter(Product.price >= float(price_min))
        if price_max:
            query = query.filter(Product.price <= float(price_max))
    except ValueError:
        price_min = price_max = ""

    if rating_min:
        try:
            r = int(rating_min)
            if 1 <= r <= 5:
                query = query.having(
                    func.coalesce(avg_subq.c.avg_rating, 0) >= r
                )
        except ValueError:
            rating_min = ""

    sort_map = {
        "newest":      Product.created_at.desc(),
        "oldest":      Product.created_at.asc(),
        "price_asc":   Product.price.asc(),
        "price_desc":  Product.price.desc(),
        "name_asc":    Product.name.asc(),
        "rating_desc": func.coalesce(avg_subq.c.avg_rating, 0).desc(),
    }
    query = query.order_by(sort_map.get(sort, Product.created_at.desc()))

    pagination = query.paginate(page=page, per_page=PER_PAGE, error_out=False)

    # Unpack (Product, avg_rating, review_count) rows
    rows     = pagination.items
    products = []
    for row in rows:
        p = row[0]
        p._avg_rating    = round(float(row[1]), 1) if row[1] else 0
        p._review_count  = int(row[2])
        products.append(p)

    # Price bounds for slider
    bounds = db.session.query(
        func.min(Product.price), func.max(Product.price)
    ).filter(Product.status == ProductStatus.active).one()
    price_floor = int(bounds[0] or 0)
    price_ceil  = int(bounds[1] or 500) + 1

    active_filters = _build_active_filters(q, seller_q, category, verified, price_min, price_max, rating_min)

    return render_template(
        "catalog/catalog.html",
        products       = products,
        pagination     = pagination,
        categories     = PRODUCT_CATEGORIES,
        q              = q,
        seller_q       = seller_q,
        category       = category,
        verified       = verified,
        sort           = sort,
        total          = pagination.total,
        price_min      = price_min,
        price_max      = price_max,
        rating_min     = rating_min,
        price_floor    = price_floor,
        price_ceil     = price_ceil,
        active_filters = active_filters,
    )


# ── Product Detail ────────────────────────────────────────────────────────────
@main_bp.route("/product/<int:product_id>")
def product_detail(product_id):
    from flask_login import current_user
    from sqlalchemy import func
    avg_subq = _avg_rating_subq()

    row = (
        Product.query
        .outerjoin(avg_subq, avg_subq.c.product_id == Product.id)
        .add_columns(
            func.coalesce(avg_subq.c.avg_rating, 0).label("avg_rating"),
            func.coalesce(avg_subq.c.review_count, 0).label("review_count"),
        )
        .filter(Product.id == product_id)
        .first_or_404()
    )

    product = row[0]
    if product.status != ProductStatus.active:
        abort(404)
    product._avg_rating   = round(float(row[1]), 1) if row[1] else 0
    product._review_count = int(row[2])

    # Record browsing history for authenticated users
    if current_user.is_authenticated:
        try:
            from app.services.recommendation_service import record_view
            record_view(current_user.id, product_id)
            db.session.commit()
        except Exception:
            db.session.rollback()

    # All reviews, newest first (no limit — we paginate client-side)
    reviews = (
        Review.query.filter_by(product_id=product_id)
        .order_by(Review.created_at.desc())
        .all()
    )

    # Rating breakdown: count per star 1-5
    breakdown = {}
    for i in range(1, 6):
        breakdown[i] = Review.query.filter_by(product_id=product_id, rating=i).count()

    # Current user's existing review (if any)
    my_review = None
    can_review = False
    if current_user.is_authenticated:
        my_review = Review.query.filter_by(
            user_id=current_user.id, product_id=product_id
        ).first()
        if not my_review:
            can_review = Review.user_purchased(current_user.id, product_id)

    related = (
        Product.query
        .filter(
            Product.category == product.category,
            Product.id != product.id,
            Product.status == ProductStatus.active,
            Product.stock_qty > 0,
        )
        .order_by(Product.created_at.desc())
        .limit(4).all()
    )

    uid = current_user.id if current_user.is_authenticated else None
    recs = get_recommendations(uid, exclude_ids=[product_id])

    return render_template(
        "catalog/product_detail.html",
        product    = product,
        related    = related,
        reviews    = reviews,
        breakdown  = breakdown,
        my_review  = my_review,
        can_review = can_review,
        recs       = recs,
    )


# ── Autocomplete Suggestions ──────────────────────────────────────────────────
@main_bp.route("/search/suggestions")
def search_suggestions():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])

    like = f"%{q}%"

    products = (
        Product.query
        .filter(
            Product.name.ilike(like) | Product.category.ilike(like),
            Product.status == ProductStatus.active
        )
        .with_entities(Product.name, Product.category)
        .limit(5).all()
    )
    sellers = (
        Business.query
        .filter(Business.name.ilike(like), Business.status == BusinessStatus.verified)
        .with_entities(Business.name)
        .limit(3).all()
    )
    categories = [c for c in PRODUCT_CATEGORIES if q.lower() in c.lower()][:3]

    results = []
    for p in products:
        results.append({"type": "product", "label": p.name, "sub": p.category or "Product"})
    for s in sellers:
        results.append({"type": "seller", "label": s.name, "sub": "Seller"})
    for c in categories:
        results.append({"type": "category", "label": c, "sub": "Category"})

    return jsonify(results)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _build_active_filters(q, seller_q, category, verified, price_min, price_max, rating_min):
    chips = []
    if q:
        chips.append({"key": "q",         "label": f'Search: "{q}"'})
    if seller_q:
        chips.append({"key": "seller",    "label": f'Seller: "{seller_q}"'})
    if category:
        chips.append({"key": "category",  "label": category})
    if verified == "1":
        chips.append({"key": "verified",  "label": "Women-Owned Only"})
    if price_min or price_max:
        lo = f"${price_min}" if price_min else "$0"
        hi = f"${price_max}" if price_max else "∞"
        chips.append({"key": "price",     "label": f"Price: {lo}–{hi}"})
    if rating_min:
        chips.append({"key": "rating",    "label": f"{rating_min}★ & up"})
    return chips
