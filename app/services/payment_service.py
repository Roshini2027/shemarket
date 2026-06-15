"""
app/services/payment_service.py
Dummy payment gateway — simulates processing for all 5 payment methods.
No real network calls are made; all transactions succeed after basic validation.
"""
import random
import string
from datetime import datetime

from app import db
from app.models.order import Order, OrderStatus
from app.models.payment import Payment, PaymentMethod, PaymentStatus


# ── Transaction ID generator ─────────────────────────────────────────────────
def generate_txn_id() -> str:
    """Return a unique TXN-prefixed 10-digit transaction reference."""
    digits = "".join(random.choices(string.digits, k=10))
    return f"TXN{digits}"


# ── Per-method field validators ───────────────────────────────────────────────
def validate_payment_fields(method: str, form: dict) -> list[str]:
    """Return a list of validation error strings, empty if all valid."""
    errors = []

    if method == "credit_card":
        card_number = form.get("card_number", "").replace(" ", "")
        expiry      = form.get("expiry", "").strip()
        cvv         = form.get("cvv", "").strip()
        name        = form.get("card_name", "").strip()
        if not name:
            errors.append("Cardholder name is required.")
        if len(card_number) != 16 or not card_number.isdigit():
            errors.append("Enter a valid 16-digit card number.")
        if not expiry or len(expiry) < 5:
            errors.append("Enter a valid expiry date (MM/YY).")
        if len(cvv) not in (3, 4) or not cvv.isdigit():
            errors.append("Enter a valid CVV.")

    elif method == "debit_card":
        card_number = form.get("card_number", "").replace(" ", "")
        expiry      = form.get("expiry", "").strip()
        cvv         = form.get("cvv", "").strip()
        name        = form.get("card_name", "").strip()
        pin         = form.get("atm_pin", "").strip()
        if not name:
            errors.append("Cardholder name is required.")
        if len(card_number) != 16 or not card_number.isdigit():
            errors.append("Enter a valid 16-digit card number.")
        if not expiry or len(expiry) < 5:
            errors.append("Enter a valid expiry date (MM/YY).")
        if len(cvv) not in (3, 4) or not cvv.isdigit():
            errors.append("Enter a valid CVV.")
        if len(pin) not in (4, 6) or not pin.isdigit():
            errors.append("Enter your 4 or 6-digit ATM PIN.")

    elif method == "upi":
        upi_id = form.get("upi_id", "").strip()
        if "@" not in upi_id or len(upi_id) < 5:
            errors.append("Enter a valid UPI ID (e.g. name@upi).")

    elif method == "net_banking":
        bank = form.get("bank_code", "").strip()
        uid  = form.get("net_user_id", "").strip()
        pwd  = form.get("net_password", "").strip()
        if not bank:
            errors.append("Please select a bank.")
        if not uid:
            errors.append("Net banking user ID is required.")
        if not pwd:
            errors.append("Net banking password is required.")

    elif method == "wallet":
        mobile = form.get("wallet_mobile", "").replace(" ", "").replace("-", "")
        if len(mobile) < 10 or not mobile.lstrip("+").isdigit():
            errors.append("Enter a valid mobile number for your wallet.")

    return errors


# ── Core processing function ──────────────────────────────────────────────────
def process_payment(order: Order, method_str: str, form: dict) -> tuple[bool, str, "Payment"]:
    """
    Simulate payment processing.

    Returns (success: bool, message: str, payment: Payment)
    On success  → updates payment.status = completed, order.status = confirmed
    On failure  → updates payment.status = failed
    All changes are committed inside this function.
    """
    payment = order.payment
    if not payment:
        return False, "Payment record not found.", None

    # Map form method string to enum
    try:
        method_enum = PaymentMethod(method_str)
    except ValueError:
        method_enum = PaymentMethod.credit_card

    # Validate fields
    errors = validate_payment_fields(method_str, form)
    if errors:
        return False, " ".join(errors), payment

    # Generate unique TXN ID (retry on collision)
    for _ in range(5):
        txn = generate_txn_id()
        if not Payment.query.filter_by(transaction_ref=txn).first():
            break

    # Simulate: always succeeds after validation passes
    payment.method          = method_enum
    payment.status          = PaymentStatus.completed
    payment.transaction_ref = txn
    payment.paid_at         = datetime.utcnow()

    # Update order status
    order.status = OrderStatus.confirmed

    db.session.commit()
    return True, "Payment successful.", payment
