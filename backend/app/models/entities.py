import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class UserRole(str, enum.Enum):
    owner = "owner"
    manager = "manager"
    staff = "staff"


class MovementType(str, enum.Enum):
    warehouse_in = "warehouse_in"
    issued_to_staff = "issued_to_staff"
    staff_sale = "staff_sale"
    staff_return = "staff_return"
    stock_adjustment = "stock_adjustment"


class RequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    fulfilled = "fulfilled"


class PaymentStatus(str, enum.Enum):
    paid = "paid"
    pending = "pending"


class PaymentMethod(str, enum.Enum):
    cash = "cash"
    upi = "upi"
    bank_transfer = "bank_transfer"
    credit = "credit"
    other = "other"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Product(TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (CheckConstraint("selling_price >= 0", name="ck_products_price_nonnegative"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160))
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    unit_name: Mapped[str] = mapped_column(String(40), default="packet")
    selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Retailer(TimestampMixin, Base):
    __tablename__ = "retailers"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    shop_name: Mapped[str] = mapped_column(String(160), index=True)
    contact_name: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(20))
    address: Mapped[str | None] = mapped_column(Text)
    area: Mapped[str | None] = mapped_column(String(120), index=True)
    city: Mapped[str | None] = mapped_column(String(120), index=True)
    district: Mapped[str | None] = mapped_column(String(120), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class StockMovement(Base):
    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint("quantity <> 0", name="ck_stock_movement_quantity_nonzero"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    staff_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    movement_type: Mapped[MovementType] = mapped_column(Enum(MovementType, name="movement_type"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    reference_type: Mapped[str | None] = mapped_column(String(60))
    reference_id: Mapped[uuid.UUID | None]
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    product: Mapped[Product] = relationship()


class StockRequest(Base):
    __tablename__ = "stock_requests"
    __table_args__ = (
        CheckConstraint("requested_quantity > 0", name="ck_stock_request_quantity_positive"),
        CheckConstraint("fulfilled_quantity IS NULL OR fulfilled_quantity > 0", name="ck_stock_request_fulfilled_quantity_positive"),
        Index("uq_open_stock_request_staff_product", "staff_id", "product_id", unique=True, postgresql_where=text("status IN ('pending', 'approved')"), sqlite_where=text("status IN ('pending', 'approved')")),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    requested_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    status: Mapped[RequestStatus] = mapped_column(Enum(RequestStatus, name="request_status"), default=RequestStatus.pending, index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fulfilled_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    fulfilled_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    review_notes: Mapped[str | None] = mapped_column(Text)


class Sale(Base):
    __tablename__ = "sales"
    __table_args__ = (
        CheckConstraint("subtotal >= 0", name="ck_sales_subtotal_nonnegative"),
        CheckConstraint("total >= 0", name="ck_sales_total_nonnegative"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sale_number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    retailer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("retailers.id", ondelete="RESTRICT"), index=True)
    sale_date: Mapped[date] = mapped_column(Date, server_default=func.current_date(), index=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    payment_status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus, name="payment_status"), index=True)
    payment_method: Mapped[PaymentMethod | None] = mapped_column(Enum(PaymentMethod, name="payment_method"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    payment_received_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    payment_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    items: Mapped[list["SaleItem"]] = relationship(back_populates="sale", lazy="selectin")
    staff: Mapped[User] = relationship(foreign_keys=[staff_id])
    retailer: Mapped[Retailer] = relationship()


class SaleItem(Base):
    __tablename__ = "sale_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_sale_items_quantity_positive"),
        CheckConstraint("unit_price_snapshot >= 0", name="ck_sale_items_price_nonnegative"),
        UniqueConstraint("sale_id", "product_id", name="uq_sale_item_product"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sale_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sales.id", ondelete="RESTRICT"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    unit_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    sale: Mapped[Sale] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()


class PaymentSettings(TimestampMixin, Base):
    __tablename__ = "payment_settings"
    __table_args__ = (CheckConstraint("singleton_key = 1", name="ck_payment_settings_singleton"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    singleton_key: Mapped[int] = mapped_column(unique=True, default=1, server_default="1")
    display_name: Mapped[str] = mapped_column(String(160))
    upi_id: Mapped[str | None] = mapped_column(String(160))
    bank_reference: Mapped[str | None] = mapped_column(Text)
    qr_storage_key: Mapped[str | None] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
