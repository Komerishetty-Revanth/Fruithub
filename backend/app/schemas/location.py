from pydantic import BaseModel, Field


class LocationCheckRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    store_id: str | None = Field(default=None, description="Optional. Defaults to the nearest store.")


class LocationCheckOut(BaseModel):
    available: bool
    self_delivery_required: bool
    message: str
    store_id: str | None
    store_name: str | None
    distance_km: float | None
    delivery_radius_km: float | None