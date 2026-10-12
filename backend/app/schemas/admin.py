import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.utils.phone import normalize_indian_phone

from app.models import OrderStatus
from app.schemas.offer import OfferOut
from app.schemas.order import OrderOut
from app.schemas.store import StoreOut


# ---------- users ----------
class AdminUserOut(BaseModel):
    id: str
    email: str
    full_name: str
    phone: str | None
    role: str
    is_active: bool
    store_id: str | None
    created_at: datetime


class AdminUserListOut(BaseModel):
    items: list[AdminUserOut]
    page: int
    page_size: int
    total: int


class OwnerCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=10, max_length=20)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, v: str) -> str:
        phone = normalize_indian_phone(v)
        if phone is None:
            raise ValueError("Enter a valid 10-digit Indian mobile number")
        return phone

    
class AdminUserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    is_active: bool | None = None
    role: str | None = Field(default=None, pattern="^(CUSTOMER|OWNER)$")


# ---------- stores ----------
class AdminStoreOut(StoreOut):
    owner_id: str
    owner_name: str
    owner_email: str
    product_count: int
    created_at: datetime


class AdminStoreListOut(BaseModel):
    items: list[AdminStoreOut]
    page: int
    page_size: int
    total: int


class AdminStoreCreate(BaseModel):
    owner_id: uuid.UUID
    name: str = Field(min_length=2, max_length=150)
    address: str | None = Field(default=None, max_length=300)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    delivery_radius_km: float = Field(default=5.0, gt=0, le=50)
    fssai_number: str | None = Field(default=None, max_length=50)
    is_approved: bool = False


class AdminStoreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    address: str | None = Field(default=None, max_length=300)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    delivery_radius_km: float | None = Field(default=None, gt=0, le=50)
    fssai_number: str | None = Field(default=None, max_length=50)
    is_approved: bool | None = None
    is_active: bool | None = None


# ---------- orders ----------
class AdminOrderOut(OrderOut):
    customer_name: str
    customer_email: str
    customer_phone: str | None
    store_id: str
    store_name: str


class AdminOrderListOut(BaseModel):
    items: list[AdminOrderOut]
    page: int
    page_size: int
    total: int


class OrderResolve(BaseModel):
    status: OrderStatus
    note: str = Field(min_length=3, max_length=255)


# ---------- offers ----------
class AdminOfferOut(OfferOut):
    store_name: str


class AdminOfferListOut(BaseModel):
    items: list[AdminOfferOut]