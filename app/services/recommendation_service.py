"""
Recommendation Service
======================
Scoring signals (all additive, verified business gets a multiplicative boost):

  browse_score    = sum of view_count for each browsed product's category
  purchase_score  = purchased product categories weighted ×3 (strong intent)
  recency_bonus   = products viewed/bought within last 30 days get +0.5
  verified_boost  = ×1.5 multiplier on final score for verified businesses
  trending_score  = (order_count × 2 + review_count) in last 30 days

Types produced:
  similar      — personalised, driven by browsing + purchase history
  trending     — global, high-velocity products
  women_owned  — verified businesses only, sorted by score
"""

from datetime import datetime, timedelta
from sqlalchemy import func
from app import db
from app.models.product import Product, ProductStatus
from app.models.business import Business, BusinessStatus
from app.models.order import Order, OrderItem, OrderStatus
from app.models.review import Review
from app.models.recommendation import BrowsingHistory, Recommendation, RecommendationType

# ── Constants ────────────────────────────────────────────────────────────────
VERIFIED_BOOST   = 1.5
PURCHASE_WEIGHT  = 3.0
RECENCY_DAYS     = 30
TRENDING_WINDOW  = timedelta(days=30)
MAX_RECS         = 8   # per section


# ── Public API ────────────────────────────────────────────────────────────────

def record_view(user_id: int, product_id: int) -> None:
    """Upsert a BrowsingHistory row. Silently swallowed if table doesn't exist."""
    try:
        row = BrowsingHistory.query.filter_by(
            user_id=user_id, product_id=product_id
        ).first()
        if row:
            row.view_count     += 1
            row.last_viewed_at  = datetime.utcnow()
        else:
            db.session.add(BrowsingHistory(
                user_id=user_id, product_id=product_id
            ))
    except Exception:
        db.session.rollback()


def get_recommendations(user_id: int | None, exclude_ids: list[int] | None = None) -> dict:
    """
    Return a dict with keys: 'similar', 'trending', 'women_owned'.
    Each value is a list of Product objects (up to MAX_RECS each).
    Returns empty lists for all keys if any database error occurs.
    """
    empty = {"similar": [], "trending": [], "women_owned": []}
    try:
        exclude_ids = set(exclude_ids or [])
        return {
            "similar":     _similar(user_id, exclude_ids),
            "trending":    _trending(exclude_ids),
            "women_owned": _women_owned(user_id, exclude_ids),
        }
    except Exception:
        db.session.rollback()
        return empty


# ── Internal builders ─────────────────────────────────────────────────────────

def _base_query():
    """Active, in-stock products joined with business."""
    return (
        Product.query
        .join(Product.business)
        .filter(
            Product.status  == ProductStatus.active,
            Product.stock_qty > 0,
        )
    )


def _apply_verified_boost(score: float, is_verified: bool) -> float:
    return score * VERIFIED_BOOST if is_verified else score


def _similar(user_id: int | None, exclude_ids: set) -> list:
    """
    Category-based collaborative score built from the user's browsing
    and purchase history.  Falls back to newest products for anonymous users.
    """
    if not user_id:
        return (
            _base_query()
            .filter(Product.id.notin_(exclude_ids))
            .order_by(Product.created_at.desc())
            .limit(MAX_RECS).all()
        )

    cutoff = datetime.utcnow() - timedelta(days=RECENCY_DAYS)

    # ── Browsing signal ─────────────────────────────────────────────
    browse_rows = (
        db.session.query(Product.category, func.sum(BrowsingHistory.view_count).label("w"))
        .join(BrowsingHistory, BrowsingHistory.product_id == Product.id)
        .filter(BrowsingHistory.user_id == user_id)
        .group_by(Product.category)
        .all()
    )
    cat_scores: dict[str, float] = {r.category: float(r.w) for r in browse_rows if r.category}

    # Recency bonus for recently browsed categories
    recent_cats = (
        db.session.query(Product.category)
        .join(BrowsingHistory, BrowsingHistory.product_id == Product.id)
        .filter(
            BrowsingHistory.user_id == user_id,
            BrowsingHistory.last_viewed_at >= cutoff,
        )
        .distinct().all()
    )
    for (cat,) in recent_cats:
        if cat:
            cat_scores[cat] = cat_scores.get(cat, 0) + 0.5

    # ── Purchase signal ────────────────────────────────────────────
    purchase_rows = (
        db.session.query(Product.category, func.count(OrderItem.id).label("c"))
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(
            Order.user_id == user_id,
            Order.status.in_([
                OrderStatus.delivered, OrderStatus.shipped,
                OrderStatus.confirmed, OrderStatus.processing,
            ]),
        )
        .group_by(Product.category)
        .all()
    )
    for row in purchase_rows:
        if row.category:
            cat_scores[row.category] = (
                cat_scores.get(row.category, 0) + row.c * PURCHASE_WEIGHT
            )

    if not cat_scores:
        # No history at all — fall back to trending
        return _trending(exclude_ids)

    # ── Already-seen product IDs (don't re-recommend what user browsed) ──
    seen_ids = {
        r.product_id
        for r in BrowsingHistory.query.filter_by(user_id=user_id).with_entities(BrowsingHistory.product_id)
    }
    exclude_ids = exclude_ids | seen_ids

    # ── Score candidate products ────────────────────────────────────
    candidates = (
        _base_query()
        .filter(Product.id.notin_(exclude_ids) if exclude_ids else True)
        .all()
    )

    scored = []
    for p in candidates:
        base = cat_scores.get(p.category, 0.0)
        if base <= 0:
            continue
        score = _apply_verified_boost(base, p.business.is_verified)
        scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:MAX_RECS]]


def _trending(exclude_ids: set) -> list:
    """
    Products with the highest (orders × 2 + reviews) count in the last
    TRENDING_WINDOW days.  Verified businesses get a 1.5× score boost.
    """
    cutoff = datetime.utcnow() - TRENDING_WINDOW

    order_subq = (
        db.session.query(
            OrderItem.product_id,
            func.count(OrderItem.id).label("order_cnt"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.created_at >= cutoff)
        .group_by(OrderItem.product_id)
        .subquery()
    )

    review_subq = (
        db.session.query(
            Review.product_id,
            func.count(Review.id).label("review_cnt"),
        )
        .filter(Review.created_at >= cutoff)
        .group_by(Review.product_id)
        .subquery()
    )

    rows = (
        _base_query()
        .filter(Product.id.notin_(exclude_ids) if exclude_ids else True)
        .outerjoin(order_subq,  order_subq.c.product_id  == Product.id)
        .outerjoin(review_subq, review_subq.c.product_id == Product.id)
        .add_columns(
            func.coalesce(order_subq.c.order_cnt,   0).label("order_cnt"),
            func.coalesce(review_subq.c.review_cnt, 0).label("review_cnt"),
        )
        .all()
    )

    scored = []
    for row in rows:
        p = row[0]
        raw = row.order_cnt * 2.0 + row.review_cnt
        if raw <= 0:
            continue
        score = _apply_verified_boost(raw, p.business.is_verified)
        scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)

    # Fall back to newest products if nothing has activity yet
    if not scored:
        return (
            _base_query()
            .filter(Product.id.notin_(exclude_ids) if exclude_ids else True)
            .order_by(Product.created_at.desc())
            .limit(MAX_RECS).all()
        )

    return [p for _, p in scored[:MAX_RECS]]


def _women_owned(user_id: int | None, exclude_ids: set) -> list:
    """
    Verified-business products only, scored by purchase popularity
    + average rating, with personalisation boost for user's preferred
    categories if history is available.
    """
    cat_pref: dict[str, float] = {}
    if user_id:
        rows = (
            db.session.query(Product.category, func.sum(BrowsingHistory.view_count).label("w"))
            .join(BrowsingHistory, BrowsingHistory.product_id == Product.id)
            .filter(BrowsingHistory.user_id == user_id)
            .group_by(Product.category)
            .all()
        )
        cat_pref = {r.category: float(r.w) for r in rows if r.category}

    order_subq = (
        db.session.query(
            OrderItem.product_id,
            func.count(OrderItem.id).label("cnt"),
        )
        .group_by(OrderItem.product_id)
        .subquery()
    )

    avg_subq = (
        db.session.query(
            Review.product_id,
            func.avg(Review.rating).label("avg_r"),
        )
        .group_by(Review.product_id)
        .subquery()
    )

    rows = (
        _base_query()
        .filter(
            Business.status == BusinessStatus.verified,
            Product.id.notin_(exclude_ids) if exclude_ids else True,
        )
        .outerjoin(order_subq, order_subq.c.product_id == Product.id)
        .outerjoin(avg_subq,   avg_subq.c.product_id   == Product.id)
        .add_columns(
            func.coalesce(order_subq.c.cnt,   0).label("order_cnt"),
            func.coalesce(avg_subq.c.avg_r,   0).label("avg_rating"),
        )
        .all()
    )

    scored = []
    for row in rows:
        p          = row[0]
        base       = row.order_cnt * 1.5 + float(row.avg_rating or 0) * 2.0
        pref_bonus = cat_pref.get(p.category, 0.0) * 0.3
        score      = base + pref_bonus + VERIFIED_BOOST   # always gets boost
        scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)

    if not scored:
        return (
            _base_query()
            .filter(Business.status == BusinessStatus.verified)
            .order_by(Product.created_at.desc())
            .limit(MAX_RECS).all()
        )

    return [p for _, p in scored[:MAX_RECS]]
