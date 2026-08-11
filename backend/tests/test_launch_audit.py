import csv
import io
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from PIL import Image
from sqlalchemy import func, select

from app.core.security import hash_password
from app.core.time import business_day_utc_bounds, business_today
from app.models import (
    MovementType,
    PaymentStatus,
    Product,
    Retailer,
    Sale,
    SaleItem,
    StockMovement,
    StockRequest,
    User,
    UserRole,
)
from tests.conftest import TestingSession


PASSWORD = "Password123!"


def login(client, phone):
    client.cookies.clear()
    response = client.post("/api/v1/auth/login", json={"phone": phone, "password": PASSWORD})
    assert response.status_code == 200


def qr_png():
    output = io.BytesIO()
    Image.new("RGB", (200, 200), "white").save(output, "PNG")
    return output.getvalue()


def setup_working_day():
    with TestingSession() as db:
        owner = db.scalar(select(User).where(User.phone == "9000000001"))
        manager = db.scalar(select(User).where(User.phone == "9000000003"))
        staff_a = db.scalar(select(User).where(User.phone == "9000000002"))
        staff_b = User(full_name="Staff B", phone="9000000004", password_hash=hash_password(PASSWORD), role=UserRole.staff)
        staff_c = User(full_name="Staff C", phone="9000000005", password_hash=hash_password(PASSWORD), role=UserRole.staff)
        products = [
            Product(name="Mav Classic", sku="MM-CL", unit_name="packet", selling_price=Decimal("12.50")),
            Product(name="Mav Premium", sku="MM-PR", unit_name="packet", selling_price=Decimal("20.00")),
            Product(name="Mav Mini", sku="MM-MN", unit_name="packet", selling_price=Decimal("7.25")),
        ]
        retailers = [
            Retailer(shop_name="Green Stores", area="Nadakkavu", district="Kozhikode"),
            Retailer(shop_name="City Mart", area="Palayam", district="Kozhikode"),
            Retailer(shop_name="Family Shop", area="Kottakkal", district="Malappuram"),
            Retailer(shop_name="Fresh Bazaar", area="Manjeri", district="Malappuram"),
            Retailer(shop_name="Daily Needs", area="Kalpetta", district="Wayanad"),
            Retailer(shop_name="Hill Stores", area="Sulthan Bathery", district="Wayanad"),
            Retailer(shop_name="Metro Shop", area="Feroke", district="Kozhikode"),
            Retailer(shop_name="കേരള സ്റ്റോർ", area="Tirur", district="Malappuram"),
        ]
        db.add_all([staff_b, staff_c, *products, *retailers])
        db.commit()
        return {
            "owner": owner, "manager": manager,
            "staff": [staff_a, staff_b, staff_c],
            "products": products, "retailers": retailers,
        }


def post_inventory(client, action, body):
    response = client.post(f"/api/v1/inventory/{action}", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def post_sale(client, retailer_id=None, new_retailer=None, items=None, status="paid", method="cash", key="sale-key", notes=None):
    payload = {
        "retailer_id": str(retailer_id) if retailer_id else None,
        "new_retailer": new_retailer,
        "items": [{"product_id": str(product_id), "quantity": quantity} for product_id, quantity in items],
        "payment_status": status,
        "payment_method": method,
        "notes": notes,
        "idempotency_key": key,
        "total": "0.01",
    }
    response = client.post("/api/v1/sales", json=payload)
    assert response.status_code == 201, response.text
    return response


def csv_rows(response):
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    response.content.decode("utf-8")
    return list(csv.DictReader(io.StringIO(response.text)))


def test_complete_v1_reconciliation_and_controls(client):
    fixture = setup_working_day()
    a, b, c = fixture["staff"]
    p1, p2, p3 = fixture["products"]
    retailers = fixture["retailers"]
    login(client, "9000000001")
    for product, quantity, key in [(p1, 300, "recon-wh-p1"), (p2, 200, "recon-wh-p2"), (p3, 400, "recon-wh-p3")]:
        post_inventory(client, "warehouse-in", {"product_id": str(product.id), "quantity": quantity, "idempotency_key": key})
    for index, (staff, product, quantity) in enumerate([(a,p1,80),(a,p2,30),(b,p1,60),(b,p3,100),(c,p2,50),(c,p3,70)]):
        post_inventory(client, "issues", {"staff_id": str(staff.id), "product_id": str(product.id), "quantity": quantity, "idempotency_key": f"recon-issue-{index}"})
    specs = [
        (a, retailers[0], [(p1.id,10)], "paid", "cash", "recon-sale-1"),
        (a, retailers[1], [(p1.id,5),(p2.id,4)], "paid", "upi", "recon-sale-2"),
        (b, retailers[2], [(p1.id,7)], "pending", "credit", "recon-sale-3"),
        (b, retailers[3], [(p3.id,20)], "paid", "cash", "recon-sale-4"),
        (c, retailers[4], [(p2.id,6),(p3.id,8)], "pending", "credit", "recon-sale-5"),
        (c, retailers[5], [(p3.id,5)], "paid", "cash", "recon-sale-6"),
    ]
    sales = []
    for staff, retailer, items, status, method, key in specs:
        login(client, staff.phone)
        sales.append(post_sale(client, retailer.id, items=items, status=status, method=method, key=key, notes="=SUM(A1:A2)" if key == "recon-sale-5" else None).json())
    failed = client.post("/api/v1/sales", json={"retailer_id": str(retailers[0].id), "items": [{"product_id": str(p3.id), "quantity": 1000}], "payment_status": "paid", "payment_method": "cash", "idempotency_key": "recon-too-large"})
    assert failed.status_code == 409

    login(client, "9000000001")
    settings = client.post("/api/v1/payments/settings", data={"display_name":"Mazha Mav Foods","upi_id":"mazhamav@bank","bank_reference":"A/C 1234","active":"true"}, files={"qr_image": ("qr.png", qr_png(), "image/png")})
    assert settings.status_code == 200
    login(client, c.phone)
    qr_context = client.get(f"/api/v1/payments/qr-context?sale_id={sales[4]['id']}").json()
    assert qr_context["display_name"] == "Mazha Mav Foods"
    assert qr_context["sale_number"] == sales[4]["sale_number"]
    assert Decimal(qr_context["amount_due"]) == Decimal("178.00")
    with TestingSession() as db:
        assert db.get(Sale, uuid.UUID(sales[4]["id"])).payment_status == PaymentStatus.pending
    paid = client.post(f"/api/v1/payments/sales/{sales[4]['id']}/received", json={"payment_method":"upi"})
    assert paid.status_code == 200 and paid.json()["payment_received_by"] == str(c.id)
    login(client, b.phone)
    assert client.post(f"/api/v1/payments/sales/{sales[4]['id']}/received", json={"payment_method":"cash"}).status_code == 403

    login(client, a.phone)
    request = client.post("/api/v1/stock-requests", json={"product_id":str(p1.id),"requested_quantity":40,"notes":"Route replenishment"})
    assert request.status_code == 201
    assert client.post("/api/v1/stock-requests", json={"product_id":str(p1.id),"requested_quantity":5}).status_code == 409
    login(client, "9000000003")
    request_id = request.json()["id"]
    assert client.post(f"/api/v1/stock-requests/{request_id}/approve", json={"note":"Approved"}).status_code == 200
    fulfilled = client.post(f"/api/v1/stock-requests/{request_id}/fulfil", json={"fulfilled_quantity":35})
    assert fulfilled.status_code == 200 and Decimal(fulfilled.json()["requested_quantity"]) == 40 and Decimal(fulfilled.json()["fulfilled_quantity"]) == 35
    retry = client.post(f"/api/v1/stock-requests/{request_id}/fulfil", json={"fulfilled_quantity":35})
    assert retry.status_code == 200

    post_inventory(client, "returns", {"staff_id":str(b.id),"product_id":str(p3.id),"quantity":10,"reason":"Unsold route stock","idempotency_key":"recon-return"})
    post_inventory(client, "adjustments", {"product_id":str(p2.id),"quantity":5,"reason":"Verified warehouse count","idempotency_key":"recon-wh-adjust"})
    post_inventory(client, "adjustments", {"staff_id":str(c.id),"product_id":str(p3.id),"quantity":-2,"reason":"Damaged packets","idempotency_key":"recon-staff-adjust"})
    invalid = client.post("/api/v1/inventory/adjustments", json={"staff_id":str(c.id),"product_id":str(p3.id),"quantity":-1000,"reason":"Invalid negative test","idempotency_key":"recon-invalid-adjust"})
    assert invalid.status_code == 409

    expected_warehouse = {p1.id:Decimal("125"), p2.id:Decimal("125"), p3.id:Decimal("240")}
    expected_staff = {
        (a.id,p1.id):Decimal("100"),(a.id,p2.id):Decimal("26"),
        (b.id,p1.id):Decimal("53"),(b.id,p3.id):Decimal("70"),
        (c.id,p2.id):Decimal("44"),(c.id,p3.id):Decimal("55"),
    }
    login(client, "9000000001")
    warehouse = {row["product_id"]:Decimal(row["current_balance"]) for row in client.get("/api/v1/inventory/warehouse").json()}
    assert warehouse == {str(k):v for k,v in expected_warehouse.items()}
    overview = {(row["staff_id"],row["product_id"]):Decimal(row["current_balance"]) for row in client.get("/api/v1/inventory/staff-overview").json()}
    assert overview == {(str(s),str(p)):v for (s,p),v in expected_staff.items()}
    login(client, c.phone)
    my_stock = {row["product_id"]:Decimal(row["current_stock"]) for row in client.get("/api/v1/inventory/my-stock").json()}
    assert my_stock[str(p2.id)] == 44 and my_stock[str(p3.id)] == 55

    login(client, "9000000001")
    dashboard = client.get("/api/v1/dashboard/owner?period=this_month").json()
    kpis = dashboard["kpis"]
    assert Decimal(kpis["sales_today"]) == Decimal("714.25")
    assert Decimal(kpis["quantity_sold_today"]) == 65
    assert Decimal(kpis["sales_this_month"]) == Decimal("714.25")
    assert Decimal(kpis["stock_with_staff"]) == 348
    assert Decimal(kpis["warehouse_stock"]) == 490
    assert kpis["pending_stock_requests"] == 0
    assert Decimal(kpis["pending_payment_value"]) == Decimal("87.50")
    assert kpis["active_sales_staff"] == 3
    assert sum(Decimal(row["revenue"]) for row in dashboard["product_performance"]) == Decimal("714.25")
    assert sum(Decimal(row["contribution_percent"]) for row in dashboard["product_performance"]) == Decimal("100.00")
    assert sum(Decimal(row["sales_value"]) for row in dashboard["staff_performance"]) == Decimal("714.25")
    assert len(dashboard["retailer_insights"]["sales_by_district"]) == 3
    assert sum(Decimal(row["value"]) for row in dashboard["payments"]["by_method"]) == Decimal("714.25")

    report_names = ["sales","staff-sales","product-sales","retailer-sales","inventory-movements","stock-requests","pending-payments"]
    operating_date = business_today()
    reports = {name:csv_rows(client.get(f"/api/v1/reports/{name}.csv?date_from={operating_date}&date_to={operating_date}")) for name in report_names}
    assert len(reports["sales"]) == 6
    assert len(reports["staff-sales"]) == 3
    assert len(reports["product-sales"]) == 3
    assert len(reports["retailer-sales"]) == 6
    assert len(reports["inventory-movements"]) == 21
    assert len(reports["stock-requests"]) == 1
    assert len(reports["pending-payments"]) == 1
    assert sum(Decimal(row["Total"]) for row in reports["sales"]) == Decimal("714.25")
    assert any(row["Notes"] == "'=SUM(A1:A2)" for row in reports["sales"])
    assert reports["pending-payments"][0]["Pending Value"] == "87.50"

    with TestingSession() as db:
        assert db.scalar(select(func.count()).select_from(Sale)) == 6
        assert db.scalar(select(func.count()).select_from(SaleItem)) == 8
        assert db.scalar(select(func.count()).select_from(StockMovement)) == 21
        assert db.scalar(select(func.count()).select_from(StockMovement).where(StockMovement.reference_type == "stock_request")) == 1
        stored_request = db.get(StockRequest, uuid.UUID(request_id))
        assert stored_request.reviewed_by is not None and stored_request.reviewed_at is not None
        assert stored_request.fulfilled_by is not None and stored_request.fulfilled_at is not None
        movement_ids = [row.id for row in db.scalars(select(StockMovement)).all()]
        assert len(movement_ids) == len(set(movement_ids))


def test_launch_authorization_matrix(client):
    fixture = setup_working_day()
    staff = fixture["staff"][0]
    product = fixture["products"][0]
    login(client, staff.phone)
    assert client.get("/api/v1/dashboard/owner").status_code == 403
    assert client.get("/api/v1/reports/sales.csv").status_code == 403
    assert client.post("/api/v1/inventory/issues", json={"staff_id":str(staff.id),"product_id":str(product.id),"quantity":1,"idempotency_key":"staff-forbidden-issue"}).status_code == 403
    assert client.get("/api/v1/admin/users").status_code == 403
    assert client.get("/api/v1/payments/settings").status_code == 403
    login(client, "9000000003")
    assert client.get("/api/v1/operations/status").status_code == 200
    assert client.get("/api/v1/inventory/warehouse").status_code == 200
    assert client.get("/api/v1/dashboard/owner").status_code == 403
    assert client.get("/api/v1/reports/sales.csv").status_code == 403
    assert client.get("/api/v1/admin/users").status_code == 403
    assert client.get("/api/v1/payments/settings").status_code == 403
    client.cookies.clear()
    assert client.get("/api/v1/inventory/warehouse").status_code == 401


def test_business_date_uses_india_timezone_across_utc_midnight_boundary():
    assert business_today(datetime(2026, 8, 11, 18, 45, tzinfo=timezone.utc)).isoformat() == "2026-08-12"
    start, end = business_day_utc_bounds(business_today(datetime(2026, 8, 11, 18, 45, tzinfo=timezone.utc)))
    assert start.isoformat() == "2026-08-11T18:30:00+00:00"
    assert end.isoformat() == "2026-08-12T18:30:00+00:00"
