import os
import uuid
from flask import current_app
from werkzeug.utils import secure_filename


def _allowed(filename, extensions):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in extensions


def save_image(file, subfolder):
    """Validate and save an uploaded image. Returns the saved filename or None."""
    if not file or not file.filename:
        return None
    allowed = current_app.config.get("ALLOWED_IMAGE_EXTENSIONS", {"png", "jpg", "jpeg", "webp"})
    if not _allowed(file.filename, allowed):
        return None
    return _write(file, subfolder)


def save_document(file, subfolder):
    """Validate and save a verification document (image or PDF). Returns (filename, original_name) or (None, None)."""
    if not file or not file.filename:
        return None, None
    allowed = current_app.config.get("ALLOWED_DOC_EXTENSIONS", {"png", "jpg", "jpeg", "webp", "pdf"})
    if not _allowed(file.filename, allowed):
        return None, None
    original = secure_filename(file.filename)
    filename = _write(file, subfolder)
    return filename, original


def _write(file, subfolder):
    ext      = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    dest     = os.path.join(current_app.config["UPLOAD_FOLDER"], subfolder)
    os.makedirs(dest, exist_ok=True)
    file.save(os.path.join(dest, filename))
    return filename


def delete_image(filename, subfolder):
    if not filename:
        return
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], subfolder, filename)
    if os.path.exists(path):
        os.remove(path)
