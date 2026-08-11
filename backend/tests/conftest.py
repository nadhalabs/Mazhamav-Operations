import os
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_SECRET"] = "test-secret-at-least-32-characters-long"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models import User, UserRole

engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def database():
    Base.metadata.create_all(engine)
    with TestingSession() as db:
        db.add_all([User(full_name="Owner", phone="9000000001", password_hash=hash_password("Password123!"), role=UserRole.owner), User(full_name="Staff", phone="9000000002", password_hash=hash_password("Password123!"), role=UserRole.staff), User(full_name="Manager", phone="9000000003", password_hash=hash_password("Password123!"), role=UserRole.manager)])
        db.commit()
    yield
    Base.metadata.drop_all(engine)


def override_db():
    with TestingSession() as db:
        yield db

app.dependency_overrides[get_db] = override_db


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)

