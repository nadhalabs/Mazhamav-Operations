from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.dependencies import owner_only
from app.core.security import hash_password
from app.database import get_db
from app.models import Product, User, UserRole
from app.schemas import ProductIn, ProductOut, UserCreate, UserOut

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

