from app import db
from datetime import datetime


class Review(db.Model):
    __tablename__ = "reviews"

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id",    ondelete="CASCADE"),  nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"),  nullable=False)
    rating     = db.Column(db.Integer, nullable=False)
    title      = db.Column(db.String(120))
    comment    = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow,  nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,  onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "product_id", name="uq_user_product_review"),
        db.CheckConstraint("rating BETWEEN 1 AND 5", name="chk_rating_range"),
    )

    user    = db.relationship("User",    back_populates="reviews")
    product = db.relationship("Product", back_populates="reviews")

    # ── Helpers ──────────────────────────────────────────────────
    @property
    def rating_label(self):
        return {1: "Poor", 2: "Fair", 3: "Good", 4: "Very Good", 5: "Excellent"}.get(self.rating, "")

    @property
    def was_edited(self):
        return self.updated_at and self.updated_at > self.created_at

    # ── Class-level purchase check ────────────────────────────────
    @staticmethod
    def user_purchased(user_id: int, product_id: int) -> bool:
        """Return True if the user has a delivered order containing this product."""
        from app.models.order import Order, OrderItem, OrderStatus
        return db.session.query(
            db.session.query(OrderItem)
            .join(OrderItem.order)
            .filter(
                Order.user_id  == user_id,
                OrderItem.product_id == product_id,
                Order.status.in_([OrderStatus.delivered, OrderStatus.confirmed,
                                   OrderStatus.shipped,  OrderStatus.processing]),
            )
            .exists()
        ).scalar()

    def __repr__(self):
        return f"<Review user={self.user_id} product={self.product_id} rating={self.rating}>"
