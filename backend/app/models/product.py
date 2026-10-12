import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey,
    Integer, Numeric, String, Text, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_product_price_nonneg"),
        CheckConstraint(
            "discount_price IS NULL OR (discount_price >= 0 AND discount_price <= price)",
            name="ck_product_discount_valid",
        ),
        CheckConstraint("stock_quantity >= 0", name="ck_product_stock_nonneg"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id"), index=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(150), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    origin: Mapped[str | None] = mapped_column(String(150), nullable=True)
    nutrition: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingredients: Mapped[str | None] = mapped_column(Text, nullable=True)
    allergens: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_veg: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    shelf_life_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    best_before: Mapped[date | None] = mapped_column(Date, nullable=True)
    storage_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    sugar_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_made_to_order: Mapped[bool] = mapped_column(Boolean, default=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    discount_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    unit: Mapped[str] = mapped_column(String(20), default="kg")
    stock_quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    asset_3d_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    rating: Mapped[float] = mapped_column(Float, default=0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )