import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models import PaymentMethod


class CheckoutRequest(BaseModel):
    address_id: uuid.UUID
    accept_self_delivery: bool = False
    payment_method: PaymentMethod = PaymentMethod.ONLINE


class ManualUpiReferenceRequest(BaseModel):
    transaction_reference: str = Field(
        min_length=6, max_length=50, pattern=r"^[A-Za-z0-9/-]+$"
    )


class PaymentConfirmRequest(BaseModel):
    provider_order_id: str = Field(max_length=100)
    provider_payment_id: str = Field(max_length=100)
    signature: str = Field(max_length=200)


class OrderItemOut(BaseModel):
    product_id: str | None
    variant_id: str | None = None
    name: str
    unit: str
    variant_label: str | None = None
    original_price: Decimal
    unit_price: Decimal
    quantity: Decimal
    line_total: Decimal


class StatusEventOut(BaseModel):
    status: str
    note: str | None
    created_at: datetime


class OrderOut(BaseModel):
    id: str
    order_number: str
    status: str
    payment_status: str
    payment_method: str
    items: list[OrderItemOut]
    subtotal: Decimal
    discount_total: Decimal
    delivery_fee: Decimal
    total: Decimal
    delivery_line1: str
    delivery_line2: str | None
    delivery_city: str
    delivery_pincode: str
    distance_km: float
    seller_delivery_available: bool
    created_at: datetime
    pay_before: datetime | None      # only while waiting for payment
    history: list[StatusEventOut]


class PaymentInfoOut(BaseModel):
    provider: str
    provider_order_id: str | None
    amount: Decimal
    currency: str
    upi_vpa: str | None = None
    payee_name: str | None = None
    payment_uri: str | None = None
    reference_submitted: bool = False
    pay_before: datetime | None = None


class CheckoutOut(BaseModel):
    order: OrderOut
    payment: PaymentInfoOut