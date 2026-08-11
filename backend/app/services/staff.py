import uuid
from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.time import business_today
from app.models import PaymentStatus, Product, RequestStatus, Retailer, Sale, SaleItem, StockMovement, StockRequest, User, UserRole
from app.services.dashboard import resolve_range
from app.services.inventory import stock_totals

ZERO = Decimal("0")
MANAGED_ROLES = (UserRole.manager, UserRole.staff)


def staff_list(db: Session, query: str | None, role: UserRole | None, active: bool | None, limit: int, offset: int):
    stmt = select(User).where(User.role.in_(MANAGED_ROLES))
    if query:
        term = f"%{query.strip()}%"
        stmt = stmt.where(or_(User.full_name.ilike(term), User.phone.ilike(term)))
    if role:
        if role not in MANAGED_ROLES:
            raise HTTPException(422, "Role filter must be staff or manager")
        stmt = stmt.where(User.role == role)
    if active is not None:
        stmt = stmt.where(User.active.is_(active))
    users = db.scalars(stmt.order_by(User.full_name).offset(offset).limit(limit)).all()
    if not users:
        return []
    ids = [user.id for user in users]
    today = business_today(); month_start = today.replace(day=1)
    today_sales = dict(db.execute(select(Sale.staff_id, func.sum(Sale.total)).where(Sale.staff_id.in_(ids), Sale.sale_date == today).group_by(Sale.staff_id)).all())
    month_sales = dict(db.execute(select(Sale.staff_id, func.sum(Sale.total)).where(Sale.staff_id.in_(ids), Sale.sale_date.between(month_start, today)).group_by(Sale.staff_id)).all())
    sale_activity = dict(db.execute(select(Sale.staff_id, func.max(Sale.created_at)).where(Sale.staff_id.in_(ids)).group_by(Sale.staff_id)).all())
    movement_activity = dict(db.execute(select(StockMovement.staff_id, func.max(StockMovement.created_at)).where(StockMovement.staff_id.in_(ids)).group_by(StockMovement.staff_id)).all())
    request_activity = dict(db.execute(select(StockRequest.staff_id, func.max(StockRequest.requested_at)).where(StockRequest.staff_id.in_(ids)).group_by(StockRequest.staff_id)).all())
    totals, _ = stock_totals(db)
    rows = []
    for user in users:
        current_stock = sum((v["issued"] - v["sold"] - v["returned"] + v["adjustments"] for (sid, _), v in totals.items() if sid == user.id), ZERO)
        activities = [value for value in (sale_activity.get(user.id), movement_activity.get(user.id), request_activity.get(user.id)) if value]
        rows.append({"id": user.id, "full_name": user.full_name, "phone": user.phone, "role": user.role, "active": user.active, "current_stock": current_stock, "sales_today": today_sales.get(user.id, ZERO), "sales_this_month": month_sales.get(user.id, ZERO), "last_activity": max(activities) if activities else None, "created_at": user.created_at})
    return rows


def staff_detail(db: Session, staff_id: uuid.UUID, period: str, date_from: date | None, date_to: date | None):
    user = db.scalar(select(User).where(User.id == staff_id, User.role.in_(MANAGED_ROLES)))
    if not user:
        raise HTTPException(404, "Staff account not found")
    start, end = resolve_range(period, date_from, date_to)
    today = business_today(); week_start = today - timedelta(days=6); month_start = today.replace(day=1)
    sales_today = db.scalar(select(func.coalesce(func.sum(Sale.total), 0)).where(Sale.staff_id == staff_id, Sale.sale_date == today)) or ZERO
    sales_week = db.scalar(select(func.coalesce(func.sum(Sale.total), 0)).where(Sale.staff_id == staff_id, Sale.sale_date.between(week_start, today))) or ZERO
    sales_month = db.scalar(select(func.coalesce(func.sum(Sale.total), 0)).where(Sale.staff_id == staff_id, Sale.sale_date.between(month_start, today))) or ZERO
    range_value, range_retailers = db.execute(select(func.coalesce(func.sum(Sale.total), 0), func.count(func.distinct(Sale.retailer_id))).where(Sale.staff_id == staff_id, Sale.sale_date.between(start, end))).one()
    range_quantity = db.scalar(select(func.coalesce(func.sum(SaleItem.quantity), 0)).join(Sale, Sale.id == SaleItem.sale_id).where(Sale.staff_id == staff_id, Sale.sale_date.between(start, end))) or ZERO
    pending_value = db.scalar(select(func.coalesce(func.sum(Sale.total), 0)).where(Sale.staff_id == staff_id, Sale.payment_status == PaymentStatus.pending, Sale.sale_date.between(start, end))) or ZERO
    pending_requests = db.scalar(select(func.count()).select_from(StockRequest).where(StockRequest.staff_id == staff_id, StockRequest.status.in_((RequestStatus.pending, RequestStatus.approved)))) or 0
    totals, _ = stock_totals(db)
    products = db.scalars(select(Product).order_by(Product.name)).all()
    stock = []
    for product in products:
        values = totals[(staff_id, product.id)]
        stock.append({"product_id": product.id, "product": product.name, "unit_name": product.unit_name, "total_issued": values["issued"], "total_sold": values["sold"], "total_returned": values["returned"], "adjustments": values["adjustments"], "current_stock": values["issued"] - values["sold"] - values["returned"] + values["adjustments"]})
    current_stock = sum((row["current_stock"] for row in stock), ZERO)

    product_rows = db.execute(select(Product.id, Product.name, func.sum(SaleItem.quantity), func.sum(SaleItem.line_total)).join(SaleItem, SaleItem.product_id == Product.id).join(Sale, Sale.id == SaleItem.sale_id).where(Sale.staff_id == staff_id, Sale.sale_date.between(start, end)).group_by(Product.id, Product.name).order_by(func.sum(SaleItem.line_total).desc())).all()
    # Sum sale totals in a separate subquery to avoid multiplying multi-item sale values.
    retailer_sales = db.execute(select(Retailer.id, Retailer.shop_name, func.sum(Sale.total), func.max(Sale.sale_date)).join(Sale, Sale.retailer_id == Retailer.id).where(Sale.staff_id == staff_id, Sale.sale_date.between(start, end)).group_by(Retailer.id, Retailer.shop_name).order_by(func.sum(Sale.total).desc())).all()
    retailer_quantity = dict(db.execute(select(Sale.retailer_id, func.sum(SaleItem.quantity)).join(SaleItem, SaleItem.sale_id == Sale.id).where(Sale.staff_id == staff_id, Sale.sale_date.between(start, end)).group_by(Sale.retailer_id)).all())
    place_value = db.execute(select(Retailer.district, Retailer.city, Retailer.area, func.sum(Sale.total), func.count(func.distinct(Sale.retailer_id)), func.max(Sale.sale_date)).join(Sale, Sale.retailer_id == Retailer.id).where(Sale.staff_id == staff_id, Sale.sale_date.between(start, end)).group_by(Retailer.district, Retailer.city, Retailer.area).order_by(func.sum(Sale.total).desc())).all()
    place_quantity = {(district, city, area): quantity for district, city, area, quantity in db.execute(select(Retailer.district, Retailer.city, Retailer.area, func.sum(SaleItem.quantity)).join(Sale, Sale.retailer_id == Retailer.id).join(SaleItem, SaleItem.sale_id == Sale.id).where(Sale.staff_id == staff_id, Sale.sale_date.between(start, end)).group_by(Retailer.district, Retailer.city, Retailer.area)).all()}
    recent = db.scalars(select(Sale).options(joinedload(Sale.retailer), selectinload(Sale.items)).where(Sale.staff_id == staff_id).order_by(Sale.created_at.desc()).limit(10)).all()
    requests = db.execute(select(StockRequest, Product.name).join(Product, Product.id == StockRequest.product_id).where(StockRequest.staff_id == staff_id).order_by(StockRequest.requested_at.desc()).limit(20)).all()
    return {
        "id": user.id, "full_name": user.full_name, "phone": user.phone, "role": user.role, "active": user.active, "created_at": user.created_at,
        "range": {"period": period, "date_from": start.isoformat(), "date_to": end.isoformat()},
        "performance": {"sales_today": sales_today, "sales_this_week": sales_week, "sales_this_month": sales_month, "quantity_sold": range_quantity, "sales_value": range_value, "retailers_served": range_retailers, "pending_payment_value": pending_value, "current_stock": current_stock, "pending_stock_requests": pending_requests},
        "stock": stock,
        "product_performance": [{"product_id": pid, "product": name, "quantity_sold": quantity, "revenue": revenue} for pid, name, quantity, revenue in product_rows],
        "retailer_activity": [{"retailer_id": rid, "retailer": name, "quantity_sold": retailer_quantity.get(rid, ZERO), "sales_value": value, "last_sale_date": last} for rid, name, value, last in retailer_sales],
        "area_performance": [{"district": district, "city": city, "area": area, "quantity_sold": place_quantity.get((district, city, area), ZERO), "sales_value": value, "retailers_served": served, "last_sale_date": last} for district, city, area, value, served, last in place_value],
        "recent_sales": [{"id": sale.id, "sale_number": sale.sale_number, "retailer": sale.retailer.shop_name, "quantity": sum((item.quantity for item in sale.items), ZERO), "total": sale.total, "payment_status": sale.payment_status, "sale_date": sale.sale_date, "created_at": sale.created_at} for sale in recent],
        "stock_requests": [{"id": request.id, "product": product_name, "requested_quantity": request.requested_quantity, "fulfilled_quantity": request.fulfilled_quantity, "status": request.status, "requested_at": request.requested_at} for request, product_name in requests],
    }
