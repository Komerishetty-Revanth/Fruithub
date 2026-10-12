import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_customer
from app.models import User
from app.schemas.order import OrderOut, PaymentConfirmRequest
from app.services import order_service

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("/confirm", response_model=OrderOut)
def confirm(data: PaymentConfirmRequest, user: User = Depends(require_customer), db: Session = Depends(get_db)):
    """Used by real gateways. The signature is verified on the server."""
    return order_service.confirm_payment(
        db, user, data.provider_order_id, data.provider_payment_id, data.signature
    )


@router.post("/mock/{order_id}/pay", response_model=OrderOut)
def mock_pay(order_id: uuid.UUID, user: User = Depends(require_customer), db: Session = Depends(get_db)):
    """Development only: pretends to be the gateway and completes the payment."""
    return order_service.mock_pay(db, user, order_id)