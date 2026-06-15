from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.product import Product, ProductImage, ProductStatus, PRODUCT_CATEGORIES
from app.models.user import UserRole
from app.utils.upload import save_image, delete_image

products_bp = Blueprint("products", __name__)

MAX_IMAGES = 6


def _get_seller_product(product_id):
    """Return product only if it belongs to the current seller, else abort."""
    product = Product.query.get_or_404(product_id)
    if not current_user.business or product.business_id != current_user.business.id:
        abort(403)
    return product


def _seller_required():
    if current_user.role != UserRole.business_owner or not current_user.business:
        flash("Seller account with a registered business is required.", "warning")
        return redirect(url_for("main.index"))
    return None


# ── Product List ───────────────────────────────────────────────────────────────

@products_bp.route("/")
@login_required
def list_products():
    guard = _seller_required()
    if guard:
        return guard

    status_filter = request.args.get("status", "all")
    query = Product.query.filter_by(business_id=current_user.business.id)

    if status_filter != "all":
        try:
            query = query.filter_by(status=ProductStatus(status_filter))
        except ValueError:
            pass

    products = query.order_by(Product.created_at.desc()).all()

    counts = {
        "all":          Product.query.filter_by(business_id=current_user.business.id).count(),
        "active":       Product.query.filter_by(business_id=current_user.business.id, status=ProductStatus.active).count(),
        "inactive":     Product.query.filter_by(business_id=current_user.business.id, status=ProductStatus.inactive).count(),
        "out_of_stock": Product.query.filter_by(business_id=current_user.business.id, status=ProductStatus.out_of_stock).count(),
    }

    return render_template("seller/products.html",
                           products=products,
                           status_filter=status_filter,
                           counts=counts,
                           business=current_user.business)


# ── Add Product ────────────────────────────────────────────────────────────────

@products_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_product():
    guard = _seller_required()
    if guard:
        return guard

    if request.method == "POST":
        errors, product = _process_product_form(None)
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("seller/product_form.html",
                                   categories=PRODUCT_CATEGORIES,
                                   form_data=request.form,
                                   product=None)
        db.session.add(product)
        db.session.flush()  # get product.id before saving images
        _process_images(product, request.files.getlist("images"))
        db.session.commit()
        flash(f"'{product.name}' has been listed.", "success")
        return redirect(url_for("products.list_products"))

    return render_template("seller/product_form.html",
                           categories=PRODUCT_CATEGORIES,
                           form_data={},
                           product=None)


# ── Edit Product ───────────────────────────────────────────────────────────────

@products_bp.route("/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def edit_product(product_id):
    guard = _seller_required()
    if guard:
        return guard

    product = _get_seller_product(product_id)

    if request.method == "POST":
        errors, _ = _process_product_form(product)
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("seller/product_form.html",
                                   categories=PRODUCT_CATEGORIES,
                                   form_data=request.form,
                                   product=product)
        new_files = request.files.getlist("images")
        remaining = MAX_IMAGES - len(product.images)
        if new_files and new_files[0].filename:
            _process_images(product, new_files[:remaining])
        db.session.commit()
        flash(f"'{product.name}' has been updated.", "success")
        return redirect(url_for("products.list_products"))

    return render_template("seller/product_form.html",
                           categories=PRODUCT_CATEGORIES,
                           form_data={},
                           product=product)


# ── Delete Product ─────────────────────────────────────────────────────────────

@products_bp.route("/<int:product_id>/delete", methods=["POST"])
@login_required
def delete_product(product_id):
    guard = _seller_required()
    if guard:
        return guard

    product = _get_seller_product(product_id)

    for img in product.images:
        delete_image(img.image_url, "products")

    db.session.delete(product)
    db.session.commit()
    flash(f"'{product.name}' has been deleted.", "info")
    return redirect(url_for("products.list_products"))


# ── Delete Single Image ────────────────────────────────────────────────────────

@products_bp.route("/image/<int:image_id>/delete", methods=["POST"])
@login_required
def delete_product_image(image_id):
    guard = _seller_required()
    if guard:
        return guard

    img = ProductImage.query.get_or_404(image_id)
    _get_seller_product(img.product_id)  # ownership check

    was_primary = img.is_primary
    product     = img.product

    delete_image(img.image_url, "products")
    db.session.delete(img)
    db.session.flush()

    # Promote first remaining image to primary if the primary was removed
    if was_primary and product.images:
        product.images[0].is_primary = True

    db.session.commit()
    flash("Image removed.", "info")
    return redirect(url_for("products.edit_product", product_id=img.product_id))


# ── Set Primary Image ──────────────────────────────────────────────────────────

@products_bp.route("/image/<int:image_id>/set-primary", methods=["POST"])
@login_required
def set_primary_image(image_id):
    guard = _seller_required()
    if guard:
        return guard

    img     = ProductImage.query.get_or_404(image_id)
    product = _get_seller_product(img.product_id)

    for i in product.images:
        i.is_primary = (i.id == image_id)

    db.session.commit()
    flash("Primary image updated.", "success")
    return redirect(url_for("products.edit_product", product_id=img.product_id))


# ── Helpers ────────────────────────────────────────────────────────────────────

def _process_product_form(product):
    """Validate form and apply to product (new or existing). Returns (errors, product)."""
    name        = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    category    = request.form.get("category", "").strip()
    price_raw   = request.form.get("price", "").strip()
    qty_raw     = request.form.get("stock_qty", "0").strip()
    status_raw  = request.form.get("status", "active")

    errors = []

    if not name:
        errors.append("Product name is required.")
    if len(name) > 200:
        errors.append("Product name must be 200 characters or fewer.")
    if not description or len(description) < 20:
        errors.append("Description must be at least 20 characters.")
    if not category:
        errors.append("Please select a category.")

    try:
        price = float(price_raw)
        if price <= 0:
            raise ValueError
    except ValueError:
        price = None
        errors.append("Price must be a positive number.")

    try:
        qty = int(qty_raw)
        if qty < 0:
            raise ValueError
    except ValueError:
        qty = None
        errors.append("Quantity must be a non-negative whole number.")

    try:
        status = ProductStatus(status_raw)
    except ValueError:
        status = ProductStatus.active

    if errors:
        return errors, product

    if product is None:
        product = Product(business_id=current_user.business.id)

    product.name        = name
    product.description = description
    product.category    = category
    product.price       = price
    product.stock_qty   = qty
    product.status      = status

    # Auto-set out_of_stock when qty hits 0
    if qty == 0 and status == ProductStatus.active:
        product.status = ProductStatus.out_of_stock

    return [], product


def _process_images(product, files):
    """Save uploaded image files and attach to product. First image becomes primary if none set."""
    has_primary = any(img.is_primary for img in product.images)

    for idx, file in enumerate(files):
        if not file or not file.filename:
            continue
        filename = save_image(file, "products")
        if not filename:
            continue
        is_primary = not has_primary
        img = ProductImage(
            product_id = product.id,
            image_url  = filename,
            is_primary = is_primary,
            sort_order = len(product.images) + idx,
        )
        db.session.add(img)
        has_primary = True
