from app import db
from datetime import datetime
import enum


class RecommendationType(enum.Enum):
    similar        = "similar"       # same-category products
    trending       = "trending"      # high order/review velocity
    women_owned    = "women_owned"   # verified business boost


class BrowsingHistory(db.Model):
    """One row per user × product view. view_count accumulates repeat visits."""
    __tablename__ = "browsing_history"

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id",    ondelete="CASCADE"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    view_count = db.Column(db.Integer, default=1, nullable=False)
    last_viewed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "product_id", name="uq_browse_user_product"),
    )

    user    = db.relationship("User",    back_populates="browsing_history")
    product = db.relationship("Product", back_populates="browsing_history")

    def __repr__(self):
        return f"<BrowsingHistory user={self.user_id} product={self.product_id} views={self.view_count}>"


class Recommendation(db.Model):
    """
    Cached recommendation rows, refreshed on each homepage/product-detail load.
    For anonymous users user_id is NULL (global trending / women-owned picks).
    """
    __tablename__ = "recommendations"

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True,  index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    rec_type   = db.Column(db.Enum(RecommendationType), nullable=False, index=True)
    score      = db.Column(db.Float, default=0.0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user    = db.relationship("User",    back_populates="recommendations", foreign_keys=[user_id])
    product = db.relationship("Product", back_populates="recommendations")

    def __repr__(self):
        return f"<Recommendation user={self.user_id} product={self.product_id} type={self.rec_type.value} score={self.score:.2f}>"
