from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.location import LocationCheckOut, LocationCheckRequest
from app.services import delivery_service

router = APIRouter(prefix="/locations", tags=["Location"])


@router.post("/check", response_model=LocationCheckOut)
def check_delivery(data: LocationCheckRequest, db: Session = Depends(get_db)):
    """Is this point inside a store's delivery radius? Coordinates are never stored or returned."""
    return delivery_service.check_location(db, data.latitude, data.longitude, data.store_id)