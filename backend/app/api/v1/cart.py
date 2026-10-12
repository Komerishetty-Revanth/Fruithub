import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_customer
from app.models import User
from app.schemas.cart import CartItemAdd, CartItemUpdate, CartOut
from app.services import cart_service

router = APIRouter(prefix="/cart", tags=["Cart"])


@router.get("", response_model=CartOut)
def view_cart(user: User = Depends(require_customer), db: Session = Depends(get_db)):
    return cart_service.get_cart(db, user)


@router.post("/items", response_model=CartOut)
def add_to_cart(data: CartItemAdd, user: User = Depends(require_customer), db: Session = Depends(get_db)):
    return cart_service.add_item(db, user, data)


@router.patch("/items/{product_id}", response_model=CartOut)
def change_quantity(product_id: uuid.UUID, data: CartItemUpdate,
                    variant_id: uuid.UUID | None = None,
                    user: User = Depends(require_customer), db: Session = Depends(get_db)):
    return cart_service.update_item(db, user, product_id, data, variant_id)


@router.delete("/items/{product_id}", response_model=CartOut)
def remove_from_cart(product_id: uuid.UUID, variant_id: uuid.UUID | None = None,
                    user: User = Depends(require_customer), db: Session = Depends(get_db)):
    return cart_service.remove_item(db, user, product_id, variant_id)


@router.delete("", response_model=CartOut)
def clear(user: User = Depends(require_customer), db: Session = Depends(get_db)):
    return cart_service.clear_cart(db, user)