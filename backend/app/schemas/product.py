from decimal import Decimal

from pydantic import BaseModel


class CategoryOut(BaseModel):
    id: str
    name: str
    slug: str
    product_type: str


class ProductOut(BaseModel):
    id: str
    store_id: str
    store_name: str
    category: CategoryOut
    name: str
    description: str | None
    origin: str | None = None
    nutrition: str | None = None
    ingredients: str | None = None
    allergens: str | None = None
    is_veg: bool | None = None
    shelf_life_days: int | None = None
    best_before: str | None = None
    storage_note: str | None = None
    sugar_info: str | None = None
    is_made_to_order: bool = False
    price: Decimal
    discount_price: Decimal | None
    final_price: Decimal
    discount_percent: int
    unit: str
    stock_quantity: Decimal
    image_url: str | None
    asset_3d_url: str | None
    is_available: bool
    is_active: bool = True
    rating: float
    rating_count: int


class ProductListOut(BaseModel):
    items: list[ProductOut]
    page: int
    page_size: int
    total: int