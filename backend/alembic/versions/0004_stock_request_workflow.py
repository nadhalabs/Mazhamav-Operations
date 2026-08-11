"""Complete stock request fulfilment audit fields

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    uuid = postgresql.UUID(as_uuid=True)
    op.add_column("stock_requests", sa.Column("fulfilled_quantity", sa.Numeric(14, 3), nullable=True))
    op.add_column("stock_requests", sa.Column("fulfilled_by", uuid, nullable=True))
    op.add_column("stock_requests", sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("stock_requests", sa.Column("review_notes", sa.Text(), nullable=True))
    op.create_foreign_key("fk_stock_requests_fulfilled_by_users", "stock_requests", "users", ["fulfilled_by"], ["id"], ondelete="RESTRICT")
    op.create_check_constraint("ck_stock_request_fulfilled_quantity_positive", "stock_requests", "fulfilled_quantity IS NULL OR fulfilled_quantity > 0")
    op.create_index("uq_open_stock_request_staff_product", "stock_requests", ["staff_id", "product_id"], unique=True, postgresql_where=sa.text("status IN ('pending', 'approved')"))


def downgrade():
    op.drop_index("uq_open_stock_request_staff_product", table_name="stock_requests")
    op.drop_constraint("ck_stock_request_fulfilled_quantity_positive", "stock_requests", type_="check")
    op.drop_constraint("fk_stock_requests_fulfilled_by_users", "stock_requests", type_="foreignkey")
    op.drop_column("stock_requests", "fulfilled_at")
    op.drop_column("stock_requests", "fulfilled_by")
    op.drop_column("stock_requests", "fulfilled_quantity")
    op.drop_column("stock_requests", "review_notes")
