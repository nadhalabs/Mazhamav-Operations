from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import select
from app.models import MovementType, PaymentMethod, PaymentStatus, Product, RequestStatus, Retailer, Sale, SaleItem, StockMovement, StockRequest, User
from tests.conftest import TestingSession


def login(client, phone="9000000001"):
    client.cookies.clear()
    assert client.post("/api/v1/auth/login", json={"phone": phone, "password": "Password123!"}).status_code == 200


def dashboard_fixture():
    with TestingSession() as db:
        owner = db.scalar(select(User).where(User.phone == "9000000001"))
        staff = db.scalar(select(User).where(User.phone == "9000000002"))
        product = Product(name="Dashboard Product", sku="DASH-1", unit_name="packet", selling_price=10)
        retailer_a = Retailer(shop_name="Retailer A", area="North", district="One")
        retailer_b = Retailer(shop_name="Retailer B", area="South", district="Two")
        db.add_all([product, retailer_a, retailer_b]); db.flush()
        today = date.today(); yesterday = today - timedelta(days=1)
        sale_today = Sale(sale_number="DASH-TODAY", idempotency_key="dashboard-today", staff_id=staff.id, retailer_id=retailer_a.id, sale_date=today, subtotal=20, total=20, payment_status=PaymentStatus.paid, payment_method=PaymentMethod.cash)
        sale_yesterday = Sale(sale_number="DASH-YESTERDAY", idempotency_key="dashboard-yesterday", staff_id=staff.id, retailer_id=retailer_b.id, sale_date=yesterday, subtotal=30, total=30, payment_status=PaymentStatus.pending)
        db.add_all([sale_today, sale_yesterday]); db.flush()
        db.add_all([SaleItem(sale_id=sale_today.id, product_id=product.id, quantity=2, unit_price_snapshot=10, line_total=20), SaleItem(sale_id=sale_yesterday.id, product_id=product.id, quantity=3, unit_price_snapshot=10, line_total=30)])
        db.add_all([
            StockMovement(product_id=product.id, movement_type=MovementType.warehouse_in, quantity=100, created_by=owner.id, idempotency_key="dash-wh-in"),
            StockMovement(product_id=product.id, staff_id=staff.id, movement_type=MovementType.issued_to_staff, quantity=20, created_by=owner.id, idempotency_key="dash-issue"),
            StockMovement(product_id=product.id, staff_id=staff.id, movement_type=MovementType.staff_sale, quantity=2, created_by=staff.id, reference_type="sale", reference_id=sale_today.id, idempotency_key="dash-sale-1"),
            StockMovement(product_id=product.id, staff_id=staff.id, movement_type=MovementType.staff_sale, quantity=3, created_by=staff.id, reference_type="sale", reference_id=sale_yesterday.id, idempotency_key="dash-sale-2"),
            StockRequest(staff_id=staff.id, product_id=product.id, requested_quantity=5, status=RequestStatus.pending),
        ])
        db.commit()


def test_owner_dashboard_core_metrics_reconcile(client):
    dashboard_fixture(); login(client)
    response = client.get("/api/v1/dashboard/owner?period=last_7_days")
    assert response.status_code == 200
    data = response.json(); kpis = data["kpis"]
    assert Decimal(kpis["sales_today"]) == 20
    assert Decimal(kpis["sales_yesterday"]) == 30
    assert Decimal(kpis["quantity_sold_today"]) == 2
    assert Decimal(kpis["stock_with_staff"]) == 15
    assert Decimal(kpis["warehouse_stock"]) == 80
    assert kpis["pending_stock_requests"] == 1
    assert Decimal(kpis["pending_payment_value"]) == 30
    assert kpis["active_sales_staff"] == 1


def test_dashboard_breakdowns_match_sales_and_do_not_double_count(client):
    dashboard_fixture(); login(client)
    data = client.get("/api/v1/dashboard/owner?period=last_7_days").json()
    product = data["product_performance"][0]
    assert Decimal(product["quantity_sold"]) == 5
    assert Decimal(product["revenue"]) == 50
    assert Decimal(product["contribution_percent"]) == 100
    staff = data["staff_performance"][0]
    assert Decimal(staff["sales_value"]) == 50
    assert Decimal(staff["quantity_sold"]) == 5
    assert staff["retailers_served"] == 2
    assert Decimal(staff["current_stock"]) == 15
    assert data["payments"]["paid"]["count"] == 1
    assert data["payments"]["pending"]["count"] == 1


def test_trend_is_complete_and_reconciles_to_selected_period(client):
    dashboard_fixture(); login(client)
    data = client.get("/api/v1/dashboard/owner?period=last_7_days").json()
    assert len(data["sales_trend"]) == 7
    assert sum((Decimal(row["sales_value"]) for row in data["sales_trend"]), Decimal("0")) == 50


def test_dashboard_and_exports_are_owner_only(client):
    dashboard_fixture(); login(client, "9000000002")
    assert client.get("/api/v1/dashboard/owner").status_code == 403
    assert client.get("/api/v1/reports/sales.csv").status_code == 403


def test_csv_reports_have_authoritative_rows(client):
    dashboard_fixture(); login(client)
    sales = client.get("/api/v1/reports/sales.csv")
    assert sales.status_code == 200
    assert "DASH-TODAY" in sales.text and "DASH-YESTERDAY" in sales.text
    product = client.get("/api/v1/reports/product-sales.csv")
    assert product.status_code == 200
    assert "Dashboard Product,DASH-1,5.000,50.00" in product.text
    pending = client.get("/api/v1/reports/pending-payments.csv")
    assert "DASH-YESTERDAY" in pending.text and "DASH-TODAY" not in pending.text


def test_invalid_custom_dashboard_range_is_rejected(client):
    login(client)
    assert client.get("/api/v1/dashboard/owner?period=custom&date_from=2026-08-10&date_to=2026-08-01").status_code == 422
