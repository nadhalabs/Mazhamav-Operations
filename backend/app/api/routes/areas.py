from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.api.dependencies import owner_only
from app.database import get_db
from app.models import User
from app.services.areas import area_detail, area_overview

router = APIRouter(prefix="/areas", tags=["areas"])

@router.get("")
def overview(period: str = "last_30_days", date_from: date | None = None, date_to: date | None = None, _: User = Depends(owner_only), db: Session = Depends(get_db)):
    return area_overview(db, period, date_from, date_to)

@router.get("/detail")
def detail(area: str = Query(min_length=1, max_length=120), period: str = "last_30_days", date_from: date | None = None, date_to: date | None = None, _: User = Depends(owner_only), db: Session = Depends(get_db)):
    return area_detail(db, area, period, date_from, date_to)
