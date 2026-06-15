from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models.order import Order, OrderStatus, ORDER_PIPELINE
from app.models.payment import PaymentStatus
from app.services.recommendation_service import get_recommendations

orders_bp = Blueprint("orders", __name__)

SELLER_TRANSITIONS = {
    OrderStatus.confirmed:  [OrderStatus.processing, OrderStatus.cancelled],
    OrderStatus.processing: [OrderStatus.shipped,    OrderStatus.cancelled],
    OrderStatus.shipped:    [OrderStatus.delivered],
}


def _status_tab_counts(base_query):
    counts = {"all": base_query.count()}
    for s in OrderStatus:
        counts[s.value] = base_query.filter(Order.status == s).count()
    return counts


# ── Customer: list all orders ──────────────────────────────────────────────────
@orders_bp.route("/")
@login_required
def my_orders():
    status_filter = request.args.get("status", "all")
    q = Order.query.filter_by(user_id=current_user.id)
    if status_filter != "all":
        try:
            q = q.filter(Order.status == OrderStatus(status_filter))
        except ValueError:
            pass
    orders = q.order_by(Order.created_at.desc()).all()
    counts = _status_tab_counts(Order.query.filter_by(user_id=current_user.id))
    recs = get_recommendations(current_user.id)
    return render_template("orders/my_orders.html",
                           orders=orders, status_filter=status_filter, counts=counts, recs=recs)


# ── Customer: order detail + tracking ─────────────────────────────────────────
@orders_bp.route("/<int:order_id>")
@login_required
def order_detail(order_id):
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    return render_template("orders/order_detail.html",
                           order=order, pipeline=ORDER_PIPELINE)


# ── Customer: cancel order ─────────────────────────────────────────────────────
@orders_bp.route("/<int:order_id>/cancel", methods=["POST"])
@login_required
def cancel_order(order_id):
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    if not order.can_cancel:
        flash("This order can no longer be cancelled.", "warning")
        return redirect(url_for("orders.order_detail", order_id=order_id))

    # Restore stock
    for item in order.items:
        item.product.stock_qty += item.quantity
        from app.models.product import ProductStatus
        if item.product.status.value == "out_of_stock":
            item.product.status = ProductStatus.active

    order.status = OrderStatus.cancelled

    # Mark payment failed if still pending
    if order.payment and order.payment.status == PaymentStatus.pending:
        order.payment.status = PaymentStatus.failed

    db.session.commit()
    flash(f"Order {order.order_number_display} has been cancelled.", "info")
    return redirect(url_for("orders.my_orders"))


# ── Seller: orders dashboard ───────────────────────────────────────────────────
@orders_bp.route("/seller")
@login_required
def seller_orders():
    if not current_user.business:
        flash("You need a registered business to view orders.", "warning")
        return redirect(url_for("seller.dashboard"))

    biz_id        = current_user.business.id
    status_filter = request.args.get("status", "all")

    # All orders that contain at least one product from this seller's business
    from app.models.order import OrderItem
    from app.models.product import Product
    base = (Order.query
            .join(Order.items)
            .join(OrderItem.product)
            .filter(Product.business_id == biz_id)
            .distinct())

    if status_filter != "all":
        try:
            base = base.filter(Order.status == OrderStatus(status_filter))
        except ValueError:
            pass

    orders = base.order_by(Order.created_at.desc()).all()

    # Counts use same join
    from app.models.order import OrderItem as OI
    def _cnt(status_val=None):
        q = (Order.query.join(Order.items).join(OI.product)
             .filter(Product.business_id == biz_id).distinct())
        if status_val:
            q = q.filter(Order.status == OrderStatus(status_val))
        return q.count()

    counts = {"all": _cnt()}
    for s in OrderStatus:
        counts[s.value] = _cnt(s.value)

    return render_template("orders/seller_orders.html",
                           orders=orders,
                           status_filter=status_filter,
                           counts=counts,
                           transitions=SELLER_TRANSITIONS)


# ── Seller: update order status ────────────────────────────────────────────────
@orders_bp.route("/seller/<int:order_id>/status", methods=["POST"])
@login_required
def update_order_status(order_id):
    if not current_user.business:
        abort(403)

    order      = Order.query.get_or_404(order_id)
    new_status = request.form.get("new_status", "").strip()

    # Verify order contains a product from this seller
    biz_id = current_user.business.id
    owns = any(item.product.business_id == biz_id for item in order.items)
    if not owns:
        abort(403)

    allowed = [s.value for s in SELLER_TRANSITIONS.get(order.status, [])]
    if new_status not in allowed:
        flash("Invalid status transition.", "danger")
        return redirect(url_for("orders.seller_orders"))

    order.status = OrderStatus(new_status)
    db.session.commit()
    flash(f"Order {order.order_number_display} updated to {new_status.title()}.", "success")
    return redirect(url_for("orders.seller_orders"))
