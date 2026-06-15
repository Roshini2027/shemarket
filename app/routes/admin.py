from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import func, or_
from app import db
from app.models.business import Business, BusinessStatus, VerificationDocument, DocStatus, REQUIRED_DOC_TYPES
from app.models.order import Order, OrderItem, OrderStatus
from app.models.payment import Payment, PaymentStatus
from app.models.product import Product, ProductStatus, PRODUCT_CATEGORIES
from app.models.user import User, UserRole, UserStatus

admin_bp = Blueprint("admin", __name__)

PER_PAGE = 20


def _guard():
    if not current_user.is_authenticated or current_user.role != UserRole.admin:
        flash("Admin access required.", "danger")
        return redirect(url_for("main.index"))
    return None


# ── Dashboard ─────────────────────────────────────────────────────────────────

@admin_bp.route("/")
@login_required
def dashboard():
    g = _guard()
    if g:
        return g

    stats = {
        "total_users":    User.query.count(),
        "customers":      User.query.filter_by(role=UserRole.customer).count(),
        "sellers":        User.query.filter_by(role=UserRole.business_owner).count(),
        "verified_biz":   Business.query.filter_by(status=BusinessStatus.verified).count(),
        "pending_verif":  Business.query.filter_by(status=BusinessStatus.pending_verification).count(),
        "total_products": Product.query.count(),
        "total_orders":   Order.query.count(),
        "revenue":        db.session.query(
                              func.coalesce(func.sum(Payment.amount), 0)
                          ).filter_by(status=PaymentStatus.completed).scalar(),
    }

    recent_orders    = Order.query.order_by(Order.created_at.desc()).limit(8).all()
    recent_users     = User.query.order_by(User.created_at.desc()).limit(6).all()
    pending_businesses = (
        Business.query
        .filter_by(status=BusinessStatus.pending_verification)
        .order_by(Business.created_at.asc())
        .limit(5).all()
    )

    order_breakdown = {
        "pending":    Order.query.filter_by(status=OrderStatus.pending).count(),
        "confirmed":  Order.query.filter_by(status=OrderStatus.confirmed).count(),
        "processing": Order.query.filter_by(status=OrderStatus.processing).count(),
        "shipped":    Order.query.filter_by(status=OrderStatus.shipped).count(),
        "delivered":  Order.query.filter_by(status=OrderStatus.delivered).count(),
        "cancelled":  Order.query.filter_by(status=OrderStatus.cancelled).count(),
    }

    return render_template(
        "admin/dashboard.html",
        stats              = stats,
        recent_orders      = recent_orders,
        recent_users       = recent_users,
        pending_businesses = pending_businesses,
        order_breakdown    = order_breakdown,
        pending_verif_count = stats["pending_verif"],
    )


# ── Users ─────────────────────────────────────────────────────────────────────

@admin_bp.route("/users")
@login_required
def users_list():
    g = _guard()
    if g:
        return g

    q      = request.args.get("q", "").strip()
    role   = request.args.get("role", "")
    status = request.args.get("status", "")
    page   = request.args.get("page", 1, type=int)

    query = User.query
    if q:
        like = f"%{q}%"
        query = query.filter(User.full_name.ilike(like) | User.email.ilike(like))
    if role:
        try:
            query = query.filter_by(role=UserRole(role))
        except ValueError:
            pass
    if status:
        try:
            query = query.filter_by(status=UserStatus(status))
        except ValueError:
            pass

    pagination = query.order_by(User.created_at.desc()).paginate(page=page, per_page=PER_PAGE, error_out=False)

    counts = {
        "total":     User.query.count(),
        "customers": User.query.filter_by(role=UserRole.customer).count(),
        "sellers":   User.query.filter_by(role=UserRole.business_owner).count(),
        "admins":    User.query.filter_by(role=UserRole.admin).count(),
        "suspended": User.query.filter_by(status=UserStatus.suspended).count(),
    }

    return render_template("admin/users.html",
                           users=pagination.items, pagination=pagination,
                           counts=counts, q=q, role=role, status=status)


@admin_bp.route("/users/<int:user_id>/block", methods=["POST"])
@login_required
def block_user(user_id):
    g = _guard()
    if g:
        return g
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You cannot block yourself.", "danger")
    else:
        user.status = UserStatus.suspended
        db.session.commit()
        flash(f"{user.full_name} has been blocked.", "warning")
    return redirect(url_for("admin.users_list", **_back_args()))


@admin_bp.route("/users/<int:user_id>/activate", methods=["POST"])
@login_required
def activate_user(user_id):
    g = _guard()
    if g:
        return g
    user = User.query.get_or_404(user_id)
    user.status = UserStatus.active
    db.session.commit()
    flash(f"{user.full_name} has been activated.", "success")
    return redirect(url_for("admin.users_list", **_back_args()))


# ── Sellers ───────────────────────────────────────────────────────────────────

@admin_bp.route("/sellers")
@login_required
def sellers_list():
    g = _guard()
    if g:
        return g

    q      = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    page   = request.args.get("page", 1, type=int)

    query = Business.query.join(Business.owner)
    if q:
        like = f"%{q}%"
        query = query.filter(Business.name.ilike(like) | User.full_name.ilike(like) | User.email.ilike(like))
    if status:
        try:
            query = query.filter(Business.status == BusinessStatus(status))
        except ValueError:
            pass

    pagination = query.order_by(Business.created_at.desc()).paginate(page=page, per_page=PER_PAGE, error_out=False)

    counts = {
        "total":     Business.query.count(),
        "verified":  Business.query.filter_by(status=BusinessStatus.verified).count(),
        "pending":   Business.query.filter_by(status=BusinessStatus.pending_verification).count(),
        "rejected":  Business.query.filter_by(status=BusinessStatus.rejected).count(),
        "suspended": Business.query.filter_by(status=BusinessStatus.suspended).count(),
    }

    return render_template("admin/sellers.html",
                           businesses=pagination.items, pagination=pagination,
                           counts=counts, q=q, status=status)


@admin_bp.route("/sellers/<int:business_id>/suspend", methods=["POST"])
@login_required
def suspend_seller(business_id):
    g = _guard()
    if g:
        return g
    biz = Business.query.get_or_404(business_id)
    biz.status = BusinessStatus.suspended
    db.session.commit()
    flash(f"'{biz.name}' has been suspended.", "warning")
    return redirect(url_for("admin.sellers_list"))


@admin_bp.route("/sellers/<int:business_id>/reinstate", methods=["POST"])
@login_required
def reinstate_seller(business_id):
    g = _guard()
    if g:
        return g
    biz = Business.query.get_or_404(business_id)
    biz.status = BusinessStatus.verified if biz.verified_at else BusinessStatus.pending_verification
    db.session.commit()
    flash(f"'{biz.name}' has been reinstated.", "success")
    return redirect(url_for("admin.sellers_list"))


# ── Verification Queue ─────────────────────────────────────────────────────────

@admin_bp.route("/verifications")
@login_required
def verification_list():
    g = _guard()
    if g:
        return g

    status_filter = request.args.get("status", "pending_verification")
    query = Business.query

    if status_filter == "all":
        businesses = query.order_by(Business.created_at.desc()).all()
    else:
        try:
            status_enum = BusinessStatus(status_filter)
        except ValueError:
            status_enum = BusinessStatus.pending_verification
        businesses = query.filter_by(status=status_enum).order_by(Business.created_at.asc()).all()

    counts = {
        "pending":  Business.query.filter_by(status=BusinessStatus.pending_verification).count(),
        "verified": Business.query.filter_by(status=BusinessStatus.verified).count(),
        "rejected": Business.query.filter_by(status=BusinessStatus.rejected).count(),
    }

    return render_template("admin/verification_list.html",
                           businesses=businesses,
                           status_filter=status_filter,
                           counts=counts,
                           pending_verif_count=counts["pending"])


@admin_bp.route("/verifications/<int:business_id>")
@login_required
def verification_detail(business_id):
    g = _guard()
    if g:
        return g

    business      = Business.query.get_or_404(business_id)
    docs_map      = {d.doc_type: d for d in business.verification_documents}
    required_docs = REQUIRED_DOC_TYPES
    pending_verif_count = Business.query.filter_by(status=BusinessStatus.pending_verification).count()

    return render_template("admin/verification_detail.html",
                           business=business,
                           docs_map=docs_map,
                           required_docs=required_docs,
                           pending_verif_count=pending_verif_count)


@admin_bp.route("/verifications/<int:business_id>/approve", methods=["POST"])
@login_required
def approve_business(business_id):
    g = _guard()
    if g:
        return g

    business = Business.query.get_or_404(business_id)
    if not business.docs_complete():
        flash("Cannot approve: not all required documents have been uploaded.", "danger")
        return redirect(url_for("admin.verification_detail", business_id=business_id))

    now = datetime.utcnow()
    business.status            = BusinessStatus.verified
    business.verified_at       = now
    business.rejection_comment = None

    for doc in business.verification_documents:
        doc.doc_status  = DocStatus.approved
        doc.reviewed_by = current_user.id
        doc.reviewed_at = now

    db.session.commit()
    flash(f"'{business.name}' has been verified and is now live on SheMarket.", "success")
    return redirect(url_for("admin.verification_list"))


@admin_bp.route("/verifications/<int:business_id>/reject", methods=["POST"])
@login_required
def reject_business(business_id):
    g = _guard()
    if g:
        return g

    business = Business.query.get_or_404(business_id)
    comment  = request.form.get("rejection_comment", "").strip()

    if not comment:
        flash("A rejection comment is required.", "danger")
        return redirect(url_for("admin.verification_detail", business_id=business_id))

    now = datetime.utcnow()
    business.status            = BusinessStatus.rejected
    business.rejection_comment = comment
    business.verified_at       = None

    for doc in business.verification_documents:
        doc.doc_status        = DocStatus.rejected
        doc.reviewed_by       = current_user.id
        doc.reviewed_at       = now
        doc.rejection_comment = comment

    db.session.commit()
    flash(f"'{business.name}' verification has been rejected.", "warning")
    return redirect(url_for("admin.verification_list"))


# ── Products ──────────────────────────────────────────────────────────────────

@admin_bp.route("/products")
@login_required
def products_list():
    g = _guard()
    if g:
        return g

    q        = request.args.get("q", "").strip()
    category = request.args.get("category", "")
    status   = request.args.get("status", "")
    page     = request.args.get("page", 1, type=int)

    query = Product.query.join(Product.business).join(Business.owner)
    if q:
        like = f"%{q}%"
        query = query.filter(Product.name.ilike(like) | Business.name.ilike(like))
    if category:
        query = query.filter(Product.category == category)
    if status:
        try:
            query = query.filter(Product.status == ProductStatus(status))
        except ValueError:
            pass

    pagination = query.order_by(Product.created_at.desc()).paginate(page=page, per_page=PER_PAGE, error_out=False)

    return render_template("admin/products.html",
                           products=pagination.items, pagination=pagination,
                           categories=PRODUCT_CATEGORIES,
                           q=q, category=category, status=status)


@admin_bp.route("/products/<int:product_id>/remove", methods=["POST"])
@login_required
def remove_product(product_id):
    g = _guard()
    if g:
        return g
    product = Product.query.get_or_404(product_id)
    name = product.name
    db.session.delete(product)
    db.session.commit()
    flash(f'"{name}" has been removed from the platform.', "success")
    return redirect(url_for("admin.products_list"))


# ── Orders ────────────────────────────────────────────────────────────────────

@admin_bp.route("/orders")
@login_required
def orders_list():
    g = _guard()
    if g:
        return g

    q      = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    page   = request.args.get("page", 1, type=int)

    query = Order.query.join(Order.user)
    if q:
        like = f"%{q}%"
        query = query.filter(
            Order.order_number.ilike(like)
            | User.full_name.ilike(like)
            | User.email.ilike(like)
        )
    if status:
        try:
            query = query.filter(Order.status == OrderStatus(status))
        except ValueError:
            pass

    pagination = query.order_by(Order.created_at.desc()).paginate(page=page, per_page=PER_PAGE, error_out=False)

    counts = {
        "total":      Order.query.count(),
        "pending":    Order.query.filter_by(status=OrderStatus.pending).count(),
        "processing": Order.query.filter_by(status=OrderStatus.processing).count(),
        "shipped":    Order.query.filter_by(status=OrderStatus.shipped).count(),
        "delivered":  Order.query.filter_by(status=OrderStatus.delivered).count(),
        "cancelled":  Order.query.filter_by(status=OrderStatus.cancelled).count(),
    }

    return render_template("admin/orders.html",
                           orders=pagination.items, pagination=pagination,
                           counts=counts, q=q, status=status)


# ── Payments ──────────────────────────────────────────────────────────────────

@admin_bp.route("/payments")
@login_required
def payments_list():
    g = _guard()
    if g:
        return g

    status_filter = request.args.get("status", "all")
    page          = request.args.get("page", 1, type=int)

    query = Payment.query.join(Payment.order)
    if status_filter != "all":
        try:
            query = query.filter(Payment.status == PaymentStatus(status_filter))
        except ValueError:
            pass

    pagination = query.order_by(Payment.created_at.desc()).paginate(page=page, per_page=PER_PAGE, error_out=False)

    stats = {
        "total":     Payment.query.count(),
        "completed": Payment.query.filter_by(status=PaymentStatus.completed).count(),
        "pending":   Payment.query.filter_by(status=PaymentStatus.pending).count(),
        "failed":    Payment.query.filter_by(status=PaymentStatus.failed).count(),
        "revenue":   db.session.query(
                         func.coalesce(func.sum(Payment.amount), 0)
                     ).filter_by(status=PaymentStatus.completed).scalar(),
    }

    return render_template(
        "admin/payments.html",
        payments      = pagination.items,
        pagination    = pagination,
        status_filter = status_filter,
        stats         = stats,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _back_args():
    """Preserve filter args on redirect."""
    return {k: v for k, v in request.args.items() if k in ("q", "role", "status", "page")}
