from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from app import db
from app.services.recommendation_service import record_view

rec_bp = Blueprint("recommendations", __name__)


@rec_bp.route("/view/<int:product_id>", methods=["POST"])
@login_required
def track_view(product_id):
    record_view(current_user.id, product_id)
    db.session.commit()
    return jsonify({"ok": True})
