from pydantic import BaseModel, Field

from app.schemas.location import LocationCheckOut

SOURCE_PATTERN = "^(MAP_PIN|GPS|SEARCH)$"


class AddressCreate(BaseModel):
    """Only latitude and longitude are required. The rest can be added later."""
    label: str = Field(default="Home", min_length=1, max_length=50)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    location_label: str | None = Field(default=None, max_length=300)
    location_source: str = Field(default="MAP_PIN", pattern=SOURCE_PATTERN)
    line1: str | None = Field(default=None, min_length=3, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    landmark: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, min_length=2, max_length=100)
    pincode: str | None = Field(default=None, pattern=r"^\d{6}$")
    is_default: bool = False


class AddressUpdate(BaseModel):
    """Send only what you want to change. Use this to add the main address later or move the pin."""
    label: str | None = Field(default=None, min_length=1, max_length=50)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_label: str | None = Field(default=None, max_length=300)
    location_source: str | None = Field(default=None, pattern=SOURCE_PATTERN)
    line1: str | None = Field(default=None, min_length=3, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    landmark: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, min_length=2, max_length=100)
    pincode: str | None = Field(default=None, pattern=r"^\d{6}$")
    is_default: bool | None = None


class AddressOut(BaseModel):
    id: str
    label: str
    latitude: float
    longitude: float
    location_label: str | None
    location_source: str
    line1: str | None
    line2: str | None
    landmark: str | None
    city: str | None
    pincode: str | None
    is_default: bool
    is_complete: bool                      # True when street, city and pincode are filled
    delivery: LocationCheckOut | None