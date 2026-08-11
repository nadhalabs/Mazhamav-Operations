import uuid
import hashlib
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.time import business_today
from app.models import MovementType, Product, Retailer, Sale, SaleItem, StockMovement, User, UserRole
from app.schemas.sales import SaleCreate
from app.services.inventory import staff_balance

MONEY = Decimal("0.01")


def create_sale(db: Session, actor: User, payload: SaleCreate) -> Sale:
    if actor.role != UserRole.staff:
        raise HTTPException(403, "Only staff accounts can record sales")
    existing = db.scalar(select(Sale).where(Sale.idempotency_key == payload.idempotency_key))
    if existing:
        return existing

    product_ids = sorted((item.product_id for item in payload.items), key=str)
    products = db.scalars(select(Product).where(Product.id.in_(product_ids), Product.active.is_(True)).order_by(Product.id).with_for_update()).all()
    product_map = {product.id: product for product in products}
    if len(product_map) != len(product_ids):
        raise HTTPException(422, "One or more products are inactive or unavailable")

    # Recheck after locks: another request with the same key may have committed while we waited.
    existing = db.scalar(select(Sale).where(Sale.idempotency_key == payload.idempotency_key))
    if existing:
        return existing

    for item in payload.items:
        available = staff_balance(db, actor.id, item.product_id)
        if available < item.quantity:
            raise HTTPException(409, f"Insufficient stock for {product_map[item.product_id].name}; available balance is {available}")

    if payload.retailer_id:
        retailer = db.scalar(select(Retailer).where(Retailer.id == payload.retailer_id, Retailer.active.is_(True)))
        if not retailer:
            raise HTTPException(422, "Active retailer not found")
    else:
        if not get_settings().staff_can_create_retailers:
            raise HTTPException(403, "Staff retailer creation is disabled")
        retailer = Retailer(**payload.new_retailer.model_dump())
        db.add(retailer)
        db.flush()

    sale_id = uuid.uuid4()
    line_data = []
    for item in payload.items:
        price = product_map[item.product_id].selling_price
        line_total = (price * item.quantity).quantize(MONEY, rounding=ROUND_HALF_UP)
        line_data.append((item, price, line_total))
    subtotal = sum((line[2] for line in line_data), Decimal("0.00")).quantize(MONEY)
    sale_date = business_today()
    sale = Sale(id=sale_id, sale_number=f"MM-{sale_date:%Y%m%d}-{str(sale_id)[:8].upper()}", idempotency_key=payload.idempotency_key, staff_id=actor.id, retailer_id=retailer.id, sale_date=sale_date, subtotal=subtotal, total=subtotal, payment_status=payload.payment_status, payment_method=payload.payment_method, notes=payload.notes)
    db.add(sale)
    for item, price, line_total in line_data:
        db.add(SaleItem(sale_id=sale.id, product_id=item.product_id, quantity=item.quantity, unit_price_snapshot=price, line_total=line_total))
        movement_key = "sale:" + hashlib.sha256(f"{payload.idempotency_key}:{item.product_id}".encode()).hexdigest()
        db.add(StockMovement(product_id=item.product_id, staff_id=actor.id, movement_type=MovementType.staff_sale, quantity=item.quantity, reference_type="sale", reference_id=sale.id, notes=f"Sale {sale.sale_number}", created_by=actor.id, idempotency_key=movement_key))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        duplicate = db.scalar(select(Sale).where(Sale.idempotency_key == payload.idempotency_key))
        if duplicate:
            return duplicate
        raise HTTPException(409, "Duplicate or conflicting sale operation")
    return db.scalar(select(Sale).where(Sale.id == sale.id))
