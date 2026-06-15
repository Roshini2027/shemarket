from app import db
from datetime import datetime
import enum


class OrderStatus(enum.Enum):
    pending    = "pending"
    confirmed  = "confirmed"
    processing = "processing"
    shipped    = "shipped"
    delivered  = "delivered"
    cancelled  = "cancelled"
    refunded   = "refunded"


# ── Status metadata ───────────────────────────────────────────────────────────
_STATUS_META = {
    "pending":    ("warning",   "bi-clock-fill",          "Pending"),
    "confirmed":  ("primary",   "bi-check-circle-fill",   "Confirmed"),
    "processing": ("info",      "bi-arrow-repeat",         "Processing"),
    "shipped":    ("primary",   "bi-truck",               "Shipped"),
    "delivered":  ("success",   "bi-house-check-fill",    "Delivered"),
    "cancelled":  ("danger",    "bi-x-circle-fill",       "Cancelled"),
    "refunded":   ("secondary", "bi-arrow-counterclockwise", "Refunded"),
}

# Ordered pipeline used for the tracking timeline
ORDER_PIPELINE = ["pending", "confirmed", "processing", "shipped", "delivered"]


class Cart(db.Model):
    __tablename__ = "carts"

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user  = db.relationship("User", back_populates="cart")
    items = db.relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Cart user_id={self.user_id}>"


class CartItem(db.Model):
    __tablename__ = "cart_items"

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cart_id    = db.Column(db.Integer, db.ForeignKey("carts.id",    ondelete="CASCADE"),  nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"),  nullable=False)
    quantity   = db.Column(db.Integer, nullable=False, default=1)
    added_at   = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (db.UniqueConstraint("cart_id", "product_id", name="uq_cart_product"),)

    cart    = db.relationship("Cart",    back_populates="items")
    product = db.relationship("Product", back_populates="cart_items")

    def __repr__(self):
        return f"<CartItem cart_id={self.cart_id} product_id={self.product_id}>"


class Order(db.Model):
    __tablename__ = "orders"

    id               = db.Column(db.Integer,      primary_key=True, autoincrement=True)
    order_number     = db.Column(db.String(20),   unique=True, index=True)          # ORD100001
    user_id          = db.Column(db.Integer,      db.ForeignKey("users.id",   ondelete="RESTRICT"), nullable=False)
    status           = db.Column(db.Enum(OrderStatus), default=OrderStatus.pending, nullable=False)
    total_amount     = db.Column(db.Numeric(10, 2), nullable=False)
    shipping_address = db.Column(db.String(255),  nullable=False)
    notes            = db.Column(db.Text)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at       = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user    = db.relationship("User",      back_populates="orders")
    items   = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payment = db.relationship("Payment",   back_populates="order", uselist=False)

    # ── Computed helpers ──────────────────────────────────────────
    @property
    def order_number_display(self):
        return self.order_number or f"ORD{100000 + self.id}"

    def generate_order_number(self):
        """Call after flush() so self.id is available."""
        if not self.order_number:
            self.order_number = f"ORD{100000 + self.id}"

    @property
    def status_badge(self):
        meta = _STATUS_META.get(self.status.value, ("secondary", "bi-circle", self.status.value.title()))
        return meta   # (color, icon, label)

    @property
    def can_cancel(self):
        return self.status in (OrderStatus.pending, OrderStatus.confirmed)

    @property
    def subtotal(self):
        return sum(float(i.unit_price) * i.quantity for i in self.items)

    @property
    def shipping_cost(self):
        return round(float(self.total_amount) - self.subtotal, 2)

    @property
    def payment_status_label(self):
        if not self.payment:
            return ("secondary", "bi-circle", "No Payment")
        return self.payment.status_badge   # (color, icon, label)

    @property
    def pipeline_index(self):
        """Index in ORDER_PIPELINE for the tracking stepper (-1 if cancelled/refunded)."""
        try:
            return ORDER_PIPELINE.index(self.status.value)
        except ValueError:
            return -1

    def __repr__(self):
        return f"<Order {self.order_number_display} status={self.status.value}>"


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id         = db.Column(db.Integer,      primary_key=True, autoincrement=True)
    order_id   = db.Column(db.Integer,      db.ForeignKey("orders.id",   ondelete="CASCADE"),  nullable=False)
    product_id = db.Column(db.Integer,      db.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    quantity   = db.Column(db.Integer,      nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)

    order   = db.relationship("Order",   back_populates="items")
    product = db.relationship("Product", back_populates="order_items")

    @property
    def line_total(self):
        return round(float(self.unit_price) * self.quantity, 2)

    def __repr__(self):
        return f"<OrderItem order_id={self.order_id} product_id={self.product_id}>"
