import uuid
from decimal import Decimal
from sqlalchemy import func, select
from app.models import MovementType, Product, RequestStatus, StockMovement, StockRequest, User
from tests.conftest import TestingSession


def login(client, phone):
    client.cookies.clear()
    assert client.post("/api/v1/auth/login", json={"phone": phone, "password": "Password123!"}).status_code == 200


def setup_product():
    with TestingSession() as db:
        product = Product(name="Request Product", sku="REQ-1", unit_name="packet", selling_price=10)
        db.add(product); db.commit(); db.refresh(product)
        staff = db.scalar(select(User).where(User.phone == "9000000002"))
        return str(product.id), str(staff.id)


def create_request(client, product_id, quantity=5):
    login(client, "9000000002")
    return client.post("/api/v1/stock-requests", json={"product_id": product_id, "requested_quantity": quantity, "notes": "Need more stock"})


def add_warehouse_stock(client, product_id, quantity=20):
    login(client, "9000000001")
    return client.post("/api/v1/inventory/warehouse-in", json={"product_id": product_id, "quantity": quantity, "idempotency_key": f"request-warehouse-{quantity}"})


def test_request_creation_and_staff_listing(client):
    product_id, _ = setup_product()
    response = create_request(client, product_id)
    assert response.status_code == 201
    mine = client.get("/api/v1/stock-requests/mine").json()
    assert len(mine) == 1
    assert mine[0]["status"] == "pending"
    assert mine[0]["product_name"] == "Request Product"


def test_duplicate_open_request_prevented(client):
    product_id, _ = setup_product()
    assert create_request(client, product_id).status_code == 201
    assert client.post("/api/v1/stock-requests", json={"product_id": product_id, "requested_quantity": 2}).status_code == 409


def test_approve_and_reject_transitions_are_audited(client):
    product_id, _ = setup_product()
    first = create_request(client, product_id).json()
    login(client, "9000000001")
    approved = client.post(f"/api/v1/stock-requests/{first['id']}/approve", json={"note": "Approved for route"})
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["reviewed_by"] is not None
    assert approved.json()["review_notes"] == "Approved for route"

    login(client, "9000000002")
    # An approved request remains open, so another cannot be created yet.
    assert client.post("/api/v1/stock-requests", json={"product_id": product_id, "requested_quantity": 1}).status_code == 409
    with TestingSession() as db:
        second_product = Product(name="Second Request Product", sku="REQ-2", unit_name="packet", selling_price=10)
        db.add(second_product); db.commit(); db.refresh(second_product)
        second_product_id = str(second_product.id)
    second = client.post("/api/v1/stock-requests", json={"product_id": second_product_id, "requested_quantity": 3}).json()
    login(client, "9000000003")
    rejected = client.post(f"/api/v1/stock-requests/{second['id']}/reject", json={"note": "Not required"})
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"


def test_fulfilment_uses_explicit_quantity_and_posts_movement(client):
    product_id, staff_id = setup_product()
    request = create_request(client, product_id, 8).json()
    add_warehouse_stock(client, product_id, 20)
    response = client.post(f"/api/v1/stock-requests/{request['id']}/fulfil", json={"fulfilled_quantity": 6})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "fulfilled"
    assert Decimal(body["fulfilled_quantity"]) == 6
    assert body["fulfilled_by"] is not None and body["fulfilled_at"] is not None
    with TestingSession() as db:
        movement = db.scalar(select(StockMovement).where(StockMovement.reference_type == "stock_request"))
        assert movement.movement_type == MovementType.issued_to_staff
        assert Decimal(movement.quantity) == 6
        assert str(movement.staff_id) == staff_id


def test_insufficient_warehouse_rolls_back_status_and_movement(client):
    product_id, _ = setup_product()
    request = create_request(client, product_id, 10).json()
    add_warehouse_stock(client, product_id, 3)
    response = client.post(f"/api/v1/stock-requests/{request['id']}/fulfil", json={})
    assert response.status_code == 409
    with TestingSession() as db:
        stored = db.get(StockRequest, uuid.UUID(request["id"]))
        assert stored.status == RequestStatus.pending
        assert stored.fulfilled_quantity is None
        assert db.scalar(select(func.count()).select_from(StockMovement).where(StockMovement.reference_type == "stock_request")) == 0


def test_fulfilment_updates_staff_and_warehouse_balances(client):
    product_id, _ = setup_product()
    request = create_request(client, product_id, 4).json()
    add_warehouse_stock(client, product_id, 10)
    assert client.post(f"/api/v1/stock-requests/{request['id']}/fulfil", json={}).status_code == 200
    warehouse = client.get("/api/v1/inventory/warehouse").json()[0]
    assert Decimal(warehouse["current_balance"]) == 6
    login(client, "9000000002")
    assert Decimal(client.get("/api/v1/inventory/my-stock").json()[0]["current_stock"]) == 4


def test_staff_cannot_review_or_fulfil_and_owner_cannot_create(client):
    product_id, _ = setup_product()
    request = create_request(client, product_id).json()
    assert client.post(f"/api/v1/stock-requests/{request['id']}/approve", json={}).status_code == 403
    assert client.post(f"/api/v1/stock-requests/{request['id']}/fulfil", json={}).status_code == 403
    login(client, "9000000001")
    assert client.post("/api/v1/stock-requests", json={"product_id": product_id, "requested_quantity": 1}).status_code == 403


def test_fulfilment_retry_is_idempotent(client):
    product_id, _ = setup_product()
    request = create_request(client, product_id, 2).json()
    add_warehouse_stock(client, product_id, 5)
    url = f"/api/v1/stock-requests/{request['id']}/fulfil"
    first = client.post(url, json={}); second = client.post(url, json={})
    assert first.status_code == second.status_code == 200
    with TestingSession() as db:
        assert db.scalar(select(func.count()).select_from(StockMovement).where(StockMovement.reference_id == uuid.UUID(request["id"]))) == 1
