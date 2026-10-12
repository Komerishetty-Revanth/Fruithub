import uuid
from enum import Enum

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProductType(str, Enum):
    FRUIT = "FRUIT"
    JUICE = "JUICE"
    DRY_FRUIT = "DRY_FRUIT"


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(80), unique=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    product_type: Mapped[str] = mapped_column(String(20), default=ProductType.FRUIT.value, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)