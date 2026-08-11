from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import PaymentStatus, Product, Retailer, Sale, SaleItem, User
from app.services.dashboard import resolve_range

ZERO = Decimal("0")


def _place_rows(db: Session, column, start: date, end: date):
    values = {row[0]: row[1:] for row in db.execute(select(column, func.sum(Sale.total), func.count(func.distinct(Sale.retailer_id)), func.max(Sale.sale_date)).join(Sale, Sale.retailer_id == Retailer.id).where(Sale.sale_date.between(start, end), column.is_not(None), column != "").group_by(column)).all()}
    quantities = dict(db.execute(select(column, func.sum(SaleItem.quantity)).join(Sale, Sale.id == SaleItem.sale_id).join(Retailer, Retailer.id == Sale.retailer_id).where(Sale.sale_date.between(start, end), column.is_not(None), column != "").group_by(column)).all())
    active = dict(db.execute(select(column, func.count()).where(Retailer.active.is_(True), column.is_not(None), column != "").group_by(column)).all())
    return [{"name": name, "sales_value": str(value), "quantity_sold": str(quantities.get(name, ZERO)), "retailers_served": served, "active_retailers": active.get(name, 0), "last_sale_date": last.isoformat()} for name, (value, served, last) in values.items()]


def _focus(rows, previous):
    positive = [Decimal(r["sales_value"]) for r in rows if Decimal(r["sales_value"]) > 0]
    average = sum(positive, ZERO) / len(positive) if positive else ZERO
    output = {"strong": [], "growth_opportunity": [], "needs_attention": [], "low_coverage": []}
    for row in rows:
        value, before = Decimal(row["sales_value"]), previous.get(row["name"], ZERO)
        item = {**row, "previous_sales_value": str(before)}
        if before > 0 and value < before:
            item["why"] = f"Sales fell from ₹{before} to ₹{value} versus the previous comparable period."
            output["needs_attention"].append(item)
        if row["active_retailers"] <= 1:
            output["low_coverage"].append({**item, "why": f"Only {row['active_retailers']} active retailer is recorded here."})
        elif value >= average and value > 0:
            output["strong"].append({**item, "why": f"₹{value} is at or above the ₹{average.quantize(Decimal('0.01'))} area average."})
        elif value > 0:
            output["growth_opportunity"].append({**item, "why": f"{row['active_retailers']} active retailers, with sales below the area average."})
    return output


def area_overview(db: Session, period: str, date_from: date | None, date_to: date | None):
    start, end = resolve_range(period, date_from, date_to)
    span = (end - start).days + 1
    previous_start, previous_end = start - timedelta(days=span), start - timedelta(days=1)
    areas = sorted(_place_rows(db, Retailer.area, start, end), key=lambda r: Decimal(r["sales_value"]), reverse=True)
    previous = {r["name"]: Decimal(r["sales_value"]) for r in _place_rows(db, Retailer.area, previous_start, previous_end)}
    sales = db.scalar(select(func.coalesce(func.sum(Sale.total), 0)).where(Sale.sale_date.between(start, end))) or ZERO
    quantity = db.scalar(select(func.coalesce(func.sum(SaleItem.quantity), 0)).join(Sale).where(Sale.sale_date.between(start, end))) or ZERO
    return {"range": {"period": period, "date_from": start.isoformat(), "date_to": end.isoformat()}, "summary": {"sales_value": str(sales), "quantity_sold": str(quantity), "active_retailers": db.scalar(select(func.count()).select_from(Retailer).where(Retailer.active.is_(True))) or 0, "areas": len(areas), "highest_area": areas[0]["name"] if areas else None}, "districts": sorted(_place_rows(db, Retailer.district, start, end), key=lambda r: Decimal(r["sales_value"]), reverse=True), "cities": sorted(_place_rows(db, Retailer.city, start, end), key=lambda r: Decimal(r["sales_value"]), reverse=True), "areas": areas, "focus": _focus(areas, previous)}


def area_detail(db: Session, area: str, period: str, date_from: date | None, date_to: date | None):
    start, end = resolve_range(period, date_from, date_to)
    condition = Retailer.area == area
    sale_ids = select(Sale.id).join(Retailer).where(condition, Sale.sale_date.between(start, end))
    sales = db.scalars(select(Sale).join(Retailer).where(condition, Sale.sale_date.between(start, end)).order_by(Sale.created_at.desc()).limit(20)).all()
    daily = dict(db.execute(select(Sale.sale_date, func.sum(Sale.total)).join(Retailer).where(condition, Sale.sale_date.between(start, end)).group_by(Sale.sale_date)).all())
    products = db.execute(select(Product.name, func.sum(SaleItem.quantity), func.sum(SaleItem.line_total)).join(SaleItem).where(SaleItem.sale_id.in_(sale_ids)).group_by(Product.id, Product.name).order_by(func.sum(SaleItem.line_total).desc())).all()
    retailers = db.execute(select(Retailer.id, Retailer.shop_name, func.sum(Sale.total)).join(Sale).where(condition, Sale.sale_date.between(start, end)).group_by(Retailer.id, Retailer.shop_name).order_by(func.sum(Sale.total).desc())).all()
    staff = db.execute(select(User.id, User.full_name, func.sum(Sale.total)).join(Sale, Sale.staff_id == User.id).join(Retailer, Retailer.id == Sale.retailer_id).where(condition, Sale.sale_date.between(start, end)).group_by(User.id, User.full_name).order_by(func.sum(Sale.total).desc())).all()
    pending = db.scalar(select(func.coalesce(func.sum(Sale.total), 0)).join(Retailer).where(condition, Sale.payment_status == PaymentStatus.pending)) or ZERO
    trend = []; cursor = start
    while cursor <= end:
        trend.append({"date": cursor.isoformat(), "sales_value": str(daily.get(cursor, ZERO))}); cursor += timedelta(days=1)
    return {"area": area, "range": {"period": period, "date_from": start.isoformat(), "date_to": end.isoformat()}, "sales_value": str(sum((s.total for s in sales), ZERO)), "pending_payment_value": str(pending), "trend": trend, "products": [{"product": n, "quantity": str(q), "sales_value": str(v)} for n, q, v in products], "retailers": [{"id": str(i), "retailer": n, "sales_value": str(v)} for i, n, v in retailers], "staff": [{"id": str(i), "staff": n, "sales_value": str(v)} for i, n, v in staff], "recent_sales": [{"id": str(s.id), "sale_number": s.sale_number, "retailer": s.retailer.shop_name, "date": s.sale_date, "total": str(s.total), "status": s.payment_status.value} for s in sales]}
