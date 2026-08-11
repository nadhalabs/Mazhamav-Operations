import calendar
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session
from app.models import PaymentMethod, PaymentStatus, Product, RequestStatus, Retailer, Sale, SaleItem, StockRequest, User, UserRole
from app.core.time import business_today
from app.services.inventory import stock_totals

ZERO = Decimal("0")


def resolve_range(period: str, date_from: date | None, date_to: date | None) -> tuple[date, date]:
    today = business_today()
    if period == "today": return today, today
    if period == "last_7_days": return today - timedelta(days=6), today
    if period == "last_30_days": return today - timedelta(days=29), today
    if period == "this_month": return today.replace(day=1), today
    if period == "custom":
        if not date_from or not date_to or date_from > date_to:
            raise HTTPException(422, "Custom range requires valid date_from and date_to")
        if (date_to - date_from).days > 366:
            raise HTTPException(422, "Dashboard range cannot exceed 367 days")
        return date_from, date_to
    raise HTTPException(422, "Unsupported dashboard period")


def _sales_summary(db: Session, start: date, end: date):
    value = db.scalar(select(func.coalesce(func.sum(Sale.total), 0)).where(Sale.sale_date.between(start, end))) or ZERO
    quantity = db.scalar(select(func.coalesce(func.sum(SaleItem.quantity), 0)).join(Sale, Sale.id == SaleItem.sale_id).where(Sale.sale_date.between(start, end))) or ZERO
    return value, quantity


def owner_dashboard(db: Session, period: str, date_from: date | None, date_to: date | None):
    start, end = resolve_range(period, date_from, date_to)
    today = business_today(); yesterday = today - timedelta(days=1)
    month_start = today.replace(day=1)
    prev_month_end = month_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)
    comparable_end = prev_month_start.replace(day=min(today.day, calendar.monthrange(prev_month_start.year, prev_month_start.month)[1]))

    today_sales, today_qty = _sales_summary(db, today, today)
    yesterday_sales, _ = _sales_summary(db, yesterday, yesterday)
    month_sales, _ = _sales_summary(db, month_start, today)
    previous_comparable_sales, _ = _sales_summary(db, prev_month_start, comparable_end)

    staff_totals, warehouse_totals = stock_totals(db)
    stock_with_staff = sum((v["issued"] - v["sold"] - v["returned"] + v["adjustments"] for v in staff_totals.values()), ZERO)
    warehouse_stock = sum((v["warehouse_in"] - v["issued"] + v["returned"] + v["adjustments"] for v in warehouse_totals.values()), ZERO)
    pending_requests = db.scalar(select(func.count()).select_from(StockRequest).where(StockRequest.status == RequestStatus.pending)) or 0
    pending_value = db.scalar(select(func.coalesce(func.sum(Sale.total), 0)).where(Sale.payment_status == PaymentStatus.pending)) or ZERO
    active_staff = db.scalar(select(func.count()).select_from(User).where(User.role == UserRole.staff, User.active.is_(True))) or 0

    daily_raw = dict(db.execute(select(Sale.sale_date, func.sum(Sale.total)).where(Sale.sale_date.between(start, end)).group_by(Sale.sale_date)).all())
    trend = []
    cursor = start
    while cursor <= end:
        trend.append({"date": cursor.isoformat(), "sales_value": str(daily_raw.get(cursor, ZERO))})
        cursor += timedelta(days=1)

    product_rows = db.execute(select(Product.id, Product.name, func.sum(SaleItem.quantity), func.sum(SaleItem.line_total)).join(SaleItem, SaleItem.product_id == Product.id).join(Sale, Sale.id == SaleItem.sale_id).where(Sale.sale_date.between(start, end)).group_by(Product.id, Product.name).order_by(func.sum(SaleItem.line_total).desc())).all()
    product_revenue = sum((row[3] for row in product_rows), ZERO)
    products = [{"product_id": str(pid), "product": name, "quantity_sold": str(qty), "revenue": str(revenue), "contribution_percent": str((revenue / product_revenue * 100).quantize(Decimal("0.01")) if product_revenue else ZERO)} for pid, name, qty, revenue in product_rows]

    staff_value = {row[0]: row[1:] for row in db.execute(select(Sale.staff_id, func.sum(Sale.total), func.count(distinct(Sale.retailer_id))).where(Sale.sale_date.between(start, end)).group_by(Sale.staff_id)).all()}
    staff_qty = dict(db.execute(select(Sale.staff_id, func.sum(SaleItem.quantity)).join(SaleItem, SaleItem.sale_id == Sale.id).where(Sale.sale_date.between(start, end)).group_by(Sale.staff_id)).all())
    request_counts = dict(db.execute(select(StockRequest.staff_id, func.count()).where(StockRequest.status == RequestStatus.pending).group_by(StockRequest.staff_id)).all())
    staff_users = db.scalars(select(User).where(User.role == UserRole.staff, User.active.is_(True)).order_by(User.full_name)).all()
    staff = []
    for user in staff_users:
        value, retailers = staff_value.get(user.id, (ZERO, 0)); qty = staff_qty.get(user.id, ZERO)
        current = sum((v["issued"] - v["sold"] - v["returned"] + v["adjustments"] for (sid, _), v in staff_totals.items() if sid == user.id), ZERO)
        staff.append({"staff_id": str(user.id), "staff": user.full_name, "quantity_sold": str(qty), "sales_value": str(value), "retailers_served": retailers, "current_stock": str(current), "pending_stock_requests": request_counts.get(user.id, 0)})

    products_all = db.scalars(select(Product).where(Product.active.is_(True)).order_by(Product.name)).all()
    warehouse_by_product = []
    for p in products_all:
        v = warehouse_totals[p.id]; balance = v["warehouse_in"] - v["issued"] + v["returned"] + v["adjustments"]
        warehouse_by_product.append({"product_id": str(p.id), "product": p.name, "unit_name": p.unit_name, "available": str(balance), "is_low_stock": balance <= Decimal("5"), "has_discrepancy": balance < 0})
    negative_staff = [{"staff_id": str(sid), "product_id": str(pid), "balance": str(v["issued"] - v["sold"] - v["returned"] + v["adjustments"])} for (sid, pid), v in staff_totals.items() if v["issued"] - v["sold"] - v["returned"] + v["adjustments"] < 0]

    retailer_rows = db.execute(select(Retailer.id, Retailer.shop_name, Retailer.area, Retailer.district, func.sum(Sale.total), func.max(Sale.sale_date)).join(Sale, Sale.retailer_id == Retailer.id).where(Sale.sale_date.between(start, end)).group_by(Retailer.id, Retailer.shop_name, Retailer.area, Retailer.district).order_by(func.sum(Sale.total).desc())).all()
    all_retailer_metrics = [{"retailer_id": str(rid), "retailer": name, "area": area, "district": district, "sales_value": str(value), "last_sale_date": last.isoformat()} for rid, name, area, district, value, last in retailer_rows]
    top_retailers = all_retailer_metrics[:10]
    recent_retailers = sorted(all_retailer_metrics, key=lambda row: row["last_sale_date"], reverse=True)[:10]
    active_ids = {row[0] for row in retailer_rows}
    inactive = db.scalars(select(Retailer).where(Retailer.active.is_(True), Retailer.id.not_in(active_ids) if active_ids else True).order_by(Retailer.shop_name).limit(20)).all()
    inactive_retailers = [{"retailer_id": str(r.id), "retailer": r.shop_name, "area": r.area, "district": r.district} for r in inactive]
    geo_rows = db.execute(select(Retailer.district, func.sum(Sale.total)).join(Sale, Sale.retailer_id == Retailer.id).where(Sale.sale_date.between(start, end), Retailer.district.is_not(None)).group_by(Retailer.district).order_by(func.sum(Sale.total).desc())).all()
    sales_by_district = [{"district": district, "sales_value": str(value)} for district, value in geo_rows] if len(geo_rows) >= 2 else []

    payment_rows = db.execute(select(Sale.payment_status, func.count(), func.sum(Sale.total)).where(Sale.sale_date.between(start, end)).group_by(Sale.payment_status)).all()
    payments = {status.value: {"count": count, "value": str(value)} for status, count, value in payment_rows}
    method_rows = db.execute(select(Sale.payment_method, func.count(), func.sum(Sale.total)).where(Sale.sale_date.between(start, end), Sale.payment_method.is_not(None)).group_by(Sale.payment_method)).all()
    methods = [{"method": method.value, "count": count, "value": str(value)} for method, count, value in method_rows]

    return {"range": {"period": period, "date_from": start.isoformat(), "date_to": end.isoformat()}, "kpis": {"sales_today": str(today_sales), "sales_yesterday": str(yesterday_sales), "quantity_sold_today": str(today_qty), "sales_this_month": str(month_sales), "sales_previous_comparable_period": str(previous_comparable_sales), "stock_with_staff": str(stock_with_staff), "warehouse_stock": str(warehouse_stock), "pending_stock_requests": pending_requests, "pending_payment_value": str(pending_value), "active_sales_staff": active_staff}, "sales_trend": trend, "product_performance": products, "staff_performance": staff, "stock_overview": {"warehouse_by_product": warehouse_by_product, "staff_total": str(stock_with_staff), "pending_requests": pending_requests, "negative_staff_discrepancies": negative_staff}, "retailer_insights": {"top_retailers": top_retailers, "recently_active": recent_retailers, "inactive_in_period": inactive_retailers, "sales_by_district": sales_by_district}, "payments": {"paid": payments.get("paid", {"count": 0, "value": "0"}), "pending": payments.get("pending", {"count": 0, "value": "0"}), "by_method": methods}}
