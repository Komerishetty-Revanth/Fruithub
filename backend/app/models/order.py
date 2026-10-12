import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, Enum, Float, ForeignKey, Numeric, String, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OrderStatus(str, enum.Enum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PLACED = "PLACED"
    CONFIRMED = "CONFIRMED"
    PACKING = "PACKING"
    READY_FOR_DELIVERY = "READY_FOR_DELIVERY"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class PaymentMethod(str, enum.Enum):
    ONLINE = "ONLINE"
    UPI_MANUAL = "UPI_MANUAL"


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("total >= 0", name="ck_order_total_nonneg"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id"), index=True
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"),
        default=OrderStatus.PENDING_PAYMENT,
        index=True,
    )
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method"), default=PaymentMethod.ONLINE
    )
    payment_status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status"), default=PaymentStatus.PENDING
    )

    # Address snapshot (copied at order time)
    delivery_line1: Mapped[str] = mapped_column(String(200))
    delivery_line2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    delivery_city: Mapped[str] = mapped_column(String(100))
    delivery_pincode: Mapped[str] = mapped_column(String(10))
    delivery_latitude: Mapped[float] = mapped_column(Float)
    delivery_longitude: Mapped[float] = mapped_column(Float)
    distance_km: Mapped[float] = mapped_column(Float)
    seller_delivery_available: Mapped[bool] = mapped_column(Boolean, default=True)

    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    discount_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )