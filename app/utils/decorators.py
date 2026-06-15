from functools import wraps
from flask import abort
from flask_login import current_user


def role_required(*roles):
    """Restricts a view to users with one of the given roles.

    Usage:
        @role_required("admin")
        @role_required("seller", "admin")
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if not current_user.has_role(*roles):
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator
