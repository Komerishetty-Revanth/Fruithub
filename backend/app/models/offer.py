import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, Enum, ForeignKey,
    Numeric, String, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DiscountType(str, enum.Enum):
    PERCENTAGE = "PERCENTAGE"
    FIXED = "FIXED"


class Offer(Base):
    __tablename__ = "offers"
    __table_args__ = (
        CheckConstraint("discount_value > 0", name="ck_offer_value_positive"),
        CheckConstraint("ends_at > starts_at", name="ck_offer_dates_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id"), index=True
    )
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    discount_type: Mapped[DiscountType] = mapped_column(
        Enum(DiscountType, name="discount_type")
    )
    discount_value: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    min_order_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )