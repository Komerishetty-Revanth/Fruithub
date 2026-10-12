import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_orderitem_qty_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True
    )
    product_name: Mapped[str] = mapped_column(String(150))   # snapshot
    unit: Mapped[str] = mapped_column(String(20))            # snapshot
    variant_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # price actually charged per unit
    original_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    variant_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(10, 2))