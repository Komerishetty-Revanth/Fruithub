from pydantic import BaseModel, Field


class StoreOut(BaseModel):
    id: str
    name: str
    address: str | None
    latitude: float
    longitude: float
    delivery_radius_km: float
    fssai_number: str | None = None
    upi_vpa: str | None = None
    is_approved: bool
    is_active: bool


class OwnerStoreUpdate(BaseModel):
    """Owners can change store details and their payment VPA; admin controls location and radius."""
    name: str | None = Field(default=None, min_length=2, max_length=150)
    address: str | None = Field(default=None, max_length=300)
    upi_vpa: str | None = Field(
        default=None,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}@[A-Za-z0-9][A-Za-z0-9.-]{0,63}$",
    )