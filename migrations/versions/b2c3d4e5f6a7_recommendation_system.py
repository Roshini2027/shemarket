"""recommendation system: browsing_history and recommendations tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-15 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision     = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on    = None


def upgrade():
    op.create_table(
        'browsing_history',
        sa.Column('id',             sa.Integer(),  autoincrement=True, nullable=False),
        sa.Column('user_id',        sa.Integer(),  nullable=False),
        sa.Column('product_id',     sa.Integer(),  nullable=False),
        sa.Column('view_count',     sa.Integer(),  nullable=False, server_default='1'),
        sa.Column('last_viewed_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'],    ['users.id'],    ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'product_id', name='uq_browse_user_product'),
    )
    op.create_index('ix_browsing_history_user_id',    'browsing_history', ['user_id'])
    op.create_index('ix_browsing_history_product_id', 'browsing_history', ['product_id'])

    op.create_table(
        'recommendations',
        sa.Column('id',         sa.Integer(),                          autoincrement=True, nullable=False),
        sa.Column('user_id',    sa.Integer(),                          nullable=True),
        sa.Column('product_id', sa.Integer(),                          nullable=False),
        sa.Column('rec_type',   sa.Enum('similar', 'trending', 'women_owned', name='recommendationtype'), nullable=False),
        sa.Column('score',      sa.Float(),                            nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(),                         nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'],    ['users.id'],    ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_recommendations_user_id',  'recommendations', ['user_id'])
    op.create_index('ix_recommendations_rec_type', 'recommendations', ['rec_type'])


def downgrade():
    op.drop_index('ix_recommendations_rec_type', table_name='recommendations')
    op.drop_index('ix_recommendations_user_id',  table_name='recommendations')
    op.drop_table('recommendations')

    op.drop_index('ix_browsing_history_product_id', table_name='browsing_history')
    op.drop_index('ix_browsing_history_user_id',    table_name='browsing_history')
    op.drop_table('browsing_history')
