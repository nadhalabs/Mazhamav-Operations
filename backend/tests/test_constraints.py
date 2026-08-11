from decimal import Decimal
import pytest
from sqlalchemy.exc import IntegrityError
from app.models import Product, StockRequest, User
from tests.conftest import TestingSession


def test_duplicate_sku_rejected():
    with TestingSession() as db:
        db.add_all([Product(name="A", sku="ONE", unit_name="packet", selling_price=1), Product(name="B", sku="ONE", unit_name="packet", selling_price=2)])
        with pytest.raises(IntegrityError):
            db.commit()


def test_stock_request_quantity_must_be_positive():
    with TestingSession() as db:
        user = db.query(User).first()
        product = Product(name="A", sku="A", unit_name="packet", selling_price=1)
        db.add(product); db.flush()
        db.add(StockRequest(staff_id=user.id, product_id=product.id, requested_quantity=Decimal("0")))
        with pytest.raises(IntegrityError):
            db.commit()
