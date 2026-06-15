from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from app import db
from app.models.order import Order, OrderStatus
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.services.payment_service import process_payment

payment_bp = Blueprint("payment", __name__)

# Net banking options shown in the dropdown
BANKS = [
    ("SBI",   "State Bank of India"),
    ("HDFC",  "HDFC Bank"),
    ("ICICI", "ICICI Bank"),
    ("AXIS",  "Axis Bank"),
    ("KOTAK", "Kotak Mahindra Bank"),
    ("PNB",   "Punjab National Bank"),
    ("BOB",   "Bank of Baroda"),
    ("YES",   "Yes Bank"),
    ("CANARA","Canara Bank"),
    ("UNION", "Union Bank of India"),
]


def _owned_order(order_id: int) -> Order:
    """Return order only if it belongs to current_user, else 404."""
    return Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()


# ── Payment page ──────────────────────────────────────────────────────────────
@payment_bp.route("/<int:order_id>", methods=["GET"])
@login_required
def payment_page(order_id):
    order = _owned_order(order_id)

    # If already paid, skip straight to success
    if order.payment and order.payment.status == PaymentStatus.completed:
        return redirect(url_for("payment.payment_success", order_id=order.id))

    subtotal = sum(float(i.unit_price) * i.quantity for i in order.items)
    shipping = round(float(order.total_amount) - subtotal, 2)

    return render_template(
        "payment/payment.html",
        order    = order,
        subtotal = round(subtotal, 2),
        shipping = shipping,
        banks    = BANKS,
    )


# ── Process payment ───────────────────────────────────────────────────────────
@payment_bp.route("/<int:order_id>/process", methods=["POST"])
@login_required
def process(order_id):
    order = _owned_order(order_id)

    if order.payment and order.payment.status == PaymentStatus.completed:
        return redirect(url_for("payment.payment_success", order_id=order.id))

    method_str = request.form.get("payment_method", "credit_card").strip()

    success, msg, payment = process_payment(order, method_str, request.form)

    if not success:
        flash(msg, "danger")
        return redirect(url_for("payment.payment_page", order_id=order.id))

    return redirect(url_for("payment.payment_success", order_id=order.id))


# ── Success page ──────────────────────────────────────────────────────────────
@payment_bp.route("/<int:order_id>/success")
@login_required
def payment_success(order_id):
    order = _owned_order(order_id)

    if not order.payment or order.payment.status != PaymentStatus.completed:
        flash("Payment not completed for this order.", "warning")
        return redirect(url_for("payment.payment_page", order_id=order.id))

    subtotal = sum(float(i.unit_price) * i.quantity for i in order.items)
    shipping = round(float(order.total_amount) - subtotal, 2)

    return render_template(
        "payment/success.html",
        order    = order,
        payment  = order.payment,
        subtotal = round(subtotal, 2),
        shipping = shipping,
    )


# ── Payment history (customer) ────────────────────────────────────────────────
@payment_bp.route("/history")
@login_required
def history():
    payments = (
        Payment.query
        .join(Payment.order)
        .filter(Order.user_id == current_user.id)
        .order_by(Payment.created_at.desc())
        .all()
    )
    return render_template("payment/history.html", payments=payments)
