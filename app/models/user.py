from app import db
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import enum

class UserRole(enum.Enum):
    customer = "customer"
    business_owner = "business_owner"
    admin = "admin"

class UserStatus(enum.Enum):
    active = "active"
    suspended = "suspended"
    pending = "pending"

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20), unique=True)
    role = db.Column(db.Enum(UserRole), default=UserRole.customer, nullable=False)
    status = db.Column(db.Enum(UserStatus), default=UserStatus.active, nullable=False)
    profile_image = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    business = db.relationship("Business", back_populates="owner", uselist=False)
    cart = db.relationship("Cart", back_populates="user", uselist=False)
    orders = db.relationship("Order", back_populates="user")
    reviews = db.relationship("Review", back_populates="user")
    browsing_history  = db.relationship("BrowsingHistory",  back_populates="user", cascade="all, delete-orphan")
    recommendations   = db.relationship("Recommendation",   back_populates="user", cascade="all, delete-orphan", foreign_keys="Recommendation.user_id")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):
        return self.status == UserStatus.active

    def has_role(self, *roles):
        return self.role.value in roles

    def __repr__(self):
        return f"<User {self.email}>"
