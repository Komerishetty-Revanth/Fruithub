import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_customer
from app.models import User
from app.schemas.order import (
    CheckoutOut, CheckoutRequest, ManualUpiReferenceRequest, OrderOut, PaymentInfoOut,
)
from app.services import order_service

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("/checkout", response_model=CheckoutOut, status_code=201)
def checkout(data: CheckoutRequest, user: User = Depends(require_customer), db: Session = Depends(get_db)):
    """Validates address, stock and seller delivery; creates an order awaiting payment."""
    return order_service.place_order(db, user, data)


@router.get("", response_model=list[OrderOut])
def my_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    return order_service.list_orders(db, user, page, page_size)


@router.get("/{order_id}", response_model=OrderOut)
def my_order(order_id: uuid.UUID, user: User = Depends(require_customer), db: Session = Depends(get_db)):
    return order_service.get_order(db, user, order_id)


@router.post("/{order_id}/confirm-external-delivery", response_model=OrderOut)
def confirm_external_delivery(
    order_id: uuid.UUID, user: User = Depends(require_customer), db: Session = Depends(get_db),
):
    return order_service.confirm_external_delivery(db, user, order_id)


@router.post("/{order_id}/upi-reference", response_model=OrderOut)
def submit_upi_reference(
    order_id: uuid.UUID,
    data: ManualUpiReferenceRequest,
    user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    return order_service.submit_manual_upi_reference(db, user, order_id, data)


@router.get("/{order_id}/upi-payment", response_model=PaymentInfoOut)
def get_upi_payment(
    order_id: uuid.UUID,
    user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    return order_service.get_manual_upi_payment_info(db, user, order_id)


@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel(order_id: uuid.UUID, user: User = Depends(require_customer), db: Session = Depends(get_db)):
    return order_service.cancel_own_order(db, user, order_id)