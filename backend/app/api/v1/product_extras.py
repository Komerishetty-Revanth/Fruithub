import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_customer
from app.models import User
from app.schemas.product import ProductOut
from app.schemas.review import ReviewCreate, ReviewListOut, ReviewOut
from app.services import product_service, review_service

router = APIRouter(tags=["Catalog"])


@router.get("/products/{product_id}/related", response_model=list[ProductOut])
def related(product_id: uuid.UUID, db: Session = Depends(get_db)):
    return product_service.related_products(db, product_id)


@router.get("/products/{product_id}/reviews", response_model=ReviewListOut)
def reviews(
    product_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    return review_service.list_reviews(db, product_id, page, page_size)


@router.put("/products/{product_id}/reviews", response_model=ReviewOut)
def write_review(product_id: uuid.UUID, data: ReviewCreate,
                 user: User = Depends(require_customer), db: Session = Depends(get_db)):
    """Create or update your review. Only for products from a delivered order."""
    return review_service.save_review(db, user, product_id, data)


@router.delete("/products/{product_id}/reviews")
def remove_review(product_id: uuid.UUID, user: User = Depends(require_customer),
                  db: Session = Depends(get_db)):
    review_service.delete_review(db, user, product_id)
    return {"success": True}