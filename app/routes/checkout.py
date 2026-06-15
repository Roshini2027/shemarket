import uuid
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app import db
from app.models.order import Cart, CartItem, Order, OrderItem, OrderStatus
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.models.product import ProductStatus

checkout_bp = Blueprint("checkout", __name__)

SHIPPING_FEE   = 5.99
FREE_SHIPPING  = 50.00

PAYMENT_LABELS = {
    "credit_card":      "Credit Card",
    "debit_card":       "Debit Card",
    "upi":              "UPI",
    "net_banking":      "Net Banking",
    "wallet":           "Wallet",
    "cash_on_delivery": "Cash on Delivery",
}


def _cart_or_redirect():
    cart = current_user.cart
    if not cart or not cart.items:
        flash("Your cart is empty.", "warning")
        return None, redirect(url_for("cart.view_cart"))
    return cart, None


def _compute_totals(cart):
    subtotal = sum(float(i.product.price) * i.quantity for i in cart.items)
    shipping = 0.0 if subtotal >= FREE_SHIPPING else SHIPPING_FEE
    return round(subtotal, 2), round(shipping, 2), round(subtotal + shipping, 2)


# ── Step 1 & 2  GET: show address form + order review ────────────────────────
@checkout_bp.route("/", methods=["GET"])
@login_required
def checkout():
    cart, redir = _cart_or_redirect()
    if redir:
        return redir

    # Pre-fill from last order if exists
    last_order = (
        Order.query
        .filter_by(user_id=current_user.id)
        .order_by(Order.created_at.desc())
        .first()
    )
    prefill = last_order.shipping_address if last_order else ""

    subtotal, shipping, total = _compute_totals(cart)
    return render_template(
        "checkout/checkout.html",
        cart        = cart,
        subtotal    = subtotal,
        shipping    = shipping,
        total       = total,
        prefill     = prefill,
        pay_labels  = PAYMENT_LABELS,
        free_threshold = FREE_SHIPPING,
    )


# ── Step 3  POST: validate → create order → deduct stock → clear cart ────────
@checkout_bp.route("/", methods=["POST"])
@login_required
def place_order():
    cart, redir = _cart_or_redirect()
    if redir:
        return redir

    # ── Collect & validate address fields ────────────────────────
    full_name   = request.form.get("full_name",   "").strip()
    street      = request.form.get("street",      "").strip()
    city        = request.form.get("city",        "").strip()
    state       = request.form.get("state",       "").strip()
    postal_code = request.form.get("postal_code", "").strip()
    country     = request.form.get("country",     "").strip()
    phone       = request.form.get("phone",       "").strip()
    pay_method  = request.form.get("payment_method", "cash_on_delivery").strip()

    errors = []
    if not full_name:   errors.append("Full name is required.")
    if not street:      errors.append("Street address is required.")
    if not city:        errors.append("City is required.")
    if not postal_code: errors.append("Postal / ZIP code is required.")
    if not country:     errors.append("Country is required.")
    if pay_method not in PAYMENT_LABELS:
        pay_method = "cash_on_delivery"

    if errors:
        for e in errors:
            flash(e, "danger")
        subtotal, shipping, total = _compute_totals(cart)
        return render_template(
            "checkout/checkout.html",
            cart        = cart,
            subtotal    = subtotal,
            shipping    = shipping,
            total       = total,
            prefill     = street,
            pay_labels  = PAYMENT_LABELS,
            free_threshold = FREE_SHIPPING,
            form        = request.form,
        ), 422

    shipping_address = f"{full_name}, {street}, {city}, {state} {postal_code}, {country}"
    if phone:
        shipping_address += f" | {phone}"

    subtotal, shipping_cost, total = _compute_totals(cart)

    # ── Stock check (revalidate at purchase time) ─────────────────
    for item in cart.items:
        p = item.product
        if p.status != ProductStatus.active or p.stock_qty < item.quantity:
            flash(
                f'"{p.name}" is no longer available in the requested quantity. '
                f"Please update your cart.",
                "danger",
            )
            return redirect(url_for("cart.view_cart"))

    # ── Create Order ──────────────────────────────────────────────
    order = Order(
        user_id          = current_user.id,
        status           = OrderStatus.confirmed,
        total_amount     = total,
        shipping_address = shipping_address,
    )
    db.session.add(order)
    db.session.flush()   # get order.id
    order.generate_order_number()

    # ── Create OrderItems + deduct stock ──────────────────────────
    for item in cart.items:
        db.session.add(OrderItem(
            order_id   = order.id,
            product_id = item.product_id,
            quantity   = item.quantity,
            unit_price = item.product.price,
        ))
        item.product.stock_qty -= item.quantity
        # auto mark out-of-stock
        if item.product.stock_qty == 0:
            from app.models.product import ProductStatus as PS
            item.product.status = PS.out_of_stock

    # ── Create Payment record ─────────────────────────────────────
    try:
        method_enum = PaymentMethod(pay_method)
    except ValueError:
        method_enum = PaymentMethod.cash_on_delivery

    payment = Payment(
        order_id        = order.id,
        amount          = total,
        method          = method_enum,
        status          = PaymentStatus.pending,
        transaction_ref = str(uuid.uuid4()),
    )
    db.session.add(payment)

    # ── Clear Cart ────────────────────────────────────────────────
    CartItem.query.filter_by(cart_id=cart.id).delete()

    db.session.commit()

    # If method needs payment processing, go to payment page
    if method_enum != PaymentMethod.cash_on_delivery:
        return redirect(url_for("payment.payment_page", order_id=order.id))

    return redirect(url_for("checkout.confirmation", order_id=order.id))


# ── Confirmation page ─────────────────────────────────────────────────────────
@checkout_bp.route("/confirmation/<int:order_id>")
@login_required
def confirmation(order_id):
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    subtotal = sum(float(i.unit_price) * i.quantity for i in order.items)
    shipping = round(float(order.total_amount) - subtotal, 2)
    return render_template(
        "checkout/confirmation.html",
        order    = order,
        subtotal = round(subtotal, 2),
        shipping = shipping,
    )
