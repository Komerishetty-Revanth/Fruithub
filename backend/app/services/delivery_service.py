import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Store
from app.schemas.location import LocationCheckOut
from app.utils.geo import haversine_km, is_within_radius


def distance_to_store(store, lat: float, lng: float) -> float:
    return haversine_km(store.latitude, store.longitude, lat, lng)


def require_delivery(store, lat: float, lng: float) -> float:
    """Used by checkout. Returns the distance, or raises if outside the radius."""
    distance = distance_to_store(store, lat, lng)
    if not is_within_radius(distance, store.delivery_radius_km):
        raise AppError(
            "OUTSIDE_DELIVERY_RADIUS",
            f"This address is outside the {store.delivery_radius_km:g} KM delivery area.",
            422,
        )
    return distance


def check_location(db: Session, lat: float, lng: float, store_id: str | None) -> LocationCheckOut:
    stmt = select(Store).where(Store.is_active.is_(True), Store.is_approved.is_(True))
    if store_id:
        try:
            stmt = stmt.where(Store.id == uuid.UUID(store_id))
        except ValueError:
            raise AppError("STORE_NOT_FOUND", "This store was not found.", 404)
    stores = db.scalars(stmt).all()
    if not stores:
        raise AppError("STORE_NOT_FOUND", "No store is available right now.", 404)

    nearest = min(stores, key=lambda s: distance_to_store(s, lat, lng))
    distance = distance_to_store(nearest, lat, lng)
    ok = is_within_radius(distance, nearest.delivery_radius_km)

    if ok:
        message = "Seller delivery is available to this location."
    else:
        message = "The seller cannot deliver to this location. You may still order, but must arrange and pay for delivery separately."

    return LocationCheckOut(
        available=ok, self_delivery_required=not ok, message=message, store_id=str(nearest.id),
        store_name=nearest.name, distance_km=round(distance, 2),
        delivery_radius_km=nearest.delivery_radius_km,
    )