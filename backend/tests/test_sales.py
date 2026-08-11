from decimal import Decimal
from sqlalchemy import func, select
from app.models import MovementType, Product, Retailer, Sale, SaleItem, StockMovement, User
from tests.conftest import TestingSession


def login(client, phone):
    client.cookies.clear()
    assert client.post("/api/v1/auth/login", json={"phone": phone, "password": "Password123!"}).status_code == 200


def setup_inventory(client, products):
    with TestingSession() as db:
        rows = [Product(name=name, sku=sku, unit_name="packet", selling_price=price) for name, sku, price in products]
        db.add_all(rows); db.commit()
        staff = db.scalar(select(User).where(User.phone == "9000000002"))
        ids = [(str(p.id), price) for p, (_, _, price) in zip(rows, products)]
        staff_id = str(staff.id)
    login(client, "9000000001")
    for index, (product_id, _) in enumerate(ids):
        client.post("/api/v1/inventory/warehouse-in", json={"product_id": product_id, "quantity": 20, "idempotency_key": f"sales-stock-in-{index}"})
        client.post("/api/v1/inventory/issues", json={"product_id": product_id, "staff_id": staff_id, "quantity": 10, "idempotency_key": f"sales-issue---{index}"})
    retailer = client.post("/api/v1/retailers", json={"shop_name": "Green Stores", "contact_name": "Ravi", "phone": "9876543210", "area": "Town"}).json()
    login(client, "9000000002")
    return ids, staff_id, retailer["id"]


def sale_payload(retailer_id, items, key="sale-test-0001"):
    return {"retailer_id": retailer_id, "items": items, "payment_status": "paid", "payment_method": "cash", "notes": "Counter sale", "idempotency_key": key, "total": "0.01"}


def test_successful_sale_total_and_stock_deduction(client):
    products, _, retailer_id = setup_inventory(client, [("Classic", "SC-1", Decimal("12.50"))])
    product_id = products[0][0]
    response = client.post("/api/v1/sales", json=sale_payload(retailer_id, [{"product_id": product_id, "quantity": 3}]))
    assert response.status_code == 201
    body = response.json()
    assert Decimal(body["total"]) == Decimal("37.50")
    assert Decimal(body["items"][0]["unit_price_snapshot"]) == Decimal("12.50")
    assert Decimal(client.get("/api/v1/inventory/my-stock").json()[0]["current_stock"]) == 7


def test_multi_item_sale_calculation(client):
    products, _, retailer_id = setup_inventory(client, [("A", "MULTI-A", Decimal("10.00")), ("B", "MULTI-B", Decimal("2.25"))])
    items = [{"product_id": products[0][0], "quantity": 2}, {"product_id": products[1][0], "quantity": 4}]
    response = client.post("/api/v1/sales", json=sale_payload(retailer_id, items, "sale-multi-001"))
    assert response.status_code == 201
    assert Decimal(response.json()["total"]) == Decimal("29.00")
    assert len(response.json()["items"]) == 2


def test_insufficient_stock_rolls_back_entire_sale(client):
    products, _, retailer_id = setup_inventory(client, [("A", "ROLL-A", Decimal("10")), ("B", "ROLL-B", Decimal("5"))])
    items = [{"product_id": products[0][0], "quantity": 2}, {"product_id": products[1][0], "quantity": 11}]
    response = client.post("/api/v1/sales", json=sale_payload(retailer_id, items, "sale-rollback1"))
    assert response.status_code == 409
    with TestingSession() as db:
        assert db.scalar(select(func.count()).select_from(Sale)) == 0
        assert db.scalar(select(func.count()).select_from(SaleItem)) == 0
        assert db.scalar(select(func.count()).select_from(StockMovement).where(StockMovement.movement_type == MovementType.staff_sale)) == 0


def test_duplicate_sale_does_not_double_deduct(client):
    products, _, retailer_id = setup_inventory(client, [("A", "DUP-A", Decimal("8"))])
    body = sale_payload(retailer_id, [{"product_id": products[0][0], "quantity": 2}], "sale-duplicate")
    first = client.post("/api/v1/sales", json=body); second = client.post("/api/v1/sales", json=body)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert Decimal(client.get("/api/v1/inventory/my-stock").json()[0]["current_stock"]) == 8


def test_owner_cannot_record_sale_but_can_view_all_history(client):
    products, _, retailer_id = setup_inventory(client, [("A", "ROLE-A", Decimal("8"))])
    client.post("/api/v1/sales", json=sale_payload(retailer_id, [{"product_id": products[0][0], "quantity": 1}], "sale-role-001"))
    login(client, "9000000001")
    assert client.post("/api/v1/sales", json=sale_payload(retailer_id, [{"product_id": products[0][0], "quantity": 1}], "sale-role-002")).status_code == 403
    assert len(client.get("/api/v1/sales").json()) == 1


def test_staff_can_create_retailer_during_sale(client):
    products, _, _ = setup_inventory(client, [("A", "RET-A", Decimal("8"))])
    body = {"new_retailer": {"shop_name": "New Shop", "district": "Kozhikode"}, "items": [{"product_id": products[0][0], "quantity": 1}], "payment_status": "pending", "idempotency_key": "sale-new-retailer"}
    assert client.post("/api/v1/sales", json=body).status_code == 201
    assert any(r["shop_name"] == "New Shop" for r in client.get("/api/v1/retailers?q=New").json())


def test_staff_cannot_edit_or_deactivate_retailer(client):
    products, _, retailer_id = setup_inventory(client, [("A", "EDIT-A", Decimal("8"))])
    assert client.patch(f"/api/v1/retailers/{retailer_id}", json={"shop_name": "Changed"}).status_code == 403
    assert client.delete(f"/api/v1/retailers/{retailer_id}").status_code == 403
