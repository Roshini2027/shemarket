from flask import Blueprint, render_template
from flask_login import login_required, current_user
from sqlalchemy import func, extract
from app import db
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product
from app.models.business import Business, BusinessStatus

dashboard_bp = Blueprint("dashboard", __name__)

_COMPLETED = [
    OrderStatus.delivered,
    OrderStatus.shipped,
    OrderStatus.confirmed,
    OrderStatus.processing,
]


@dashboard_bp.route("/impact")
@login_required
def impact():
    uid = current_user.id

    # ── Base join: orders → items → products → businesses ────────────────────
    base = (
        db.session.query(Order, OrderItem, Product, Business)
        .join(OrderItem,  OrderItem.order_id   == Order.id)
        .join(Product,    Product.id           == OrderItem.product_id)
        .join(Business,   Business.id          == Product.business_id)
        .filter(
            Order.user_id == uid,
            Order.status.in_(_COMPLETED),
            Business.status == BusinessStatus.verified,
        )
    )

    # 1 ── Supported businesses count
    supported_count = (
        base.with_entities(Business.id)
        .distinct()
        .count()
    )

    # 2 ── Total amount spent on women-owned businesses
    total_spent = (
        base.with_entities(
            func.sum(OrderItem.unit_price * OrderItem.quantity)
        ).scalar() or 0
    )

    # 3 ── Total completed orders involving women-owned businesses
    total_orders = (
        base.with_entities(Order.id)
        .distinct()
        .count()
    )

    # 4 ── Categories supported (distinct, non-null)
    categories_raw = (
        base.with_entities(Product.category)
        .filter(Product.category.isnot(None))
        .distinct()
        .all()
    )
    categories = sorted({r[0] for r in categories_raw if r[0]})

    _yr = extract("year",  Order.created_at)
    _mo = extract("month", Order.created_at)

    # 5 ── Monthly spending
    monthly_spending = (
        db.session.query(
            _yr.label("yr"),
            _mo.label("mo"),
            func.sum(OrderItem.unit_price * OrderItem.quantity).label("total"),
        )
        .join(OrderItem,  OrderItem.order_id   == Order.id)
        .join(Product,    Product.id           == OrderItem.product_id)
        .join(Business,   Business.id          == Product.business_id)
        .filter(
            Order.user_id == uid,
            Order.status.in_(_COMPLETED),
            Business.status == BusinessStatus.verified,
        )
        .group_by(_yr, _mo)
        .order_by(_yr, _mo)
        .all()
    )

    # 6 ── Orders per month
    monthly_orders = (
        db.session.query(
            _yr.label("yr"),
            _mo.label("mo"),
            func.count(func.distinct(Order.id)).label("cnt"),
        )
        .join(OrderItem,  OrderItem.order_id   == Order.id)
        .join(Product,    Product.id           == OrderItem.product_id)
        .join(Business,   Business.id          == Product.business_id)
        .filter(
            Order.user_id == uid,
            Order.status.in_(_COMPLETED),
            Business.status == BusinessStatus.verified,
        )
        .group_by(_yr, _mo)
        .order_by(_yr, _mo)
        .all()
    )

    # 7 ── Category distribution (spend per category)
    category_spend = (
        db.session.query(
            Product.category,
            func.sum(OrderItem.unit_price * OrderItem.quantity).label("total"),
        )
        .join(OrderItem,  OrderItem.product_id == Product.id)
        .join(Order,      Order.id             == OrderItem.order_id)
        .join(Business,   Business.id          == Product.business_id)
        .filter(
            Order.user_id == uid,
            Order.status.in_(_COMPLETED),
            Business.status == BusinessStatus.verified,
            Product.category.isnot(None),
        )
        .group_by(Product.category)
        .order_by(func.sum(OrderItem.unit_price * OrderItem.quantity).desc())
        .all()
    )

    # 8 ── Top supported businesses (spend + order count)
    top_businesses = (
        db.session.query(
            Business,
            func.sum(OrderItem.unit_price * OrderItem.quantity).label("spent"),
            func.count(func.distinct(Order.id)).label("order_cnt"),
        )
        .join(Product,    Product.business_id  == Business.id)
        .join(OrderItem,  OrderItem.product_id == Product.id)
        .join(Order,      Order.id             == OrderItem.order_id)
        .filter(
            Order.user_id == uid,
            Order.status.in_(_COMPLETED),
            Business.status == BusinessStatus.verified,
        )
        .group_by(Business.id)
        .order_by(func.sum(OrderItem.unit_price * OrderItem.quantity).desc())
        .limit(5)
        .all()
    )

    # ── Format chart data ─────────────────────────────────────────────────────
    MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun",
                   "Jul","Aug","Sep","Oct","Nov","Dec"]

    def _build_monthly(rows, value_key):
        """Return parallel label + value lists covering all months present."""
        data = {(int(r.yr), int(r.mo)): float(getattr(r, value_key)) for r in rows}
        if not data:
            return [], []
        keys = sorted(data)
        labels = [f"{MONTH_NAMES[mo-1]} {yr}" for yr, mo in keys]
        values = [round(data[k], 2) for k in keys]
        return labels, values

    spend_labels, spend_values       = _build_monthly(monthly_spending, "total")
    orders_labels, orders_values     = _build_monthly(monthly_orders,   "cnt")

    cat_labels  = [r[0] for r in category_spend]
    cat_values  = [round(float(r[1]), 2) for r in category_spend]

    return render_template(
        "dashboard/impact.html",
        supported_count  = supported_count,
        total_spent      = round(float(total_spent), 2),
        total_orders     = total_orders,
        categories       = categories,
        top_businesses   = top_businesses,
        spend_labels     = spend_labels,
        spend_values     = spend_values,
        orders_labels    = orders_labels,
        orders_values    = orders_values,
        cat_labels       = cat_labels,
        cat_values       = cat_values,
    )
