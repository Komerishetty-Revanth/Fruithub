from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models import OrderStatus
from app.schemas.order import OrderOut


class OrderStatusChange(BaseModel):
    status: OrderStatus
    note: str | None = Field(default=None, max_length=255)


class OwnerOrderOut(OrderOut):
    customer_name: str
    customer_phone: str | None
    allowed_next: list[str]


class OwnerOrderListOut(BaseModel):
    items: list[OwnerOrderOut]
    page: int
    page_size: int
    total: int


class ManualPaymentOut(BaseModel):
    order_id: str
    order_number: str
    customer_name: str
    amount: Decimal
    transaction_reference: str
    submitted_at: datetime


class ManualPaymentReject(BaseModel):
    note: str | None = Field(default=None, max_length=255)