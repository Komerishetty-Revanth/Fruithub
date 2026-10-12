import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_owner
from app.models import User
from app.schemas.category import CategoryAdminOut, CategoryCreate
from app.schemas.owner import InventoryListOut
from app.schemas.store import OwnerStoreUpdate, StoreOut
from app.services import category_service, owner_service

router = APIRouter(prefix="/owner", tags=["Owner"])


@router.get("/store", response_model=StoreOut)
def my_store(user: User = Depends(require_owner), db: Session = Depends(get_db)):
    return owner_service.get_store_settings(db, user)


@router.patch("/store", response_model=StoreOut)
def edit_store(data: OwnerStoreUpdate, user: User = Depends(require_owner), db: Session = Depends(get_db)):
    """Update store profile and UPI details; the admin controls location and delivery radius."""
    return owner_service.update_store_settings(db, user, data)


@router.post("/categories", response_model=CategoryAdminOut, status_code=201)
def add_category(data: CategoryCreate, user: User = Depends(require_owner), db: Session = Depends(get_db)):
    return category_service.create_category(db, data.name)


@router.get("/inventory", response_model=InventoryListOut)
def inventory_history(
    product_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    """Every stock change: restocks, orders, cancellations, adjustments."""
    return owner_service.list_inventory(db, user, product_id, page, page_size)