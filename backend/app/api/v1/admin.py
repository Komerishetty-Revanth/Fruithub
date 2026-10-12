import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models import OrderStatus, User, UserRole
from app.schemas.admin import (
    AdminOfferListOut, AdminOfferOut, AdminOrderListOut, AdminOrderOut, AdminStoreCreate,
    AdminStoreListOut, AdminStoreOut, AdminStoreUpdate, AdminUserListOut, AdminUserOut,
    AdminUserUpdate, OrderResolve, OwnerCreate,
)
from app.schemas.category import CategoryAdminOut, CategoryCreate, CategoryUpdate
from app.schemas.product import ProductListOut, ProductOut
from app.services import admin_service, category_service

router = APIRouter(prefix="/admin", tags=["Admin"])


# ---------- users ----------
@router.get("/users", response_model=AdminUserListOut)
def users(
    role: UserRole | None = None,
    q: str | None = Query(None, max_length=100, description="Search name or email"),
    is_active: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return admin_service.list_users(db, role, q, is_active, page, page_size)


@router.post("/owners", response_model=AdminUserOut, status_code=201)
def create_owner(data: OwnerCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return admin_service.create_owner(db, data)


@router.get("/users/{user_id}", response_model=AdminUserOut)
def user_detail(user_id: uuid.UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return admin_service.get_user(db, user_id)


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def edit_user(user_id: uuid.UUID, data: AdminUserUpdate,
              admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Activate, disable, rename, or change between CUSTOMER and OWNER."""
    return admin_service.update_user(db, admin, user_id, data)


# ---------- stores ----------
@router.get("/stores", response_model=AdminStoreListOut)
def stores(
    q: str | None = Query(None, max_length=100),
    is_approved: bool | None = None,
    is_active: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return admin_service.list_stores(db, q, is_approved, is_active, page, page_size)


@router.post("/stores", response_model=AdminStoreOut, status_code=201)
def create_store(data: AdminStoreCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return admin_service.create_store(db, data)


@router.get("/stores/{store_id}", response_model=AdminStoreOut)
def store_detail(store_id: uuid.UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return admin_service.get_store(db, store_id)


@router.patch("/stores/{store_id}", response_model=AdminStoreOut)
def edit_store(store_id: uuid.UUID, data: AdminStoreUpdate,
               admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Approve or disable a store, move its location, change its delivery radius."""
    return admin_service.update_store(db, store_id, data)


# ---------- categories ----------
@router.get("/categories", response_model=list[CategoryAdminOut])
def categories(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return category_service.list_all(db)


@router.post("/categories", response_model=CategoryAdminOut, status_code=201)
def add_category(data: CategoryCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return category_service.create_category(db, data.name, data.product_type)


@router.patch("/categories/{category_id}", response_model=CategoryAdminOut)
def edit_category(category_id: uuid.UUID, data: CategoryUpdate,
                  admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return category_service.update_category(db, category_id, data)


@router.delete("/categories/{category_id}")
def remove_category(category_id: uuid.UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    category_service.delete_category(db, category_id)
    return {"success": True}


# ---------- products ----------
@router.get("/products", response_model=ProductListOut)
def products(
    q: str | None = Query(None, max_length=100),
    store_id: uuid.UUID | None = None,
    category: str | None = Query(None, description="Category slug"),
    is_active: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return admin_service.list_products(db, q, store_id, category, is_active, page, page_size)


@router.post("/products/{product_id}/disable", response_model=ProductOut)
def disable_product(product_id: uuid.UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return admin_service.set_product_active(db, product_id, False)


@router.post("/products/{product_id}/enable", response_model=ProductOut)
def enable_product(product_id: uuid.UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return admin_service.set_product_active(db, product_id, True)


@router.delete("/products/{product_id}")
def remove_product(product_id: uuid.UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    admin_service.delete_product(db, product_id)
    return {"success": True}


# ---------- orders ----------
@router.get("/orders", response_model=AdminOrderListOut)
def orders(
    status: OrderStatus | None = None,
    store_id: uuid.UUID | None = None,
    q: str | None = Query(None, max_length=100, description="Order number, customer name or email"),
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return admin_service.list_orders(db, status, store_id, q, date_from, date_to, page, page_size)


@router.get("/orders/{order_id}", response_model=AdminOrderOut)
def order_detail(order_id: uuid.UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return admin_service.get_order(db, order_id)


@router.post("/orders/{order_id}/resolve", response_model=AdminOrderOut)
def resolve_order(order_id: uuid.UUID, data: OrderResolve,
                  admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Support override. Cancel and refund an order, or move it to another status. A note is required."""
    return admin_service.resolve_order(db, admin, order_id, data)


# ---------- offers ----------
@router.get("/offers", response_model=AdminOfferListOut)
def offers(
    store_id: uuid.UUID | None = None,
    live_only: bool = False,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return admin_service.list_offers(db, store_id, live_only)


@router.post("/offers/{offer_id}/disable", response_model=AdminOfferOut)
def disable_offer(offer_id: uuid.UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return admin_service.set_offer_active(db, offer_id, False)


@router.post("/offers/{offer_id}/enable", response_model=AdminOfferOut)
def enable_offer(offer_id: uuid.UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return admin_service.set_offer_active(db, offer_id, True)


# ---------- analytics ----------
@router.get("/analytics")
def analytics(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return admin_service.analytics(db)