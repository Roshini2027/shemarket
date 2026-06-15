"""reviews module: add title/updated_at to reviews, processing to orderstatus, order_number/notes to orders

Revision ID: a1b2c3d4e5f6
Revises: 7816ba616d6c
Create Date: 2026-06-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = 'a1b2c3d4e5f6'
down_revision = '7816ba616d6c'
branch_labels = None
depends_on = None


def upgrade():
    # ── reviews: add title + updated_at ──────────────────────────
    with op.batch_alter_table('reviews', schema=None) as batch_op:
        batch_op.add_column(sa.Column('title',      sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(),         nullable=True))

    # ── orders: add order_number + notes (exist in model, missing from initial migration) ──
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('order_number', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('notes',        sa.Text(),            nullable=True))
        batch_op.create_index('ix_orders_order_number', ['order_number'], unique=True)

    # ── orderstatus enum: add 'processing' value ─────────────────
    # MySQL requires ALTER TABLE to extend an ENUM; SQLAlchemy/Alembic
    # doesn't auto-generate this, so we do it with a raw SQL statement.
    op.execute(
        "ALTER TABLE orders MODIFY COLUMN status "
        "ENUM('pending','confirmed','processing','shipped','delivered','cancelled','refunded') "
        "NOT NULL"
    )


def downgrade():
    op.execute(
        "ALTER TABLE orders MODIFY COLUMN status "
        "ENUM('pending','confirmed','shipped','delivered','cancelled','refunded') "
        "NOT NULL"
    )

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_index('ix_orders_order_number')
        batch_op.drop_column('notes')
        batch_op.drop_column('order_number')

    with op.batch_alter_table('reviews', schema=None) as batch_op:
        batch_op.drop_column('updated_at')
        batch_op.drop_column('title')
