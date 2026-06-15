from flask import Blueprint, render_template, redirect, url_for, request, jsonify, flash
from flask_login import login_required, current_user
from app import db
from app.models.order import Cart, CartItem
from app.models.product import Product, ProductStatus

cart_bp = Blueprint("cart", __name__)


def _get_or_create_cart():
    cart = current_user.cart
    if not cart:
        cart = Cart(user_id=current_user.id)
        db.session.add(cart)
        db.session.flush()
    return cart


def _cart_totals(cart):
    subtotal = sum(float(i.product.price) * i.quantity for i in cart.items)
    shipping  = 0.0 if subtotal >= 50 else 5.99
    total     = subtotal + shipping
    return round(subtotal, 2), round(shipping, 2), round(total, 2)


# ── View Cart ─────────────────────────────────────────────────────────────────
@cart_bp.route("/")
@login_required
def view_cart():
    cart = current_user.cart
    if not cart or not cart.items:
        return render_template("cart/cart.html", cart=None, subtotal=0, shipping=0, total=0)
    subtotal, shipping, total = _cart_totals(cart)
    return render_template("cart/cart.html",
                           cart=cart,
                           subtotal=subtotal,
                           shipping=shipping,
                           total=total)


# ── Add to Cart ───────────────────────────────────────────────────────────────
@cart_bp.route("/add", methods=["POST"])
@login_required
def add_to_cart():
    data       = request.get_json(silent=True) or {}
    product_id = data.get("product_id") or request.form.get("product_id", type=int)
    quantity   = int(data.get("quantity", 1) or request.form.get("quantity", 1))

    product = Product.query.get(product_id)
    if not product or product.status != ProductStatus.active or product.stock_qty < 1:
        return jsonify({"ok": False, "msg": "Product unavailable."}), 400

    quantity = max(1, min(quantity, product.stock_qty))

    cart = _get_or_create_cart()
    item = CartItem.query.filter_by(cart_id=cart.id, product_id=product_id).first()

    if item:
        item.quantity = min(item.quantity + quantity, product.stock_qty)
    else:
        item = CartItem(cart_id=cart.id, product_id=product_id, quantity=quantity)
        db.session.add(item)

    db.session.commit()
    cart_count = sum(i.quantity for i in cart.items)
    return jsonify({"ok": True, "msg": f'"{product.name}" added to cart.', "cart_count": cart_count})


# ── Update Quantity ───────────────────────────────────────────────────────────
@cart_bp.route("/update/<int:item_id>", methods=["POST"])
@login_required
def update_quantity(item_id):
    data     = request.get_json(silent=True) or {}
    quantity = int(data.get("quantity", 1))

    item = CartItem.query.get_or_404(item_id)
    if item.cart.user_id != current_user.id:
        return jsonify({"ok": False, "msg": "Forbidden."}), 403

    if quantity < 1:
        db.session.delete(item)
        db.session.commit()
        cart = current_user.cart
        subtotal, shipping, total = _cart_totals(cart) if cart and cart.items else (0, 0, 0)
        return jsonify({"ok": True, "removed": True,
                        "subtotal": subtotal, "shipping": shipping, "total": total,
                        "cart_count": sum(i.quantity for i in cart.items) if cart else 0})

    max_qty  = item.product.stock_qty
    quantity = min(quantity, max_qty)
    item.quantity = quantity
    db.session.commit()

    cart = current_user.cart
    subtotal, shipping, total = _cart_totals(cart)
    line_total = round(float(item.product.price) * quantity, 2)
    return jsonify({"ok": True, "quantity": quantity, "line_total": line_total,
                    "subtotal": subtotal, "shipping": shipping, "total": total,
                    "cart_count": sum(i.quantity for i in cart.items)})


# ── Remove Item ───────────────────────────────────────────────────────────────
@cart_bp.route("/remove/<int:item_id>", methods=["POST"])
@login_required
def remove_item(item_id):
    item = CartItem.query.get_or_404(item_id)
    if item.cart.user_id != current_user.id:
        return jsonify({"ok": False, "msg": "Forbidden."}), 403

    db.session.delete(item)
    db.session.commit()

    cart = current_user.cart
    subtotal, shipping, total = _cart_totals(cart) if cart and cart.items else (0, 0, 0)
    return jsonify({"ok": True,
                    "subtotal": subtotal, "shipping": shipping, "total": total,
                    "cart_count": sum(i.quantity for i in cart.items) if cart else 0})


# ── Clear Cart ────────────────────────────────────────────────────────────────
@cart_bp.route("/clear", methods=["POST"])
@login_required
def clear_cart():
    cart = current_user.cart
    if cart:
        CartItem.query.filter_by(cart_id=cart.id).delete()
        db.session.commit()
    flash("Your cart has been cleared.", "info")
    return redirect(url_for("cart.view_cart"))
