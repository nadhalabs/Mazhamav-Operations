"""Phase 1 core schema

Revision ID: 0001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

user_role = postgresql.ENUM("owner", "manager", "staff", name="user_role", create_type=False)
movement_type = postgresql.ENUM("warehouse_in", "issued_to_staff", "staff_sale", "staff_return", "stock_adjustment", name="movement_type", create_type=False)
request_status = postgresql.ENUM("pending", "approved", "rejected", "fulfilled", name="request_status", create_type=False)


def upgrade():
    bind = op.get_bind()
    user_role.create(bind, checkfirst=True)
    movement_type.create(bind, checkfirst=True)
    request_status.create(bind, checkfirst=True)
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table("users", sa.Column("id", uuid, primary_key=True), sa.Column("full_name", sa.String(120), nullable=False), sa.Column("phone", sa.String(20), nullable=False), sa.Column("email", sa.String(255)), sa.Column("password_hash", sa.String(255), nullable=False), sa.Column("role", user_role, nullable=False), sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("phone"), sa.UniqueConstraint("email"))
    op.create_index("ix_users_phone", "users", ["phone"])
    op.create_index("ix_users_role", "users", ["role"])
    op.create_table("products", sa.Column("id", uuid, primary_key=True), sa.Column("name", sa.String(160), nullable=False), sa.Column("sku", sa.String(64), nullable=False), sa.Column("unit_name", sa.String(40), nullable=False), sa.Column("selling_price", sa.Numeric(12, 2), nullable=False), sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.CheckConstraint("selling_price >= 0", name="ck_products_price_nonnegative"), sa.UniqueConstraint("sku"))
    op.create_index("ix_products_sku", "products", ["sku"])
    op.create_table("retailers", sa.Column("id", uuid, primary_key=True), sa.Column("shop_name", sa.String(160), nullable=False), sa.Column("contact_name", sa.String(120)), sa.Column("phone", sa.String(20)), sa.Column("address", sa.Text()), sa.Column("area", sa.String(120)), sa.Column("district", sa.String(120)), sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("stock_movements", sa.Column("id", uuid, primary_key=True), sa.Column("product_id", uuid, sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False), sa.Column("staff_id", uuid, sa.ForeignKey("users.id", ondelete="RESTRICT")), sa.Column("movement_type", movement_type, nullable=False), sa.Column("quantity", sa.Numeric(14, 3), nullable=False), sa.Column("reference_type", sa.String(60)), sa.Column("reference_id", uuid), sa.Column("notes", sa.Text()), sa.Column("created_by", uuid, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.CheckConstraint("quantity <> 0", name="ck_stock_movement_quantity_nonzero"))
    op.create_table("stock_requests", sa.Column("id", uuid, primary_key=True), sa.Column("staff_id", uuid, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("product_id", uuid, sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False), sa.Column("requested_quantity", sa.Numeric(14, 3), nullable=False), sa.Column("status", request_status, server_default="pending", nullable=False), sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("reviewed_by", uuid, sa.ForeignKey("users.id", ondelete="RESTRICT")), sa.Column("reviewed_at", sa.DateTime(timezone=True)), sa.Column("notes", sa.Text()), sa.CheckConstraint("requested_quantity > 0", name="ck_stock_request_quantity_positive"))
    op.execute("""CREATE FUNCTION prevent_stock_movement_mutation() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'stock movements are immutable; post a compensating movement'; END; $$ LANGUAGE plpgsql""")
    op.execute("CREATE TRIGGER stock_movements_no_update_delete BEFORE UPDATE OR DELETE ON stock_movements FOR EACH ROW EXECUTE FUNCTION prevent_stock_movement_mutation()")


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS stock_movements_no_update_delete ON stock_movements")
    op.execute("DROP FUNCTION IF EXISTS prevent_stock_movement_mutation")
    for table in ("stock_requests", "stock_movements", "retailers", "products", "users"):
        op.drop_table(table)
    request_status.drop(op.get_bind(), checkfirst=True)
    movement_type.drop(op.get_bind(), checkfirst=True)
    user_role.drop(op.get_bind(), checkfirst=True)

