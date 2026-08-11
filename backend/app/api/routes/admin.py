import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.dependencies import owner_only
from app.core.security import hash_password
from app.database import get_db
from app.models import Product, User, UserRole
from app.schemas import PasswordReset, ProductIn, ProductOut, StaffDetail, StaffListRow, UserCreate, UserOut, UserUpdate
from app.services.staff import staff_detail, staff_list

router = APIRouter(prefix="/admin", tags=["owner administration"])


@router.get("/users", response_model=list[UserOut])
def list_users(_: User = Depends(owner_only), db: Session = Depends(get_db)):
    return db.scalars(select(User).order_by(User.created_at.desc())).all()


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, _: User = Depends(owner_only), db: Session = Depends(get_db)):
    if payload.role == UserRole.owner:
        raise HTTPException(status_code=400, detail="Additional owner accounts require a controlled administrative process")
    user = User(**payload.model_dump(exclude={"password"}), password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Phone or email already exists")
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: uuid.UUID, payload: UserUpdate, _: User = Depends(owner_only), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.id == user_id, User.role.in_((UserRole.manager, UserRole.staff))))
    if not user:
        raise HTTPException(status_code=404, detail="Staff account not found")
    user.full_name = payload.full_name.strip()
    user.phone = payload.phone
    user.role = payload.role
    user.active = payload.active
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Phone already exists")
    db.refresh(user)
    return user


@router.post("/users/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def reset_user_password(user_id: uuid.UUID, payload: PasswordReset, _: User = Depends(owner_only), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.id == user_id, User.role.in_((UserRole.manager, UserRole.staff))))
    if not user:
        raise HTTPException(status_code=404, detail="Staff account not found")
    user.password_hash = hash_password(payload.new_password)
    db.commit()


@router.get("/staff", response_model=list[StaffListRow])
def list_staff(q: str | None = Query(default=None, max_length=120), role: UserRole | None = None, active: bool | None = None, limit: int = Query(default=100, ge=1, le=100), offset: int = Query(default=0, ge=0), _: User = Depends(owner_only), db: Session = Depends(get_db)):
    return staff_list(db, q, role, active, limit, offset)


@router.get("/staff/{staff_id}", response_model=StaffDetail)
def get_staff_detail(staff_id: uuid.UUID, period: str = "last_30_days", date_from: date | None = None, date_to: date | None = None, _: User = Depends(owner_only), db: Session = Depends(get_db)):
    return staff_detail(db, staff_id, period, date_from, date_to)


@router.get("/products", response_model=list[ProductOut])
def list_products(_: User = Depends(owner_only), db: Session = Depends(get_db)):
    return db.scalars(select(Product).order_by(Product.name)).all()


@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductIn, _: User = Depends(owner_only), db: Session = Depends(get_db)):
    product = Product(**payload.model_dump())
    db.add(product)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="SKU already exists")
    db.refresh(product)
    return product
