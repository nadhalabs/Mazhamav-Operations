from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.api.dependencies import owner_only
from app.database import get_db
from app.models import User
from app.services.dashboard import owner_dashboard
from app.services.reports import csv_response_data, report_data

router = APIRouter(tags=["owner dashboard and reports"])
REPORTS = {"sales", "staff-sales", "product-sales", "retailer-sales", "inventory-movements", "stock-requests", "pending-payments"}


@router.get("/dashboard/owner")
def dashboard(period: str = Query(default="last_30_days"), date_from: date | None = None, date_to: date | None = None, _: User = Depends(owner_only), db: Session = Depends(get_db)):
    return owner_dashboard(db, period, date_from, date_to)


@router.get("/reports/{report}.csv")
def export_csv(report: str, date_from: date | None = None, date_to: date | None = None, _: User = Depends(owner_only), db: Session = Depends(get_db)):
    if report not in REPORTS: raise HTTPException(404, "Report not found")
    if date_from and date_to and date_from > date_to: raise HTTPException(422, "date_from must not be after date_to")
    headers, rows = report_data(db, report, date_from, date_to)
    content = "\ufeff" + csv_response_data(headers, rows)
    return Response(content=content, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="mazha-mav-{report}.csv"'})
