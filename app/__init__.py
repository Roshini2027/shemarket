from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"

def create_app():
    flask_app = Flask(__name__)
    flask_app.config.from_object(Config)

    db.init_app(flask_app)
    migrate.init_app(flask_app, db)
    login_manager.init_app(flask_app)

    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.seller import seller_bp
    from app.routes.admin import admin_bp
    from app.routes.products import products_bp
    from app.routes.cart import cart_bp
    from app.routes.checkout import checkout_bp
    from app.routes.payment import payment_bp
    from app.routes.orders import orders_bp
    from app.routes.reviews import reviews_bp
    from app.routes.recommendations import rec_bp
    from app.routes.dashboard import dashboard_bp
    flask_app.register_blueprint(main_bp)
    flask_app.register_blueprint(auth_bp,           url_prefix="/auth")
    flask_app.register_blueprint(seller_bp,         url_prefix="/seller")
    flask_app.register_blueprint(admin_bp,          url_prefix="/admin")
    flask_app.register_blueprint(products_bp,       url_prefix="/seller/products")
    flask_app.register_blueprint(cart_bp,           url_prefix="/cart")
    flask_app.register_blueprint(checkout_bp,       url_prefix="/checkout")
    flask_app.register_blueprint(payment_bp,        url_prefix="/payment")
    flask_app.register_blueprint(orders_bp,         url_prefix="/orders")
    flask_app.register_blueprint(reviews_bp,        url_prefix="/reviews")
    flask_app.register_blueprint(rec_bp,            url_prefix="/recommendations")
    flask_app.register_blueprint(dashboard_bp,      url_prefix="/dashboard")

    with flask_app.app_context():
        import app.models  # noqa: F401

        from app.models.user import User

        @login_manager.user_loader
        def load_user(user_id):
            return User.query.get(int(user_id))

        @flask_app.context_processor
        def inject_cart_count():
            from flask_login import current_user
            count = 0
            if current_user.is_authenticated and current_user.cart:
                count = sum(i.quantity for i in current_user.cart.items)
            return {"cart_count": count}

        from app.models.order import _STATUS_META

        @flask_app.template_filter("status_meta")
        def status_meta_filter(value):
            """Return (color, icon, label) for an OrderStatus string value."""
            return _STATUS_META.get(value, ("secondary", "bi-circle", value.title()))

    return flask_app
