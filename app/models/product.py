from app import db
from datetime import datetime
import enum


class ProductStatus(enum.Enum):
    active       = "active"
    inactive     = "inactive"
    out_of_stock = "out_of_stock"


PRODUCT_CATEGORIES = [
    "Fashion & Apparel", "Beauty & Wellness", "Food & Beverages",
    "Health & Fitness", "Home & Decor", "Crafts & Handmade",
    "Technology", "Education & Coaching", "Professional Services", "Other",
]


class Product(db.Model):
    __tablename__ = "products"

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    name        = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price       = db.Column(db.Numeric(10, 2), nullable=False)
    stock_qty   = db.Column(db.Integer, default=0, nullable=False)
    category    = db.Column(db.String(100))
    status      = db.Column(db.Enum(ProductStatus), default=ProductStatus.active, nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    business    = db.relationship("Business", back_populates="products")
    images      = db.relationship(
        "ProductImage", back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductImage.sort_order, ProductImage.uploaded_at"
    )
    cart_items  = db.relationship("CartItem",  back_populates="product")
    order_items = db.relationship("OrderItem", back_populates="product")
    reviews     = db.relationship("Review",    back_populates="product")
    browsing_history = db.relationship("BrowsingHistory", back_populates="product", cascade="all, delete-orphan")
    recommendations  = db.relationship("Recommendation",  back_populates="product", cascade="all, delete-orphan")

    @property
    def primary_image_url(self):
        primary = next((img for img in self.images if img.is_primary), None)
        if not primary and self.images:
            primary = self.images[0]
        return f"/static/uploads/products/{primary.image_url}" if primary else "/static/img/default_product.png"

    @property
    def status_badge(self):
        return {
            ProductStatus.active:       ("success",   "Active"),
            ProductStatus.inactive:     ("secondary", "Inactive"),
            ProductStatus.out_of_stock: ("warning",   "Out of Stock"),
        }.get(self.status, ("secondary", self.status.value))

    @property
    def is_in_stock(self):
        return self.stock_qty > 0 and self.status == ProductStatus.active

    def __repr__(self):
        return f"<Product {self.name}>"


class ProductImage(db.Model):
    __tablename__ = "product_images"

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_id  = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    image_url   = db.Column(db.String(255), nullable=False)
    is_primary  = db.Column(db.Boolean, default=False, nullable=False)
    sort_order  = db.Column(db.Integer, default=0, nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    product = db.relationship("Product", back_populates="images")

    @property
    def url(self):
        return f"/static/uploads/products/{self.image_url}"

    def __repr__(self):
        return f"<ProductImage product_id={self.product_id} primary={self.is_primary}>"
