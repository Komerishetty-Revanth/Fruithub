from pydantic import BaseModel, Field


class CategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    product_type: str = Field(default="FRUIT", pattern="^(FRUIT|JUICE|DRY_FRUIT)$")


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    product_type: str | None = Field(default=None, pattern="^(FRUIT|JUICE|DRY_FRUIT)$")
    is_active: bool | None = None


class CategoryAdminOut(BaseModel):
    id: str
    name: str
    slug: str
    product_type: str
    is_active: bool
    product_count: int