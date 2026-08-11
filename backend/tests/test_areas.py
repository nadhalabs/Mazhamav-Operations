from datetime import date
from decimal import Decimal
from sqlalchemy import select
from app.models import PaymentMethod, PaymentStatus, Product, Retailer, Sale, SaleItem, User
from app.schemas.sales import RetailerIn
from tests.conftest import TestingSession


def login(client, phone="9000000001"):
    client.cookies.clear()
    assert client.post("/api/v1/auth/login", json={"phone": phone, "password": "Password123!"}).status_code == 200


def test_location_values_are_normalized():
    retailer = RetailerIn(shop_name="Shop", city="  kochi  ", area="  kakkanad   east ", district="ernakulam")
    assert (retailer.city, retailer.area, retailer.district) == ("Kochi", "Kakkanad East", "Ernakulam")


def test_area_metrics_reconcile_and_remain_owner_only(client):
    with TestingSession() as db:
        staff = db.scalar(select(User).where(User.phone == "9000000002"))
        product = Product(name="Area Product", sku="AREA-1", unit_name="packet", selling_price=10)
        retailer = Retailer(shop_name="Area Shop", district="Ernakulam", city="Kochi", area="Kakkanad")
        db.add_all([product, retailer]); db.flush()
        sale = Sale(sale_number="AREA-SALE", idempotency_key="area-sale-key", staff_id=staff.id, retailer_id=retailer.id, sale_date=date.today(), subtotal=30, total=30, payment_status=PaymentStatus.paid, payment_method=PaymentMethod.cash)
        db.add(sale); db.flush()
        db.add(SaleItem(sale_id=sale.id, product_id=product.id, quantity=3, unit_price_snapshot=10, line_total=30)); db.commit()
    login(client)
    response = client.get("/api/v1/areas?period=today")
    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["summary"]["sales_value"]) == 30
    assert Decimal(data["summary"]["quantity_sold"]) == 3
    assert data["areas"][0]["name"] == "Kakkanad"
    detail = client.get("/api/v1/areas/detail?area=Kakkanad&period=today").json()
    assert detail["products"][0]["quantity"] == "3.000"
    login(client, "9000000002")
    assert client.get("/api/v1/areas").status_code == 403
