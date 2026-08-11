"""Add retailer city/town for territory reporting

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("retailers", sa.Column("city", sa.String(120), nullable=True))
    op.create_index("ix_retailers_city", "retailers", ["city"])


def downgrade():
    op.drop_index("ix_retailers_city", table_name="retailers")
    op.drop_column("retailers", "city")
