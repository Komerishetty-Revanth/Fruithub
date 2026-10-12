import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models import DiscountType
from app.schemas.product import ProductOut


class OfferCreate(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    description: str | None = Field(default=None, max_length=300)
    discount_type: DiscountType
    discount_value: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    min_order_amount: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    starts_at: datetime
    ends_at: datetime
    product_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def check_values(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        if self.discount_type == DiscountType.PERCENTAGE and self.discount_value > 100:
            raise ValueError("Percentage cannot be more than 100")
        return self


class OfferUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=150)
    description: str | None = Field(default=None, max_length=300)
    discount_value: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    min_order_amount: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    product_ids: list[uuid.UUID] | None = Field(default=None, max_length=100)


class OfferOut(BaseModel):
    id: str
    store_id: str
    title: str
    description: str | None
    discount_type: str
    discount_value: Decimal
    min_order_amount: Decimal | None
    starts_at: datetime
    ends_at: datetime
    is_active: bool
    is_live: bool
    product_ids: list[str]


class OfferListOut(BaseModel):
    items: list[OfferOut]


class TodaysOffersOut(BaseModel):
    offers: list[OfferOut]
    products: list[ProductOut]