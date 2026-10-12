import uuid
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProductVariant(Base):
    __tablename__ = "product_variants"
    __table_args__ = (
        UniqueConstraint("product_id", "label", name="uq_product_variant_label"),
        CheckConstraint("size_value >= 0", name="ck_variant_size_nonneg"),
        CheckConstraint("price >= 0", name="ck_variant_price_nonneg"),
        CheckConstraint(
            "discount_price IS NULL OR (discount_price >= 0 AND discount_price <= price)",
            name="ck_variant_discount_valid",
        ),
        CheckConstraint("stock_quantity >= 0", name="ck_variant_stock_nonneg"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(50))
    size_value: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    size_unit: Mapped[str] = mapped_column(String(20))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    discount_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    stock_quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
