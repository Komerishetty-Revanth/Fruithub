import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Category, Inventory, Product, Store, User
from app.schemas.owner import (
    InventoryListOut, InventoryOut, ProductCreate, ProductUpdate, StockAdjust,
)
from app.schemas.product import ProductListOut, ProductOut
from app.schemas.store import OwnerStoreUpdate, StoreOut
from app.services.product_service import to_product_out


def get_owner_store(db: Session, user: User) -> Store:
    store = db.scalar(select(Store).where(Store.owner_id == user.id))
    if store is None:
        raise AppError("STORE_NOT_FOUND", "You do not have a store yet.", 404)
    return store


def _get_category(db: Session, category_id: uuid.UUID) -> Category:
    cat = db.scalar(
        select(Category).where(Category.id == category_id, Category.is_active.is_(True))
    )
    if cat is None:
        raise AppError("CATEGORY_NOT_FOUND", "This category does not exist.", 404)
    return cat


def _get_owned_product(db: Session, store: Store, product_id: uuid.UUID, lock=False) -> Product:
    # The store_id filter is the security rule: owners only ever see their own products.
    stmt = select(Product).where(Product.id == product_id, Product.store_id == store.id)
    if lock:
        stmt = stmt.with_for_update()
    p = db.scalar(stmt)
    if p is None:
        raise AppError("PRODUCT_NOT_FOUND", "This product was not found.", 404)
    return p


def _out(db: Session, p: Product, store: Store) -> ProductOut:
    return to_product_out(p, db.get(Category, p.category_id), store)


# ---------- products ----------

def list_products(db: Session, user: User, page: int, page_size: int) -> ProductListOut:
    store = get_owner_store(db, user)
    total = db.scalar(select(func.count(Product.id)).where(Product.store_id == store.id))
    rows = db.scalars(
        select(Product).where(Product.store_id == store.id)
        .order_by(Product.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return ProductListOut(
        items=[_out(db, p, store) for p in rows],
        page=page, page_size=page_size, total=total or 0,
    )


def get_product(db: Session, user: User, product_id: uuid.UUID) -> ProductOut:
    store = get_owner_store(db, user)
    return _out(db, _get_owned_product(db, store, product_id), store)


def create_product(db: Session, user: User, data: ProductCreate) -> ProductOut:
    store = get_owner_store(db, user)
    category = _get_category(db, data.category_id)
    p = Product(
        store_id=store.id, category_id=category.id, name=data.name.strip(),
        description=data.description, origin=data.origin, nutrition=data.nutrition,
        ingredients=data.ingredients, allergens=data.allergens,
        is_veg=data.is_veg, shelf_life_days=data.shelf_life_days,
        best_before=data.best_before.date() if data.best_before else None,
        storage_note=data.storage_note, sugar_info=data.sugar_info,
        is_made_to_order=data.is_made_to_order,
        price=data.price, discount_price=data.discount_price, unit=data.unit,
        stock_quantity=data.stock_quantity, is_available=data.is_available,
    )
    db.add(p)
    db.flush()
    if p.stock_quantity > 0:
        db.add(Inventory(
            product_id=p.id, change_quantity=p.stock_quantity,
            reason="RESTOCK", note="Initial stock", created_by=user.id,
        ))
    db.commit()
    db.refresh(p)
    return _out(db, p, store)


def update_product(db: Session, user: User, product_id: uuid.UUID, data: ProductUpdate) -> ProductOut:
    store = get_owner_store(db, user)
    p = _get_owned_product(db, store, product_id)
    changes = data.model_dump(exclude_unset=True)

    for field in ("name", "category_id", "price", "unit", "is_available"):
        if field in changes and changes[field] is None:
            raise AppError("VALIDATION_ERROR", f"{field} cannot be empty.", 422)

    if "category_id" in changes:
        _get_category(db, changes["category_id"])
    for field in ("name", "description", "origin", "nutrition", "ingredients", "allergens",
                  "is_veg", "shelf_life_days", "best_before", "storage_note", "sugar_info",
                  "is_made_to_order", "category_id", "price", "discount_price", "unit", "is_available"):
        if field in changes:
            value = changes[field]
            if field == "name":
                value = value.strip()
            if field == "best_before" and value is not None:
                value = value.date()
            setattr(p, field, value)

    if p.discount_price is not None and p.discount_price > p.price:
        db.rollback()
        raise AppError("INVALID_DISCOUNT", "Discount price cannot be more than the price.", 422)

    db.commit()
    db.refresh(p)
    return _out(db, p, store)


def set_active(db: Session, user: User, product_id: uuid.UUID, active: bool) -> ProductOut:
    store = get_owner_store(db, user)
    p = _get_owned_product(db, store, product_id)
    p.is_active = active
    db.commit()
    db.refresh(p)
    return _out(db, p, store)


def adjust_stock(db: Session, user: User, product_id: uuid.UUID, data: StockAdjust) -> ProductOut:
    store = get_owner_store(db, user)
    # lock=True locks this row until commit, so two changes can't collide
    p = _get_owned_product(db, store, product_id, lock=True)
    new_stock = p.stock_quantity + data.change_quantity
    if new_stock < 0:
        db.rollback()
        raise AppError("INSUFFICIENT_STOCK", "Stock cannot go below zero.", 422)
    p.stock_quantity = new_stock
    db.add(Inventory(
        product_id=p.id, change_quantity=data.change_quantity,
        reason=data.reason, note=data.note, created_by=user.id,
    ))
    db.commit()
    db.refresh(p)
    return _out(db, p, store)


# ---------- inventory history ----------

def list_inventory(db: Session, user: User, product_id: uuid.UUID | None,
                   page: int, page_size: int) -> InventoryListOut:
    store = get_owner_store(db, user)
    filters = [Product.store_id == store.id]
    if product_id:
        filters.append(Inventory.product_id == product_id)
    total = db.scalar(
        select(func.count(Inventory.id)).join(Product, Inventory.product_id == Product.id)
        .where(*filters)
    ) or 0
    rows = db.execute(
        select(Inventory, Product.name).join(Product, Inventory.product_id == Product.id)
        .where(*filters).order_by(Inventory.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return InventoryListOut(
        items=[
            InventoryOut(
                id=str(i.id), product_id=str(i.product_id), product_name=name,
                change_quantity=i.change_quantity, reason=i.reason, note=i.note,
                created_at=i.created_at,
            ) for i, name in rows
        ],
        page=page, page_size=page_size, total=total,
    )


# ---------- store settings ----------

def _store_out(s: Store) -> StoreOut:
    return StoreOut(
        id=str(s.id), name=s.name, address=s.address, latitude=s.latitude,
        longitude=s.longitude, delivery_radius_km=s.delivery_radius_km,
        fssai_number=s.fssai_number, upi_vpa=s.upi_vpa,
        is_approved=s.is_approved, is_active=s.is_active,
    )


def get_store_settings(db: Session, user: User) -> StoreOut:
    return _store_out(get_owner_store(db, user))


def update_store_settings(db: Session, user: User, data: OwnerStoreUpdate) -> StoreOut:
    store = get_owner_store(db, user)
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes:
        if not changes["name"] or not changes["name"].strip():
            raise AppError("VALIDATION_ERROR", "Store name cannot be empty.", 422)
        store.name = changes["name"].strip()
    if "address" in changes:
        store.address = (changes["address"] or "").strip() or None
    if "upi_vpa" in changes:
        store.upi_vpa = (changes["upi_vpa"] or "").strip() or None
    db.commit()
    db.refresh(store)
    return _store_out(store)