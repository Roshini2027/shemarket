from app import db
from datetime import datetime
import enum


class BusinessStatus(enum.Enum):
    pending_verification = "pending_verification"
    verified             = "verified"
    rejected             = "rejected"
    suspended            = "suspended"


class DocType(enum.Enum):
    government_id             = "government_id"
    ownership_proof           = "ownership_proof"
    business_registration     = "business_registration"


class DocStatus(enum.Enum):
    pending  = "pending"
    approved = "approved"
    rejected = "rejected"


BUSINESS_CATEGORIES = [
    "Fashion & Apparel", "Beauty & Wellness", "Food & Beverages",
    "Health & Fitness", "Home & Decor", "Crafts & Handmade",
    "Technology", "Education & Coaching", "Professional Services", "Other",
]

REQUIRED_DOC_TYPES = [
    (DocType.government_id,         "Government ID",                     "National ID, passport or driver's licence"),
    (DocType.ownership_proof,       "Proof of Women Ownership",          "Statutory declaration or affidavit confirming women-owned status"),
    (DocType.business_registration, "Business Registration Certificate", "Official certificate from relevant authority"),
]


class Business(db.Model):
    __tablename__ = "businesses"

    id                = db.Column(db.Integer, primary_key=True, autoincrement=True)
    owner_id          = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    name              = db.Column(db.String(150), nullable=False)
    description       = db.Column(db.Text)
    category          = db.Column(db.String(100))
    address           = db.Column(db.String(255))
    contact_email     = db.Column(db.String(150))
    contact_phone     = db.Column(db.String(20))
    logo              = db.Column(db.String(255))
    status            = db.Column(db.Enum(BusinessStatus), default=BusinessStatus.pending_verification, nullable=False)
    rejection_comment = db.Column(db.Text)
    verified_at       = db.Column(db.DateTime)
    created_at        = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at        = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner                  = db.relationship("User", back_populates="business")
    verification_documents = db.relationship(
        "VerificationDocument", back_populates="business",
        cascade="all, delete-orphan", order_by="VerificationDocument.uploaded_at"
    )
    products = db.relationship("Product", back_populates="business", cascade="all, delete-orphan")

    @property
    def is_verified(self):
        return self.status == BusinessStatus.verified

    @property
    def logo_url(self):
        if self.logo:
            return f"/static/uploads/logos/{self.logo}"
        return "/static/img/default_logo.png"

    @property
    def status_badge(self):
        return {
            BusinessStatus.pending_verification: ("warning",   "Pending Verification"),
            BusinessStatus.verified:             ("success",   "Verified"),
            BusinessStatus.rejected:             ("danger",    "Rejected"),
            BusinessStatus.suspended:            ("secondary", "Suspended"),
        }.get(self.status, ("secondary", self.status.value))

    def uploaded_doc_types(self):
        return {d.doc_type for d in self.verification_documents}

    def docs_complete(self):
        return {dt for dt, _, _ in REQUIRED_DOC_TYPES}.issubset(self.uploaded_doc_types())

    def __repr__(self):
        return f"<Business {self.name}>"


class VerificationDocument(db.Model):
    __tablename__ = "verification_documents"

    id                = db.Column(db.Integer, primary_key=True, autoincrement=True)
    business_id       = db.Column(db.Integer, db.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    doc_type          = db.Column(db.Enum(DocType), nullable=False)
    file_url          = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255))
    doc_status        = db.Column(db.Enum(DocStatus), default=DocStatus.pending, nullable=False)
    rejection_comment = db.Column(db.Text)
    reviewed_by       = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at       = db.Column(db.DateTime)
    uploaded_at       = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    business = db.relationship("Business", back_populates="verification_documents")
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])

    @property
    def file_path(self):
        return f"/static/uploads/documents/{self.file_url}"

    @property
    def is_image(self):
        return self.file_url.rsplit(".", 1)[-1].lower() in {"png", "jpg", "jpeg", "webp"}

    @property
    def status_badge(self):
        return {
            DocStatus.pending:  ("warning", "Pending"),
            DocStatus.approved: ("success", "Approved"),
            DocStatus.rejected: ("danger",  "Rejected"),
        }.get(self.doc_status, ("secondary", self.doc_status.value))

    def __repr__(self):
        return f"<VerificationDocument {self.doc_type.value} business={self.business_id}>"
