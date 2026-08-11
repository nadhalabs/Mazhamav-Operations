from decimal import Decimal
from sqlalchemy import select
from app.models import Product, StockMovement, User
from tests.conftest import TestingSession


def login(client, phone):
    assert client.post("/api/v1/auth/login", json={"phone": phone, "password": "Password123!"}).status_code == 200


def setup_ids():
    with TestingSession() as db:
        product = Product(name="Classic", sku="CLASSIC", unit_name="packet", selling_price=120)
        db.add(product); db.commit(); db.refresh(product)
        staff = db.scalar(select(User).where(User.phone == "9000000002"))
        return str(product.id), str(staff.id)


def post(client, path, body):
    return client.post(f"/api/v1/inventory/{path}", json=body)


def test_issue_and_staff_balance(client):
    product_id, staff_id = setup_ids(); login(client, "9000000001")
    assert post(client, "warehouse-in", {"product_id": product_id, "quantity": 20, "idempotency_key": "receive-0001"}).status_code == 201
    response = post(client, "issues", {"product_id": product_id, "staff_id": staff_id, "quantity": 7, "idempotency_key": "issue-000001"})
    assert response.status_code == 201
    overview = client.get("/api/v1/inventory/staff-overview").json()[0]
    assert Decimal(overview["total_issued"]) == 7
    assert Decimal(overview["current_balance"]) == 7
    warehouse = client.get("/api/v1/inventory/warehouse").json()[0]
    assert Decimal(warehouse["current_balance"]) == 13


def test_insufficient_warehouse_stock(client):
    product_id, staff_id = setup_ids(); login(client, "9000000001")
    response = post(client, "issues", {"product_id": product_id, "staff_id": staff_id, "quantity": 1, "idempotency_key": "issue-empty01"})
    assert response.status_code == 409
    assert "Insufficient warehouse" in response.json()["error"]["message"]


def test_return_updates_both_balances(client):
    product_id, staff_id = setup_ids(); login(client, "9000000001")
    post(client, "warehouse-in", {"product_id": product_id, "quantity": 10, "idempotency_key": "receive-0002"})
    post(client, "issues", {"product_id": product_id, "staff_id": staff_id, "quantity": 8, "idempotency_key": "issue-000002"})
    assert post(client, "returns", {"product_id": product_id, "staff_id": staff_id, "quantity": 3, "reason": "Unsold stock", "idempotency_key": "return-00001"}).status_code == 201
    assert Decimal(client.get("/api/v1/inventory/staff-overview").json()[0]["current_balance"]) == 5
    assert Decimal(client.get("/api/v1/inventory/warehouse").json()[0]["current_balance"]) == 5


def test_adjustments_require_reason_and_never_go_negative(client):
    product_id, staff_id = setup_ids(); login(client, "9000000001")
    assert post(client, "adjustments", {"product_id": product_id, "quantity": 5, "reason": "Opening count", "idempotency_key": "adjust-00001"}).status_code == 201
    assert post(client, "adjustments", {"product_id": product_id, "quantity": -6, "reason": "Count correction", "idempotency_key": "adjust-00002"}).status_code == 409
    assert post(client, "adjustments", {"product_id": product_id, "quantity": 0, "reason": "Invalid", "idempotency_key": "adjust-00003"}).status_code == 422


def test_staff_cannot_post_movements_but_can_view_own_stock(client):
    product_id, staff_id = setup_ids(); login(client, "9000000002")
    body = {"product_id": product_id, "staff_id": staff_id, "quantity": 1, "idempotency_key": "staff-issue01"}
    assert post(client, "issues", body).status_code == 403
    assert client.get("/api/v1/inventory/my-stock").status_code == 200


def test_owner_cannot_use_staff_only_stock_endpoint(client):
    setup_ids(); login(client, "9000000001")
    assert client.get("/api/v1/inventory/my-stock").status_code == 403


def test_duplicate_issue_is_idempotent(client):
    product_id, staff_id = setup_ids(); login(client, "9000000001")
    post(client, "warehouse-in", {"product_id": product_id, "quantity": 10, "idempotency_key": "receive-0003"})
    body = {"product_id": product_id, "staff_id": staff_id, "quantity": 4, "idempotency_key": "duplicate-issue"}
    first = post(client, "issues", body); second = post(client, "issues", body)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    with TestingSession() as db:
        assert len(db.scalars(select(StockMovement).where(StockMovement.idempotency_key == "duplicate-issue")).all()) == 1


def test_manager_can_issue_stock(client):
    product_id, staff_id = setup_ids(); login(client, "9000000003")
    post(client, "warehouse-in", {"product_id": product_id, "quantity": 3, "idempotency_key": "manager-in01"})
    assert post(client, "issues", {"product_id": product_id, "staff_id": staff_id, "quantity": 2, "idempotency_key": "manager-is01"}).status_code == 201
