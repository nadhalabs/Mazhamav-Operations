"""Central payment settings and payment receipt audit

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table("payment_settings",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("singleton_key", sa.Integer(), server_default="1", nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("upi_id", sa.String(160)),
        sa.Column("bank_reference", sa.Text()),
        sa.Column("qr_storage_key", sa.String(500)),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("updated_by", uuid, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("singleton_key = 1", name="ck_payment_settings_singleton"),
        sa.UniqueConstraint("singleton_key"),
    )
    op.add_column("sales", sa.Column("payment_received_by", uuid, nullable=True))
    op.add_column("sales", sa.Column("payment_received_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_sales_payment_received_by_users", "sales", "users", ["payment_received_by"], ["id"], ondelete="RESTRICT")


def downgrade():
    op.drop_constraint("fk_sales_payment_received_by_users", "sales", type_="foreignkey")
    op.drop_column("sales", "payment_received_at")
    op.drop_column("sales", "payment_received_by")
    op.drop_table("payment_settings")
