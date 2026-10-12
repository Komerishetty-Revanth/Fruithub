"""
DEVELOPMENT SEED DATA ONLY.
The passwords below are for local testing. Never use them in production.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import (
    Category, DiscountType, Offer, OfferProduct, Product, Store, User, UserRole,
)

# Store location (sample point). Change to your real area later.
STORE_LAT, STORE_LNG = 17.3500, 78.5500

# email, name, role, password, phone (all marked verified for development)
USERS = [
    ("admin@fruithub.dev", "Platform Admin", UserRole.ADMIN, "Admin@12345", "+919999900001"),
    ("owner@fruithub.dev", "Store Owner", UserRole.OWNER, "Owner@12345", "+919999900002"),
    ("customer@fruithub.dev", "Test Customer", UserRole.CUSTOMER, "Customer@12345", "+919999900003"),
]

CATEGORIES = [
    "Mango", "Apple", "Banana", "Citrus", "Berries",
    "Melons", "Grapes", "Pomegranate", "Tropical", "Seasonal",
]

# name, category, price, discount_price, stock
FRUITS = [
    ("Alphonso Mango", "Mango", "180", "149", "50"),
    ("Kashmir Apple", "Apple", "240", None, "40"),
    ("Nagpur Orange", "Citrus", "90", "75", "60"),
    ("Robusta Banana", "Banana", "50", None, "80"),
    ("Black Grapes", "Grapes", "120", "99", "35"),
    ("Watermelon", "Melons", "30", None, "100"),
    ("Pomegranate", "Pomegranate", "200", "170", "30"),
    ("Papaya", "Tropical", "45", None, "50"),
    ("Pineapple", "Tropical", "70", None, "45"),
]


def slugify(text: str) -> str:
    return text.lower().replace(" ", "-")


def run():
    db = SessionLocal()
    try:
        if db.scalar(select(User).where(User.email == "admin@fruithub.dev")):
            print("Seed data already exists. Nothing to do.")
            return

        users = {}
        for email, name, role, pw, phone in USERS:
            u = User(email=email, full_name=name, role=role, phone=phone,
                     phone_verified=True, password_hash=hash_password(pw))
            db.add(u)
            users[role] = u
        db.flush()

        store = Store(
            owner_id=users[UserRole.OWNER].id,
            name="FruitHub Central",
            address="Sample address, Hyderabad",
            latitude=STORE_LAT,
            longitude=STORE_LNG,
            delivery_radius_km=5.0,
            is_approved=True,
        )
        db.add(store)

        cats = {}
        for name in CATEGORIES:
            c = Category(name=name, slug=slugify(name))
            db.add(c)
            cats[name] = c
        db.flush()

        products = {}
        for name, cat, price, disc, stock in FRUITS:
            p = Product(
                store_id=store.id,
                category_id=cats[cat].id,
                name=name,
                description=f"Fresh {name}, picked and delivered the same day.",
                price=Decimal(price),
                discount_price=Decimal(disc) if disc else None,
                unit="kg",
                stock_quantity=Decimal(stock),
            )
            db.add(p)
            products[name] = p
        db.flush()

        now = datetime.now(timezone.utc)
        mango_offer = Offer(
            store_id=store.id,
            title="Mango Mania: 20% off",
            discount_type=DiscountType.PERCENTAGE,
            discount_value=Decimal("20"),
            starts_at=now - timedelta(days=1),
            ends_at=now + timedelta(days=30),
        )
        flat_offer = Offer(
            store_id=store.id,
            title="Flat Rs 50 off on orders above Rs 500",
            discount_type=DiscountType.FIXED,
            discount_value=Decimal("50"),
            min_order_amount=Decimal("500"),
            starts_at=now - timedelta(days=1),
            ends_at=now + timedelta(days=30),
        )
        db.add_all([mango_offer, flat_offer])
        db.flush()
        db.add(OfferProduct(offer_id=mango_offer.id, product_id=products["Alphonso Mango"].id))

        db.commit()
        print("Seed complete.")
        print("Dev logins:")
        for email, _, role, pw, phone in USERS:
            print(f"  {role.value:9} {email}  /  {pw}   phone {phone}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()