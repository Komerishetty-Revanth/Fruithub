import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


WHOLE_NUMBER_UNITS = {"piece", "dozen", "bottle", "pack"}
VALID_UNITS = {"kg", "g", "piece", "dozen", "ml", "l", "bottle", "pack"}


def _validate_unit_amount(value: Decimal | None, unit: str | None) -> None:
    if unit is None or value is None:
        return
    if unit in WHOLE_NUMBER_UNITS and value != value.to_integral_value():
        raise ValueError(f"Quantity must be a whole number for {unit}.")


class ProductCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    origin: str | None = Field(default=None, max_length=150)
    nutrition: str | None = Field(default=None, max_length=2000)
    ingredients: str | None = Field(default=None, max_length=2000)
    allergens: str | None = Field(default=None, max_length=2000)
    is_veg: bool | None = None
    shelf_life_days: int | None = Field(default=None, ge=1)
    best_before: datetime | None = None
    storage_note: str | None = Field(default=None, max_length=2000)
    sugar_info: str | None = Field(default=None, max_length=255)
    is_made_to_order: bool = False
    category_id: uuid.UUID
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    discount_price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    unit: str = Field(default="kg", pattern="^(kg|g|piece|dozen|ml|l|bottle|pack)$")
    stock_quantity: Decimal = Field(default=Decimal("0"), ge=0, max_digits=10, decimal_places=2)
    is_available: bool = True

    @model_validator(mode="after")
    def check_discount(self):
        if self.discount_price is not None and self.discount_price > self.price:
            raise ValueError("discount_price cannot be more than price")
        _validate_unit_amount(self.stock_quantity, self.unit)
        return self


class ProductUpdate(BaseModel):
    """Send only the fields you want to change. Stock is changed through /stock."""
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    origin: str | None = Field(default=None, max_length=150)
    nutrition: str | None = Field(default=None, max_length=2000)
    ingredients: str | None = Field(default=None, max_length=2000)
    allergens: str | None = Field(default=None, max_length=2000)
    is_veg: bool | None = None
    shelf_life_days: int | None = Field(default=None, ge=1)
    best_before: datetime | None = None
    storage_note: str | None = Field(default=None, max_length=2000)
    sugar_info: str | None = Field(default=None, max_length=255)
    is_made_to_order: bool | None = None
    category_id: uuid.UUID | None = None
    price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    discount_price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    unit: str | None = Field(default=None, pattern="^(kg|g|piece|dozen|ml|l|bottle|pack)$")
    is_available: bool | None = None

    @model_validator(mode="after")
    def check_discount(self):
        if self.discount_price is not None and self.price is not None and self.discount_price > self.price:
            raise ValueError("discount_price cannot be more than price")
        if self.unit is not None and self.stock_quantity is not None:
            _validate_unit_amount(self.stock_quantity, self.unit)
        return self


class StockAdjust(BaseModel):
    change_quantity: Decimal = Field(max_digits=10, decimal_places=2)  # + adds, - removes
    reason: str = Field(default="RESTOCK", pattern="^(RESTOCK|ADJUSTMENT)$")
    note: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def not_zero(self):
        if self.change_quantity == 0:
            raise ValueError("change_quantity cannot be zero")
        return self


class InventoryOut(BaseModel):
    id: str
    product_id: str
    product_name: str
    change_quantity: Decimal
    reason: str
    note: str | None
    created_at: datetime


class InventoryListOut(BaseModel):
    items: list[InventoryOut]
    page: int
    page_size: int
    total: int