import os

# Must happen BEFORE the app is imported, so tests never touch the real database.
os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://fruithub:fruithub_dev_pw@localhost:5433/fruithub_test"
)
os.environ["PAYMENT_PROVIDER"] = "mock"
os.environ["OTP_DEV_MODE"] = "true"
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-tests-only-0123456789")

from types import SimpleNamespace
from decimal import Decimal
from itertools import count

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import app.models  # noqa: F401
from app.core.database import Base, SessionLocal, engine
from app.core.rate_limit import limiter
from app.core.security import hash_password
from app.main import app
from app.models import Category, Product, Store, User, UserRole

assert "test" in engine.url.database, "Refusing to run tests on a non-test database"

limiter.enabled = False
PASSWORD = "Passw0rd!123"
_phone_counter = count(1)


@pytest.fixture(scope="session", autouse=True)
def create_schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture(autouse=True)
def clean_db():
    with engine.begin() as conn:
        names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
        conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    yield


def _user(db, email, role, name):
    phone = f"+9199999{next(_phone_counter):05d}"
    u = User(email=email, full_name=name, role=role, phone=phone, phone_verified=True,
             password_hash=hash_password(PASSWORD))
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def world():
    """Admin, two owners with a store each, two customers, one product per store.
    Store A is at (17.35, 78.55). Store B is at (17.60, 78.80)."""
    db = SessionLocal()
    try:
        admin = _user(db, "admin@t.dev", UserRole.ADMIN, "Admin")
        oa = _user(db, "owner_a@t.dev", UserRole.OWNER, "Owner A")
        ob = _user(db, "owner_b@t.dev", UserRole.OWNER, "Owner B")
        c1 = _user(db, "cust1@t.dev", UserRole.CUSTOMER, "Customer One")
        c2 = _user(db, "cust2@t.dev", UserRole.CUSTOMER, "Customer Two")
        sa = Store(owner_id=oa.id, name="Store A", latitude=17.35, longitude=78.55,
                   delivery_radius_km=5.0, is_approved=True)
        sb = Store(owner_id=ob.id, name="Store B", latitude=17.60, longitude=78.80,
                   delivery_radius_km=5.0, is_approved=True)
        cat = Category(name="Mango", slug="mango")
        db.add_all([sa, sb, cat])
        db.flush()
        pa = Product(store_id=sa.id, category_id=cat.id, name="Test Mango",
                     price=Decimal("100"), unit="kg", stock_quantity=Decimal("10"))
        pb = Product(store_id=sb.id, category_id=cat.id, name="Other Apple",
                     price=Decimal("200"), unit="kg", stock_quantity=Decimal("10"))
        db.add_all([pa, pb])
        db.commit()
        return SimpleNamespace(
            admin=admin.email, owner_a=oa.email, owner_b=ob.email,
            cust1=c1.email, cust2=c2.email,
            store_a=str(sa.id), store_b=str(sb.id), category=str(cat.id),
            product_a=str(pa.id), product_b=str(pb.id),
        )
    finally:
        db.close()


@pytest.fixture
def client():
    return TestClient(app)   # no "with": the background expiry loop is not started


@pytest.fixture
def login(client):
    def _login(email):
        r = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}
    return _login


@pytest.fixture
def address(client):
    def _make(headers, lat=17.39, lng=78.55, complete=True):
        body = {"latitude": lat, "longitude": lng}
        if complete:
            body.update(line1="12 Test Street", city="Hyderabad", pincode="500001")
        r = client.post("/api/v1/addresses", json=body, headers=headers)
        assert r.status_code == 201, r.text
        return r.json()["id"]
    return _make


@pytest.fixture
def checkout(client, address):
    """Adds the product to the cart and tries to check out. Returns the response."""
    def _go(headers, product_id, qty=2, lat=17.39, lng=78.55):
        r = client.post("/api/v1/cart/items",
                        json={"product_id": product_id, "quantity": qty}, headers=headers)
        assert r.status_code == 200, r.text
        aid = address(headers, lat, lng)
        return client.post("/api/v1/orders/checkout", json={"address_id": aid}, headers=headers)
    return _go


@pytest.fixture
def stock(client):
    def _stock(product_id):
        return float(client.get(f"/api/v1/products/{product_id}").json()["stock_quantity"])
    return _stock