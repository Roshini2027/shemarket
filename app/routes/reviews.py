from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.review import Review
from app.models.product import Product, ProductStatus

reviews_bp = Blueprint("reviews", __name__)


def _json_err(msg, code=400):
    return jsonify({"ok": False, "msg": msg}), code


def _validate(rating_raw, title_raw, comment_raw):
    errors = []
    try:
        rating = int(rating_raw)
        if not (1 <= rating <= 5):
            raise ValueError
    except (TypeError, ValueError):
        rating = None
        errors.append("Rating must be between 1 and 5.")

    title   = (title_raw   or "").strip()[:120]
    comment = (comment_raw or "").strip()

    if comment and len(comment) < 10:
        errors.append("Review text must be at least 10 characters.")
    if len(comment) > 2000:
        errors.append("Review text must be 2000 characters or fewer.")

    return rating, title, comment, errors


# ── Submit / create ───────────────────────────────────────────────────────────
@reviews_bp.route("/product/<int:product_id>", methods=["POST"])
@login_required
def submit(product_id):
    product = Product.query.get_or_404(product_id)
    if product.status != ProductStatus.active:
        return _json_err("Product not available.")

    # One review per user per product
    existing = Review.query.filter_by(
        user_id=current_user.id, product_id=product_id
    ).first()
    if existing:
        return _json_err("You have already reviewed this product.")

    # Purchase gate
    if not Review.user_purchased(current_user.id, product_id):
        return _json_err("You can only review products you have purchased.")

    data   = request.get_json(silent=True) or {}
    rating, title, comment, errors = _validate(
        data.get("rating"), data.get("title"), data.get("comment")
    )
    if errors:
        return _json_err(" ".join(errors))

    review = Review(
        user_id    = current_user.id,
        product_id = product_id,
        rating     = rating,
        title      = title or None,
        comment    = comment or None,
    )
    db.session.add(review)
    db.session.commit()

    return jsonify({
        "ok":         True,
        "msg":        "Your review has been posted.",
        "review":     _serialise(review),
        "avg_rating": _avg(product_id),
        "count":      Review.query.filter_by(product_id=product_id).count(),
    })


# ── Edit ──────────────────────────────────────────────────────────────────────
@reviews_bp.route("/<int:review_id>", methods=["PUT"])
@login_required
def edit(review_id):
    review = Review.query.get_or_404(review_id)
    if review.user_id != current_user.id:
        return _json_err("Forbidden.", 403)

    data   = request.get_json(silent=True) or {}
    rating, title, comment, errors = _validate(
        data.get("rating"), data.get("title"), data.get("comment")
    )
    if errors:
        return _json_err(" ".join(errors))

    review.rating     = rating
    review.title      = title or None
    review.comment    = comment or None
    review.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "ok":         True,
        "msg":        "Your review has been updated.",
        "review":     _serialise(review),
        "avg_rating": _avg(review.product_id),
    })


# ── Delete ────────────────────────────────────────────────────────────────────
@reviews_bp.route("/<int:review_id>", methods=["DELETE"])
@login_required
def delete(review_id):
    review = Review.query.get_or_404(review_id)
    if review.user_id != current_user.id:
        return _json_err("Forbidden.", 403)

    product_id = review.product_id
    db.session.delete(review)
    db.session.commit()

    return jsonify({
        "ok":         True,
        "msg":        "Your review has been deleted.",
        "avg_rating": _avg(product_id),
        "count":      Review.query.filter_by(product_id=product_id).count(),
    })


# ── Helpers ───────────────────────────────────────────────────────────────────
def _avg(product_id):
    from sqlalchemy import func
    val = db.session.query(func.avg(Review.rating)).filter_by(product_id=product_id).scalar()
    return round(float(val), 1) if val else 0.0


def _serialise(r: Review) -> dict:
    return {
        "id":          r.id,
        "rating":      r.rating,
        "rating_label": r.rating_label,
        "title":       r.title or "",
        "comment":     r.comment or "",
        "author":      r.user.full_name,
        "created_at":  r.created_at.strftime("%d %b %Y"),
        "was_edited":  r.was_edited,
    }
