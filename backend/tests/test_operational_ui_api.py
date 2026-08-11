from decimal import Decimal
from sqlalchemy import select

from app.core.time import business_today
from app.models import MovementType, PaymentStatus, Product, Retailer, Sale, SaleItem, StockMovement, User
from tests.conftest import TestingSession


def login(client, phone="9000000001"):
    client.cookies.clear()
    return client.post("/api/v1/auth/login", json={"phone": phone, "password": "Password123!"})


def test_product_edit_status_and_historical_price_snapshot(client):
    login(client)
    created = client.post("/api/v1/admin/products", json={"name": "Dosa Flour 500g", "sku": "MM-500", "unit_name": "packet", "selling_price": "42.00"})
    assert created.status_code == 201
    product = created.json()
    updated = client.patch(f"/api/v1/admin/products/{product['id']}?active=false", json={"name": "Dosa Flour 500g New", "sku": "MM-500", "unit_name": "packet", "selling_price": "45.00"})
    assert updated.status_code == 200
    assert updated.json()["active"] is False and updated.json()["selling_price"] == "45.00"
    login(client, "9000000002")
    assert client.patch(f"/api/v1/admin/products/{product['id']}?active=true", json={"name": "No", "sku": "NO", "unit_name": "packet", "selling_price": "1"}).status_code == 403


def test_retailer_detail_reactivation_and_sales_are_preserved(client):
    with TestingSession() as db:
        staff = db.scalar(select(User).where(User.phone == "9000000002"))
        product = Product(name="Retail Detail Product", sku="RDP", unit_name="packet", selling_price=Decimal("10"))
        retailer = Retailer(shop_name="Detail Shop", active=False, area="Town")
        db.add_all([product, retailer]); db.flush()
        sale = Sale(sale_number="DETAIL-1", idempotency_key="detail-sale-key", staff_id=staff.id, retailer_id=retailer.id, sale_date=business_today(), subtotal=20, total=20, payment_status=PaymentStatus.pending)
        db.add(sale); db.flush(); db.add(SaleItem(sale_id=sale.id, product_id=product.id, quantity=2, unit_price_snapshot=10, line_total=20)); db.commit(); retailer_id=str(retailer.id)
    login(client)
    detail = client.get(f"/api/v1/retailers/{retailer_id}")
    assert detail.status_code == 200
    body=detail.json(); assert body["total_purchase_value"] == "20.00" and body["total_quantity"] == "2.000" and body["recent_sales"][0]["sale_number"] == "DETAIL-1"
    restored=client.patch(f"/api/v1/retailers/{retailer_id}", json={"active": True})
    assert restored.status_code == 200 and restored.json()["active"] is True
    assert client.get(f"/api/v1/retailers/{retailer_id}").json()["recent_sales"][0]["sale_number"] == "DETAIL-1"


def test_movement_history_filters_and_records_actor(client):
    with TestingSession() as db:
        owner=db.scalar(select(User).where(User.phone=="9000000001")); staff=db.scalar(select(User).where(User.phone=="9000000002"))
        product=Product(name="Ledger UI Product",sku="LEDGER-UI",unit_name="packet",selling_price=5);db.add(product);db.flush()
        db.add(StockMovement(product_id=product.id,staff_id=staff.id,movement_type=MovementType.issued_to_staff,quantity=4,created_by=owner.id,idempotency_key="ledger-ui-issue",notes="Pilot issue"));db.commit();product_id=str(product.id);staff_id=str(staff.id)
    login(client)
    rows=client.get(f"/api/v1/inventory/movements?product_id={product_id}&staff_id={staff_id}&movement_type=issued_to_staff").json()
    assert len(rows)==1 and rows[0]["product"]=="Ledger UI Product" and rows[0]["actor"]=="Owner" and rows[0]["notes"]=="Pilot issue"
    login(client,"9000000002")
    assert client.get("/api/v1/inventory/movements").status_code==403


def test_sale_detail_and_human_search_filters_respect_staff_scope(client):
    with TestingSession() as db:
        staff=db.scalar(select(User).where(User.phone=="9000000002")); product=Product(name="Sale Detail Product",sku="SALE-D",unit_name="packet",selling_price=12); retailer=Retailer(shop_name="Needle Retailer")
        db.add_all([product,retailer]);db.flush();sale=Sale(sale_number="MM-SEARCH-77",idempotency_key="sale-detail-key",staff_id=staff.id,retailer_id=retailer.id,sale_date=business_today(),subtotal=24,total=24,payment_status=PaymentStatus.paid);db.add(sale);db.flush();db.add(SaleItem(sale_id=sale.id,product_id=product.id,quantity=2,unit_price_snapshot=12,line_total=24));db.commit();sale_id=str(sale.id)
    login(client)
    assert client.get("/api/v1/sales?q=SEARCH-77&payment_status=paid").json()[0]["id"]==sale_id
    detail=client.get(f"/api/v1/sales/{sale_id}");assert detail.status_code==200 and detail.json()["items"][0]["unit_price_snapshot"]=="12.00"
    login(client,"9000000002");assert client.get(f"/api/v1/sales/{sale_id}").status_code==200
    login(client,"9000000003");assert client.get(f"/api/v1/sales/{sale_id}").status_code==200
