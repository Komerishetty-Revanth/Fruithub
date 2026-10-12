import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class CartItemAdd(BaseModel):
    product_id: uuid.UUID
    variant_id: uuid.UUID | None = None
    quantity: Decimal = Field(gt=0, le=50, max_digits=6, decimal_places=2)


class CartItemUpdate(BaseModel):
    quantity: Decimal = Field(gt=0, le=50, max_digits=6, decimal_places=2)


class CartItemOut(BaseModel):
    product_id: str
    variant_id: str | None = None
    name: str
    unit: str
    image_url: str | None
    asset_3d_url: str | None = None
    original_price: Decimal
    unit_price: Decimal
    quantity: Decimal
    line_total: Decimal
    available_stock: Decimal
    is_available: bool
    issue: str | None


class CartOut(BaseModel):
    store_id: str | None
    items: list[CartItemOut]
    item_count: int
    subtotal: Decimal
    discount_total: Decimal
    delivery_fee: Decimal
    total: Decimal
    has_issues: bool