"""Add stock movement idempotency key

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("stock_movements", sa.Column("idempotency_key", sa.String(128), nullable=True))
    op.create_unique_constraint("uq_stock_movements_idempotency_key", "stock_movements", ["idempotency_key"])


def downgrade():
    op.drop_constraint("uq_stock_movements_idempotency_key", "stock_movements", type_="unique")
    op.drop_column("stock_movements", "idempotency_key")

