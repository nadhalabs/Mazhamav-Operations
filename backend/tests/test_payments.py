import io
import uuid
from datetime import date
from PIL import Image
from sqlalchemy import select
from app.core.rate_limit import reset_rate_limits_for_tests
from app.models import PaymentSettings, PaymentStatus, Product, Retailer, Sale, User
from tests.conftest import TestingSession


def login(client, phone="9000000001", password="Password123!"):
    client.cookies.clear()
    return client.post("/api/v1/auth/login", json={"phone": phone, "password": password})


def png_bytes():
    output = io.BytesIO()
    Image.new("RGB", (200, 200), "white").save(output, "PNG")
    return output.getvalue()


def configure_qr(client):
    assert login(client).status_code == 200
    return client.post("/api/v1/payments/settings", data={"display_name": "Mazha Mav Foods", "upi_id": "mazhamav@bank", "bank_reference": "Account ending 1234", "active": "true"}, files={"qr_image": ("qr.png", png_bytes(), "image/png")})


def pending_sale():
    with TestingSession() as db:
        staff = db.scalar(select(User).where(User.phone == "9000000002"))
        retailer = Retailer(shop_name="Payment Shop")
        product = Product(name="Payment Product", sku="PAY-1", unit_name="packet", selling_price=25)
        db.add_all([retailer, product]); db.flush()
        sale = Sale(sale_number="PAY-0001", idempotency_key="pay-sale-0001", staff_id=staff.id, retailer_id=retailer.id, sale_date=date.today(), subtotal=50, total=50, payment_status=PaymentStatus.pending)
        db.add(sale); db.commit(); db.refresh(sale)
        return str(sale.id), str(staff.id)


def test_owner_can_configure_and_staff_can_view_company_qr(client):
    response = configure_qr(client)
    assert response.status_code == 200
    assert response.json()["has_qr"] is True
    login(client, "9000000002")
    context = client.get("/api/v1/payments/qr-context")
    assert context.status_code == 200
    assert context.json()["display_name"] == "Mazha Mav Foods"
    image = client.get("/api/v1/payments/qr-image")
    assert image.status_code == 200 and image.headers["content-type"] == "image/png"


def test_staff_cannot_upload_or_replace_qr(client):
    login(client, "9000000002")
    response = client.post("/api/v1/payments/settings", data={"display_name": "Fake", "active": "true"}, files={"qr_image": ("qr.png", png_bytes(), "image/png")})
    assert response.status_code == 403
    with TestingSession() as db:
        assert db.scalar(select(PaymentSettings)) is None


def test_invalid_qr_upload_is_rejected(client):
    login(client)
    response = client.post("/api/v1/payments/settings", data={"display_name": "Mazha Mav", "active": "true"}, files={"qr_image": ("bad.png", b"not-an-image", "image/png")})
    assert response.status_code == 422


def test_displaying_sale_qr_does_not_mark_payment_paid(client):
    configure_qr(client); sale_id, _ = pending_sale(); login(client, "9000000002")
    context = client.get(f"/api/v1/payments/qr-context?sale_id={sale_id}")
    assert context.status_code == 200
    assert context.json()["amount_due"] == "50.00"
    with TestingSession() as db:
        assert db.get(Sale, uuid.UUID(sale_id)).payment_status == PaymentStatus.pending


def test_authorized_staff_can_mark_own_payment_received_with_audit(client):
    sale_id, staff_id = pending_sale(); login(client, "9000000002")
    response = client.post(f"/api/v1/payments/sales/{sale_id}/received", json={"payment_method": "upi"})
    assert response.status_code == 200
    body = response.json()
    assert body["payment_status"] == "paid"
    assert body["payment_received_by"] == staff_id
    assert body["payment_received_at"] is not None


def test_owner_or_manager_cannot_use_staff_payment_receipt_endpoint(client):
    sale_id, _ = pending_sale(); login(client)
    assert client.post(f"/api/v1/payments/sales/{sale_id}/received", json={"payment_method": "cash"}).status_code == 403


def test_login_failures_are_rate_limited(client):
    reset_rate_limits_for_tests()
    try:
        for _ in range(10):
            assert login(client, password="WrongPassword!").status_code == 401
        assert login(client, password="WrongPassword!").status_code == 429
    finally:
        reset_rate_limits_for_tests()
