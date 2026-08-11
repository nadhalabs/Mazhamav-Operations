import csv
import io
from datetime import date
from enum import Enum
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models import PaymentStatus, Product, Retailer, Sale, SaleItem, StockMovement, StockRequest, User
from app.core.time import business_day_utc_bounds


def _safe(value):
    if value is None: return ""
    if isinstance(value, Enum): value = value.value
    text = str(value)
    return "'" + text if text.startswith(("=", "+", "-", "@")) else text


def csv_response_data(headers, rows):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows([[_safe(value) for value in row] for row in rows])
    return output.getvalue()


def report_data(db: Session, report: str, start: date | None, end: date | None):
    date_filter = []
    if start: date_filter.append(Sale.sale_date >= start)
    if end: date_filter.append(Sale.sale_date <= end)
    if report == "sales":
        rows = db.execute(select(Sale.sale_number, Sale.sale_date, User.full_name, Retailer.shop_name, Sale.subtotal, Sale.total, Sale.payment_status, Sale.payment_method, Sale.notes).join(User, User.id == Sale.staff_id).join(Retailer, Retailer.id == Sale.retailer_id).where(*date_filter).order_by(Sale.sale_date.desc(), Sale.sale_number)).all()
        return ["Sale Number", "Sale Date", "Staff", "Retailer", "Subtotal", "Total", "Payment Status", "Payment Method", "Notes"], rows
    if report == "staff-sales":
        sales_agg = {sid: (value, count, retailers) for sid, value, count, retailers in db.execute(select(Sale.staff_id, func.sum(Sale.total), func.count(), func.count(func.distinct(Sale.retailer_id))).where(*date_filter).group_by(Sale.staff_id)).all()}
        qty_agg = dict(db.execute(select(Sale.staff_id, func.sum(SaleItem.quantity)).join(SaleItem, SaleItem.sale_id == Sale.id).where(*date_filter).group_by(Sale.staff_id)).all())
        users = db.execute(select(User.id, User.full_name).where(User.id.in_(sales_agg.keys()))).all() if sales_agg else []
        rows = [(name, qty_agg.get(uid, 0), *sales_agg[uid]) for uid, name in users]
        return ["Staff", "Quantity Sold", "Sales Value", "Sales Count", "Retailers Served"], rows
    if report == "product-sales":
        rows = db.execute(select(Product.name, Product.sku, func.sum(SaleItem.quantity), func.sum(SaleItem.line_total)).join(SaleItem, SaleItem.product_id == Product.id).join(Sale, Sale.id == SaleItem.sale_id).where(*date_filter).group_by(Product.id, Product.name, Product.sku).order_by(func.sum(SaleItem.line_total).desc())).all()
        return ["Product", "SKU", "Quantity Sold", "Revenue"], rows
    if report == "retailer-sales":
        rows = db.execute(select(Retailer.shop_name, Retailer.area, Retailer.district, func.count(Sale.id), func.sum(Sale.total), func.max(Sale.sale_date)).join(Sale, Sale.retailer_id == Retailer.id).where(*date_filter).group_by(Retailer.id, Retailer.shop_name, Retailer.area, Retailer.district).order_by(func.sum(Sale.total).desc())).all()
        return ["Retailer", "Area", "District", "Sales Count", "Sales Value", "Last Sale Date"], rows
    if report == "inventory-movements":
        stmt = select(StockMovement.created_at, Product.name, User.full_name, StockMovement.movement_type, StockMovement.quantity, StockMovement.reference_type, StockMovement.reference_id, StockMovement.notes).join(Product, Product.id == StockMovement.product_id).outerjoin(User, User.id == StockMovement.staff_id)
        if start: stmt = stmt.where(StockMovement.created_at >= business_day_utc_bounds(start)[0])
        if end: stmt = stmt.where(StockMovement.created_at < business_day_utc_bounds(end)[1])
        return ["Timestamp", "Product", "Staff", "Movement Type", "Quantity", "Reference Type", "Reference ID", "Notes"], db.execute(stmt.order_by(StockMovement.created_at.desc())).all()
    if report == "stock-requests":
        stmt = select(StockRequest.requested_at, User.full_name, Product.name, StockRequest.requested_quantity, StockRequest.status, StockRequest.fulfilled_quantity, StockRequest.reviewed_at, StockRequest.fulfilled_at, StockRequest.notes, StockRequest.review_notes).join(User, User.id == StockRequest.staff_id).join(Product, Product.id == StockRequest.product_id)
        if start: stmt = stmt.where(StockRequest.requested_at >= business_day_utc_bounds(start)[0])
        if end: stmt = stmt.where(StockRequest.requested_at < business_day_utc_bounds(end)[1])
        return ["Requested At", "Staff", "Product", "Requested Quantity", "Status", "Fulfilled Quantity", "Reviewed At", "Fulfilled At", "Staff Note", "Review Note"], db.execute(stmt.order_by(StockRequest.requested_at.desc())).all()
    if report == "pending-payments":
        stmt = select(Sale.sale_number, Sale.sale_date, User.full_name, Retailer.shop_name, Sale.total, Sale.payment_method, Sale.notes).join(User, User.id == Sale.staff_id).join(Retailer, Retailer.id == Sale.retailer_id).where(Sale.payment_status == PaymentStatus.pending, *date_filter)
        return ["Sale Number", "Sale Date", "Staff", "Retailer", "Pending Value", "Payment Method", "Notes"], db.execute(stmt.order_by(Sale.sale_date.desc())).all()
    raise ValueError("Unsupported report")
