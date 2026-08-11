"""Reporting query indexes

Revision ID: 0005
Revises: 0004
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_stock_movements_created_at", "stock_movements", ["created_at"])
    op.create_index("ix_stock_movements_product_created", "stock_movements", ["product_id", "created_at"])
    op.create_index("ix_stock_movements_staff_product_type", "stock_movements", ["staff_id", "product_id", "movement_type"])
    op.create_index("ix_stock_requests_status_requested", "stock_requests", ["status", "requested_at"])
    op.create_index("ix_sales_date_payment", "sales", ["sale_date", "payment_status"])
    op.create_index("ix_sales_staff_date", "sales", ["staff_id", "sale_date"])
    op.create_index("ix_retailers_area", "retailers", ["area"])
    op.create_index("ix_retailers_district", "retailers", ["district"])


def downgrade():
    for name, table in (("ix_retailers_district", "retailers"), ("ix_retailers_area", "retailers"), ("ix_sales_staff_date", "sales"), ("ix_sales_date_payment", "sales"), ("ix_stock_requests_status_requested", "stock_requests"), ("ix_stock_movements_staff_product_type", "stock_movements"), ("ix_stock_movements_product_created", "stock_movements"), ("ix_stock_movements_created_at", "stock_movements")):
        op.drop_index(name, table_name=table)

