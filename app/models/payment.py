from app import db
from datetime import datetime
import enum


class PaymentStatus(enum.Enum):
    pending   = "pending"
    completed = "completed"
    failed    = "failed"
    refunded  = "refunded"


class PaymentMethod(enum.Enum):
    credit_card  = "credit_card"
    debit_card   = "debit_card"
    upi          = "upi"
    net_banking  = "net_banking"
    wallet       = "wallet"
    # legacy / kept for existing rows
    card             = "card"
    mobile_money     = "mobile_money"
    bank_transfer    = "bank_transfer"
    cash_on_delivery = "cash_on_delivery"


class Payment(db.Model):
    __tablename__ = "payments"

    id             = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_id       = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="RESTRICT"),
                               nullable=False, unique=True)
    amount         = db.Column(db.Numeric(10, 2), nullable=False)
    method         = db.Column(db.Enum(PaymentMethod), nullable=False)
    status         = db.Column(db.Enum(PaymentStatus), default=PaymentStatus.pending, nullable=False)
    # human-readable TXN-prefixed ID  e.g. TXN123456
    transaction_ref = db.Column(db.String(100), unique=True)
    paid_at        = db.Column(db.DateTime)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    order = db.relationship("Order", back_populates="payment")

    # ── convenience aliases used in templates ────────────────────
    @property
    def transaction_id(self):
        return self.transaction_ref

    @property
    def payment_date(self):
        return self.paid_at or self.created_at

    @property
    def payment_status(self):
        return self.status

    @property
    def payment_method(self):
        return self.method

    @property
    def method_label(self):
        return {
            PaymentMethod.credit_card:     "Credit Card",
            PaymentMethod.debit_card:      "Debit Card",
            PaymentMethod.upi:             "UPI",
            PaymentMethod.net_banking:     "Net Banking",
            PaymentMethod.wallet:          "Wallet",
            PaymentMethod.card:            "Card",
            PaymentMethod.mobile_money:    "Mobile Money",
            PaymentMethod.bank_transfer:   "Bank Transfer",
            PaymentMethod.cash_on_delivery:"Cash on Delivery",
        }.get(self.method, self.method.value.replace("_", " ").title())

    @property
    def status_badge(self):
        return {
            PaymentStatus.pending:   ("warning",   "bi-clock-fill",        "Pending"),
            PaymentStatus.completed: ("success",   "bi-check-circle-fill", "Paid"),
            PaymentStatus.failed:    ("danger",    "bi-x-circle-fill",     "Failed"),
            PaymentStatus.refunded:  ("info",      "bi-arrow-counterclockwise", "Refunded"),
        }.get(self.status, ("secondary", "bi-circle", self.status.value.title()))

    def __repr__(self):
        return f"<Payment order_id={self.order_id} status={self.status.value}>"
