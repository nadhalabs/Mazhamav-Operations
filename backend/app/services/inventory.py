import uuid
from collections import defaultdict
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models import MovementType, Product, StockMovement, User, UserRole

ZERO = Decimal("0")


def warehouse_balance(db: Session, product_id: uuid.UUID) -> Decimal:
    rows = db.execute(select(StockMovement.movement_type, StockMovement.staff_id, func.sum(StockMovement.quantity)).where(StockMovement.product_id == product_id).group_by(StockMovement.movement_type, StockMovement.staff_id)).all()
    total = ZERO
    for movement_type, staff_id, quantity in rows:
        if movement_type == MovementType.warehouse_in: total += quantity
        elif movement_type == MovementType.issued_to_staff: total -= quantity
        elif movement_type == MovementType.staff_return: total += quantity
        elif movement_type == MovementType.stock_adjustment and staff_id is None: total += quantity
    return total


def staff_balance(db: Session, staff_id: uuid.UUID, product_id: uuid.UUID) -> Decimal:
    rows = db.execute(select(StockMovement.movement_type, func.sum(StockMovement.quantity)).where(StockMovement.product_id == product_id, StockMovement.staff_id == staff_id).group_by(StockMovement.movement_type)).all()
    total = ZERO
    for movement_type, quantity in rows:
        if movement_type == MovementType.issued_to_staff: total += quantity
        elif movement_type in (MovementType.staff_sale, MovementType.staff_return): total -= quantity
        elif movement_type == MovementType.stock_adjustment: total += quantity
    return total


def warehouse_effect(movement: StockMovement) -> Decimal:
    if movement.movement_type == MovementType.warehouse_in:
        return movement.quantity
    if movement.movement_type == MovementType.issued_to_staff:
        return -movement.quantity
    if movement.movement_type == MovementType.staff_return:
        return movement.quantity
    if movement.movement_type == MovementType.stock_adjustment and movement.staff_id is None:
        return movement.quantity
    return ZERO


def staff_effect(movement: StockMovement) -> Decimal:
    if movement.movement_type == MovementType.issued_to_staff:
        return movement.quantity
    if movement.movement_type in (MovementType.staff_sale, MovementType.staff_return):
        return -movement.quantity
    if movement.movement_type == MovementType.stock_adjustment and movement.staff_id is not None:
        return movement.quantity
    return ZERO


def _validate_targets(db: Session, product_id: uuid.UUID, staff_id: uuid.UUID | None = None) -> tuple[Product, User | None]:
    # Product row is the serialization lock for every posting that affects its warehouse balance.
    product = db.scalar(select(Product).where(Product.id == product_id, Product.active.is_(True)).with_for_update())
    if not product:
        raise HTTPException(422, "Active product not found")
    staff = None
    if staff_id:
        staff = db.scalar(select(User).where(User.id == staff_id, User.role == UserRole.staff, User.active.is_(True)))
        if not staff:
            raise HTTPException(422, "Active staff member not found")
    return product, staff


def _existing(db: Session, key: str) -> StockMovement | None:
    return db.scalar(select(StockMovement).where(StockMovement.idempotency_key == key))


def post_movement(db: Session, *, actor: User, product_id: uuid.UUID, movement_type: MovementType, quantity: Decimal, idempotency_key: str, staff_id: uuid.UUID | None = None, notes: str | None = None) -> StockMovement:
    existing = _existing(db, idempotency_key)
    if existing:
        if (existing.product_id, existing.staff_id, existing.movement_type, existing.quantity) == (product_id, staff_id, movement_type, quantity):
            return existing
        raise HTTPException(409, "Idempotency key was already used for a different movement")

    _validate_targets(db, product_id, staff_id)
    warehouse_before = warehouse_balance(db, product_id)
    staff_before = staff_balance(db, staff_id, product_id) if staff_id else ZERO

    warehouse_after = warehouse_before
    staff_after = staff_before
    if movement_type == MovementType.issued_to_staff:
        warehouse_after -= quantity
        staff_after += quantity
    elif movement_type == MovementType.staff_return:
        warehouse_after += quantity
        staff_after -= quantity
    elif movement_type == MovementType.warehouse_in:
        warehouse_after += quantity
    elif movement_type == MovementType.stock_adjustment:
        if staff_id:
            staff_after += quantity
        else:
            warehouse_after += quantity
    else:
        raise HTTPException(422, "This movement type is not supported by this operation")

    if warehouse_after < 0:
        raise HTTPException(409, f"Insufficient warehouse stock; available balance is {warehouse_before}")
    if staff_id and staff_after < 0:
        raise HTTPException(409, f"Insufficient staff stock; available balance is {staff_before}")

    movement = StockMovement(product_id=product_id, staff_id=staff_id, movement_type=movement_type, quantity=quantity, notes=notes, created_by=actor.id, idempotency_key=idempotency_key)
    db.add(movement)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        duplicate = _existing(db, idempotency_key)
        if duplicate and (duplicate.product_id, duplicate.staff_id, duplicate.movement_type, duplicate.quantity) == (product_id, staff_id, movement_type, quantity):
            return duplicate
        raise HTTPException(409, "Duplicate or conflicting stock operation")
    db.refresh(movement)
    return movement


def stock_totals(db: Session):
    rows = db.execute(select(StockMovement.staff_id, StockMovement.product_id, StockMovement.movement_type, func.sum(StockMovement.quantity)).group_by(StockMovement.staff_id, StockMovement.product_id, StockMovement.movement_type)).all()
    staff = defaultdict(lambda: {"issued": ZERO, "sold": ZERO, "returned": ZERO, "adjustments": ZERO})
    warehouse = defaultdict(lambda: {"warehouse_in": ZERO, "issued": ZERO, "returned": ZERO, "adjustments": ZERO})
    for staff_id, product_id, movement_type, quantity in rows:
        w = warehouse[product_id]
        if movement_type == MovementType.warehouse_in: w["warehouse_in"] += quantity
        elif movement_type == MovementType.issued_to_staff: w["issued"] += quantity
        elif movement_type == MovementType.staff_return: w["returned"] += quantity
        elif movement_type == MovementType.stock_adjustment and staff_id is None: w["adjustments"] += quantity
        if staff_id:
            s = staff[(staff_id, product_id)]
            if movement_type == MovementType.issued_to_staff: s["issued"] += quantity
            elif movement_type == MovementType.staff_sale: s["sold"] += quantity
            elif movement_type == MovementType.staff_return: s["returned"] += quantity
            elif movement_type == MovementType.stock_adjustment: s["adjustments"] += quantity
    return staff, warehouse
