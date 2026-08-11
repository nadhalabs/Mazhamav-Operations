from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import operations_viewer, staff_only
from app.database import get_db
from app.models import MovementType, Product, User, UserRole
from app.schemas import AdjustmentIn, IssueStockIn, MovementOut, MyStockRow, ReturnStockIn, StaffStockRow, WarehouseIn, WarehouseStockRow
from app.services.inventory import post_movement, stock_totals

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/options")
def inventory_options(_: User = Depends(operations_viewer), db: Session = Depends(get_db)):
    staff = db.scalars(select(User).where(User.role == UserRole.staff, User.active.is_(True)).order_by(User.full_name)).all()
    products = db.scalars(select(Product).where(Product.active.is_(True)).order_by(Product.name)).all()
    return {"staff": [{"id": str(u.id), "name": u.full_name} for u in staff], "products": [{"id": str(p.id), "name": p.name, "sku": p.sku, "unit_name": p.unit_name} for p in products]}


@router.post("/issues", response_model=MovementOut, status_code=status.HTTP_201_CREATED)
def issue_stock(payload: IssueStockIn, actor: User = Depends(operations_viewer), db: Session = Depends(get_db)):
    return post_movement(db, actor=actor, product_id=payload.product_id, staff_id=payload.staff_id, movement_type=MovementType.issued_to_staff, quantity=payload.quantity, notes=payload.note, idempotency_key=payload.idempotency_key)


@router.post("/returns", response_model=MovementOut, status_code=status.HTTP_201_CREATED)
def return_stock(payload: ReturnStockIn, actor: User = Depends(operations_viewer), db: Session = Depends(get_db)):
    return post_movement(db, actor=actor, product_id=payload.product_id, staff_id=payload.staff_id, movement_type=MovementType.staff_return, quantity=payload.quantity, notes=payload.reason, idempotency_key=payload.idempotency_key)


@router.post("/warehouse-in", response_model=MovementOut, status_code=status.HTTP_201_CREATED)
def receive_warehouse_stock(payload: WarehouseIn, actor: User = Depends(operations_viewer), db: Session = Depends(get_db)):
    return post_movement(db, actor=actor, product_id=payload.product_id, movement_type=MovementType.warehouse_in, quantity=payload.quantity, notes=payload.note, idempotency_key=payload.idempotency_key)


@router.post("/adjustments", response_model=MovementOut, status_code=status.HTTP_201_CREATED)
def adjust_stock(payload: AdjustmentIn, actor: User = Depends(operations_viewer), db: Session = Depends(get_db)):
    return post_movement(db, actor=actor, product_id=payload.product_id, staff_id=payload.staff_id, movement_type=MovementType.stock_adjustment, quantity=payload.quantity, notes=payload.reason, idempotency_key=payload.idempotency_key)


@router.get("/staff-overview", response_model=list[StaffStockRow])
def staff_overview(_: User = Depends(operations_viewer), db: Session = Depends(get_db)):
    totals, _ = stock_totals(db)
    users = {u.id: u for u in db.scalars(select(User).where(User.role == UserRole.staff)).all()}
    products = {p.id: p for p in db.scalars(select(Product)).all()}
    return [StaffStockRow(staff_id=sid, staff_name=users[sid].full_name, product_id=pid, product_name=products[pid].name, unit_name=products[pid].unit_name, total_issued=v["issued"], total_sold=v["sold"], total_returned=v["returned"], adjustments=v["adjustments"], current_balance=v["issued"] - v["sold"] - v["returned"] + v["adjustments"]) for (sid, pid), v in totals.items() if sid in users and pid in products]


@router.get("/warehouse", response_model=list[WarehouseStockRow])
def warehouse_overview(_: User = Depends(operations_viewer), db: Session = Depends(get_db)):
    _, totals = stock_totals(db)
    products = db.scalars(select(Product).where(Product.active.is_(True)).order_by(Product.name)).all()
    return [WarehouseStockRow(product_id=p.id, product_name=p.name, unit_name=p.unit_name, warehouse_in=totals[p.id]["warehouse_in"], issued=totals[p.id]["issued"], returned=totals[p.id]["returned"], adjustments=totals[p.id]["adjustments"], current_balance=totals[p.id]["warehouse_in"] - totals[p.id]["issued"] + totals[p.id]["returned"] + totals[p.id]["adjustments"]) for p in products]


@router.get("/my-stock", response_model=list[MyStockRow])
def my_stock(actor: User = Depends(staff_only), db: Session = Depends(get_db)):
    totals, _ = stock_totals(db)
    products = db.scalars(select(Product).where(Product.active.is_(True)).order_by(Product.name)).all()
    return [MyStockRow(product_id=p.id, product_name=p.name, unit_name=p.unit_name, stock_received=totals[(actor.id, p.id)]["issued"], sold=totals[(actor.id, p.id)]["sold"], returned=totals[(actor.id, p.id)]["returned"], adjustments=totals[(actor.id, p.id)]["adjustments"], current_stock=totals[(actor.id, p.id)]["issued"] - totals[(actor.id, p.id)]["sold"] - totals[(actor.id, p.id)]["returned"] + totals[(actor.id, p.id)]["adjustments"]) for p in products]
