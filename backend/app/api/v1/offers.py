from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.offer import TodaysOffersOut
from app.services import offer_service

router = APIRouter(tags=["Offers"])


@router.get("/offers", response_model=TodaysOffersOut)
def todays_fresh_offers(db: Session = Depends(get_db)):
    """Only offers that are live right now. Expired offers never appear."""
    return offer_service.todays_offers(db)