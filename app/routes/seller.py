from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models.business import Business, BusinessStatus, BUSINESS_CATEGORIES, REQUIRED_DOC_TYPES, DocType, VerificationDocument
from app.models.user import UserRole
from app.utils.decorators import role_required
from app.utils.upload import save_image, delete_image, save_document

seller_bp = Blueprint("seller", __name__)


def _seller_only():
    """Redirect non-sellers away with a message."""
    if current_user.role != UserRole.business_owner:
        flash("Only seller accounts can access this page.", "warning")
        return redirect(url_for("main.index"))
    return None


# ── Register Business ──────────────────────────────────────────────────────────

@seller_bp.route("/register", methods=["GET", "POST"])
@login_required
def register_business():
    guard = _seller_only()
    if guard:
        return guard

    if current_user.business:
        return redirect(url_for("seller.dashboard"))

    if request.method == "POST":
        name            = request.form.get("name", "").strip()
        category        = request.form.get("category", "").strip()
        description     = request.form.get("description", "").strip()
        contact_phone   = request.form.get("contact_phone", "").strip() or None
        contact_email   = request.form.get("contact_email", "").strip().lower() or None
        address         = request.form.get("address", "").strip() or None
        logo_file       = request.files.get("logo")

        # Server-side validation
        errors = []
        if not name:
            errors.append("Business name is required.")
        if len(name) > 150:
            errors.append("Business name must be 150 characters or fewer.")
        if not category:
            errors.append("Please select a category.")
        if not description or len(description) < 20:
            errors.append("Description must be at least 20 characters.")
        if not contact_phone and not contact_email:
            errors.append("Provide at least one contact method (phone or email).")

        logo_filename = None
        if logo_file and logo_file.filename:
            logo_filename = save_image(logo_file, "logos")
            if logo_filename is None:
                errors.append("Logo must be a PNG, JPG, JPEG or WEBP image under 5 MB.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("seller/register_business.html",
                                   categories=BUSINESS_CATEGORIES,
                                   form_data=request.form)

        business = Business(
            owner_id      = current_user.id,
            name          = name,
            category      = category,
            description   = description,
            contact_phone = contact_phone,
            contact_email = contact_email,
            address       = address,
            logo          = logo_filename,
            status        = BusinessStatus.pending_verification,
        )
        db.session.add(business)
        db.session.commit()

        flash("Business registered! Our team will verify it within 2–3 business days.", "success")
        return redirect(url_for("seller.dashboard"))

    return render_template("seller/register_business.html",
                           categories=BUSINESS_CATEGORIES,
                           form_data={})


# ── Upload Verification Documents ─────────────────────────────────────────────

@seller_bp.route("/documents", methods=["GET", "POST"])
@login_required
def upload_documents():
    guard = _seller_only()
    if guard:
        return guard

    business = current_user.business
    if not business:
        return redirect(url_for("seller.register_business"))

    if request.method == "POST":
        uploaded_any = False
        errors = []

        for doc_type, label, _ in REQUIRED_DOC_TYPES:
            file = request.files.get(doc_type.value)
            if not file or not file.filename:
                continue

            filename, original = save_document(file, "documents")
            if filename is None:
                errors.append(f"{label}: must be PDF, PNG, JPG or WEBP under 10 MB.")
                continue

            # Replace existing doc of same type
            existing = next((d for d in business.verification_documents if d.doc_type == doc_type), None)
            if existing:
                delete_image(existing.file_url, "documents")
                existing.file_url          = filename
                existing.original_filename = original
                existing.doc_status        = __import__("app.models.business", fromlist=["DocStatus"]).DocStatus.pending
                existing.rejection_comment = None
                existing.reviewed_by       = None
                existing.reviewed_at       = None
                from datetime import datetime
                existing.uploaded_at       = datetime.utcnow()
            else:
                doc = VerificationDocument(
                    business_id       = business.id,
                    doc_type          = doc_type,
                    file_url          = filename,
                    original_filename = original,
                )
                db.session.add(doc)
            uploaded_any = True

        if errors:
            for e in errors:
                flash(e, "danger")

        if uploaded_any:
            # Reset business to pending_verification when new docs are submitted
            if business.status == BusinessStatus.rejected:
                business.status = BusinessStatus.pending_verification
                business.rejection_comment = None
            db.session.commit()
            flash("Documents uploaded successfully. Admin will review them shortly.", "success")

        return redirect(url_for("seller.upload_documents"))

    uploaded_types = business.uploaded_doc_types()
    docs_map = {d.doc_type: d for d in business.verification_documents}
    return render_template(
        "seller/upload_documents.html",
        business       = business,
        required_docs  = REQUIRED_DOC_TYPES,
        uploaded_types = uploaded_types,
        docs_map       = docs_map,
    )



@seller_bp.route("/dashboard")
@login_required
def dashboard():
    guard = _seller_only()
    if guard:
        return guard

    if not current_user.business:
        return redirect(url_for("seller.register_business"))

    return render_template("seller/dashboard.html", business=current_user.business)


# ── Edit Business ──────────────────────────────────────────────────────────────

@seller_bp.route("/edit", methods=["GET", "POST"])
@login_required
def edit_business():
    guard = _seller_only()
    if guard:
        return guard

    business = current_user.business
    if not business:
        return redirect(url_for("seller.register_business"))

    if request.method == "POST":
        business.name          = request.form.get("name", "").strip() or business.name
        business.category      = request.form.get("category", "").strip() or business.category
        business.description   = request.form.get("description", "").strip() or business.description
        business.contact_phone = request.form.get("contact_phone", "").strip() or business.contact_phone
        business.contact_email = request.form.get("contact_email", "").strip().lower() or business.contact_email
        business.address       = request.form.get("address", "").strip() or business.address

        logo_file = request.files.get("logo")
        if logo_file and logo_file.filename:
            new_logo = save_image(logo_file, "logos")
            if new_logo:
                delete_image(business.logo, "logos")
                business.logo = new_logo
            else:
                flash("Invalid logo file. Must be PNG, JPG, JPEG or WEBP under 5 MB.", "danger")
                return render_template("seller/register_business.html",
                                       categories=BUSINESS_CATEGORIES,
                                       form_data=request.form,
                                       business=business,
                                       edit_mode=True)

        db.session.commit()
        flash("Business details updated.", "success")
        return redirect(url_for("seller.dashboard"))

    return render_template("seller/register_business.html",
                           categories=BUSINESS_CATEGORIES,
                           form_data={},
                           business=business,
                           edit_mode=True)
