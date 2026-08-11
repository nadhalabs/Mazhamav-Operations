from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.security import verify_password
from app.core.time import business_today
from app.models import MovementType, PaymentStatus, Product, RequestStatus, Retailer, Sale, SaleItem, StockMovement, StockRequest, User, UserRole
from tests.conftest import TestingSession


PASSWORD = "Password123!"


def login(client, phone="9000000001", password=PASSWORD):
    client.cookies.clear()
    return client.post("/api/v1/auth/login", json={"phone": phone, "password": password})


def user_payload(phone, role="staff", password="DirectPass123!"):
    return {"full_name": f"New {role.title()}", "phone": phone, "password": password, "role": role, "active": True}


def test_owner_creates_staff_and_manager_with_immediate_login_and_secure_hash(client):
    assert login(client).status_code == 200
    staff = client.post("/api/v1/admin/users", json=user_payload("9555000001"))
    manager = client.post("/api/v1/admin/users", json=user_payload("9555000002", "manager"))
    assert staff.status_code == manager.status_code == 201
    assert "password" not in staff.text and "password_hash" not in staff.text
    with TestingSession() as db:
        stored = db.scalar(select(User).where(User.phone == "9555000001"))
        assert stored.password_hash != "DirectPass123!"
        assert verify_password("DirectPass123!", stored.password_hash)
    assert login(client, "9555000001", "DirectPass123!").status_code == 200
    assert login(client, "9555000002", "DirectPass123!").status_code == 200


def test_duplicate_phone_edit_and_role_rules(client):
    login(client)
    created = client.post("/api/v1/admin/users", json=user_payload("9555000010")).json()
    assert client.post("/api/v1/admin/users", json=user_payload("9555000010", "manager")).status_code == 409
    updated = client.patch(f"/api/v1/admin/users/{created['id']}", json={"full_name":"Edited Staff","phone":"9555000011","role":"manager","active":True})
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Edited Staff" and updated.json()["role"] == "manager"
    assert client.patch(f"/api/v1/admin/users/{created['id']}", json={"full_name":"Bad","phone":"9555000011","role":"owner","active":True}).status_code == 422


def test_password_reset_replaces_password_and_requires_confirmation(client):
    login(client)
    created = client.post("/api/v1/admin/users", json=user_payload("9555000020")).json()
    assert client.post(f"/api/v1/admin/users/{created['id']}/password", json={"new_password":"ChangedPass123!","confirm_password":"Different123!"}).status_code == 422
    reset = client.post(f"/api/v1/admin/users/{created['id']}/password", json={"new_password":"ChangedPass123!","confirm_password":"ChangedPass123!"})
    assert reset.status_code == 204
    assert login(client, "9555000020", "DirectPass123!").status_code == 401
    assert login(client, "9555000020", "ChangedPass123!").status_code == 200


def test_disable_preserves_history_blocks_login_and_reenable_restores_access(client):
    login(client)
    created = client.post("/api/v1/admin/users", json=user_payload("9555000030")).json()
    url = f"/api/v1/admin/users/{created['id']}"
    assert login(client, "9555000030", "DirectPass123!").status_code == 200
    active_session = client.cookies.get("access_token")
    login(client)
    disabled = client.patch(url, json={"full_name":"New Staff","phone":"9555000030","role":"staff","active":False})
    assert disabled.status_code == 200 and disabled.json()["active"] is False
    assert login(client, "9555000030", "DirectPass123!").status_code == 401
    client.cookies.set("access_token", active_session)
    assert client.get("/api/v1/inventory/my-stock").status_code == 401
    login(client)
    assert client.patch(url, json={"full_name":"New Staff","phone":"9555000030","role":"staff","active":True}).status_code == 200
    assert login(client, "9555000030", "DirectPass123!").status_code == 200


def test_staff_and_manager_cannot_manage_users_or_view_staff_module(client):
    login(client, "9000000002")
    assert client.post("/api/v1/admin/users", json=user_payload("9555000040")).status_code == 403
    assert client.get("/api/v1/admin/staff").status_code == 403
    login(client, "9000000003")
    assert client.post("/api/v1/admin/users", json=user_payload("9555000041")).status_code == 403
    assert client.get("/api/v1/admin/staff").status_code == 403


def test_staff_profile_performance_and_stock_are_authoritative(client):
    with TestingSession() as db:
        owner = db.scalar(select(User).where(User.phone == "9000000001"))
        staff = db.scalar(select(User).where(User.phone == "9000000002"))
        product_a = Product(name="Staff Product A", sku="STAFF-A", unit_name="packet", selling_price=Decimal("10"))
        product_b = Product(name="Staff Product B", sku="STAFF-B", unit_name="packet", selling_price=Decimal("4.50"))
        retailer = Retailer(shop_name="Staff Retailer", district="Kozhikode")
        db.add_all([product_a, product_b, retailer]); db.flush()
        today = business_today()
        sale = Sale(sale_number="STAFF-PERF-1", idempotency_key="staff-perf-1", staff_id=staff.id, retailer_id=retailer.id, sale_date=today, subtotal=Decimal("29"), total=Decimal("29"), payment_status=PaymentStatus.pending)
        old_sale = Sale(sale_number="STAFF-PERF-OLD", idempotency_key="staff-perf-old", staff_id=staff.id, retailer_id=retailer.id, sale_date=today-timedelta(days=10), subtotal=Decimal("10"), total=Decimal("10"), payment_status=PaymentStatus.paid)
        db.add_all([sale, old_sale]); db.flush()
        db.add_all([
            SaleItem(sale_id=sale.id, product_id=product_a.id, quantity=2, unit_price_snapshot=10, line_total=20),
            SaleItem(sale_id=sale.id, product_id=product_b.id, quantity=2, unit_price_snapshot=Decimal("4.50"), line_total=9),
            SaleItem(sale_id=old_sale.id, product_id=product_a.id, quantity=1, unit_price_snapshot=10, line_total=10),
            StockMovement(product_id=product_a.id, staff_id=staff.id, movement_type=MovementType.issued_to_staff, quantity=10, created_by=owner.id, idempotency_key="staff-profile-issue-a"),
            StockMovement(product_id=product_b.id, staff_id=staff.id, movement_type=MovementType.issued_to_staff, quantity=8, created_by=owner.id, idempotency_key="staff-profile-issue-b"),
            StockMovement(product_id=product_a.id, staff_id=staff.id, movement_type=MovementType.staff_sale, quantity=3, created_by=staff.id, idempotency_key="staff-profile-sale-a"),
            StockMovement(product_id=product_b.id, staff_id=staff.id, movement_type=MovementType.staff_sale, quantity=2, created_by=staff.id, idempotency_key="staff-profile-sale-b"),
            StockRequest(staff_id=staff.id, product_id=product_a.id, requested_quantity=5, status=RequestStatus.pending),
        ])
        db.commit(); staff_id = str(staff.id)
    login(client)
    detail = client.get(f"/api/v1/admin/staff/{staff_id}?period=last_7_days")
    assert detail.status_code == 200
    body = detail.json(); performance = body["performance"]
    assert Decimal(performance["sales_today"]) == 29
    assert Decimal(performance["sales_this_week"]) == 29
    assert Decimal(performance["sales_this_month"]) == 39
    assert Decimal(performance["quantity_sold"]) == 4
    assert Decimal(performance["sales_value"]) == 29
    assert performance["retailers_served"] == 1
    assert Decimal(performance["pending_payment_value"]) == 29
    assert Decimal(performance["current_stock"]) == 13
    assert performance["pending_stock_requests"] == 1
    stock = {row["product"]:Decimal(row["current_stock"]) for row in body["stock"]}
    assert stock["Staff Product A"] == 7 and stock["Staff Product B"] == 6
    assert sum(Decimal(row["revenue"]) for row in body["product_performance"]) == 29
    assert body["retailer_activity"][0]["sales_value"] == "29.00"
    assert len(body["recent_sales"]) == 2 and len(body["stock_requests"]) == 1
    listing = client.get("/api/v1/admin/staff?q=Staff&role=staff&active=true").json()
    row = next(item for item in listing if item["id"] == staff_id)
    assert Decimal(row["current_stock"]) == 13 and Decimal(row["sales_today"]) == 29


def test_staff_profile_custom_range_uses_business_dates(client):
    with TestingSession() as db:
        staff = db.scalar(select(User).where(User.phone == "9000000002"))
        staff_id = str(staff.id)
    today = business_today()
    login(client)
    assert client.get(f"/api/v1/admin/staff/{staff_id}?period=custom&date_from={today}&date_to={today}").status_code == 200
    assert client.get(f"/api/v1/admin/staff/{staff_id}?period=custom&date_from={today}&date_to=2020-01-01").status_code == 422
