import uuid
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models import MovementType, Product, RequestStatus, StockMovement, StockRequest, User
from app.services.inventory import warehouse_balance


def decide_request(db: Session, request_id: uuid.UUID, actor: User, target: RequestStatus, note: str | None) -> StockRequest:
    request = db.scalar(select(StockRequest).where(StockRequest.id == request_id).with_for_update())
    if not request:
        raise HTTPException(404, "Stock request not found")
    if request.status != RequestStatus.pending:
        raise HTTPException(409, f"Only pending requests can be {target.value}")
    request.status = target
    request.reviewed_by = actor.id
    request.reviewed_at = datetime.now(timezone.utc)
    request.review_notes = note
    db.commit(); db.refresh(request)
    return request


def fulfil_request(db: Session, request_id: uuid.UUID, actor: User, fulfilled_quantity: Decimal | None) -> StockRequest:
    request = db.scalar(select(StockRequest).where(StockRequest.id == request_id).with_for_update())
    if not request:
        raise HTTPException(404, "Stock request not found")
    if request.status == RequestStatus.fulfilled:
        if fulfilled_quantity is not None and fulfilled_quantity != request.fulfilled_quantity:
            raise HTTPException(409, f"Request was already fulfilled with quantity {request.fulfilled_quantity}")
        return request
    if request.status not in (RequestStatus.pending, RequestStatus.approved):
        raise HTTPException(409, "Only pending or approved requests can be fulfilled")
    quantity = fulfilled_quantity or request.requested_quantity

    product = db.scalar(select(Product).where(Product.id == request.product_id, Product.active.is_(True)).with_for_update())
    if not product:
        raise HTTPException(422, "Active product not found")
    available = warehouse_balance(db, request.product_id)
    if available < quantity:
        raise HTTPException(409, f"Insufficient warehouse stock; available balance is {available}")

    now = datetime.now(timezone.utc)
    movement = StockMovement(product_id=request.product_id, staff_id=request.staff_id, movement_type=MovementType.issued_to_staff, quantity=quantity, reference_type="stock_request", reference_id=request.id, notes=f"Fulfilment of stock request {request.id}", created_by=actor.id, idempotency_key=f"stock-request:{request.id}")
    db.add(movement)
    request.status = RequestStatus.fulfilled
    request.fulfilled_quantity = quantity
    request.fulfilled_by = actor.id
    request.fulfilled_at = now
    if request.reviewed_by is None:
        request.reviewed_by = actor.id
        request.reviewed_at = now
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        current = db.get(StockRequest, request_id)
        if current and current.status == RequestStatus.fulfilled:
            return current
        raise HTTPException(409, "Duplicate or conflicting fulfilment")
    db.refresh(request)
    return request
