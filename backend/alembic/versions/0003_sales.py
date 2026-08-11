"""Retail sales and line items

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

payment_status = postgresql.ENUM("paid", "pending", name="payment_status", create_type=False)
payment_method = postgresql.ENUM("cash", "upi", "bank_transfer", "credit", "other", name="payment_method", create_type=False)


def upgrade():
    bind = op.get_bind()
    payment_status.create(bind, checkfirst=True)
    payment_method.create(bind, checkfirst=True)
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table("sales",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("sale_number", sa.String(40), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("staff_id", uuid, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("retailer_id", uuid, sa.ForeignKey("retailers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sale_date", sa.Date(), server_default=sa.func.current_date(), nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.Column("payment_status", payment_status, nullable=False),
        sa.Column("payment_method", payment_method),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("subtotal >= 0", name="ck_sales_subtotal_nonnegative"),
        sa.CheckConstraint("total >= 0", name="ck_sales_total_nonnegative"),
        sa.UniqueConstraint("sale_number"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_sales_sale_number", "sales", ["sale_number"])
    op.create_index("ix_sales_staff_id", "sales", ["staff_id"])
    op.create_index("ix_sales_retailer_id", "sales", ["retailer_id"])
    op.create_index("ix_sales_sale_date", "sales", ["sale_date"])
    op.create_index("ix_sales_payment_status", "sales", ["payment_status"])
    op.create_table("sale_items",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("sale_id", uuid, sa.ForeignKey("sales.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("product_id", uuid, sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_price_snapshot", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_sale_items_quantity_positive"),
        sa.CheckConstraint("unit_price_snapshot >= 0", name="ck_sale_items_price_nonnegative"),
        sa.UniqueConstraint("sale_id", "product_id", name="uq_sale_item_product"),
    )
    op.create_index("ix_sale_items_sale_id", "sale_items", ["sale_id"])
    op.create_index("ix_sale_items_product_id", "sale_items", ["product_id"])


def downgrade():
    op.drop_table("sale_items")
    op.drop_table("sales")
    payment_method.drop(op.get_bind(), checkfirst=True)
    payment_status.drop(op.get_bind(), checkfirst=True)
