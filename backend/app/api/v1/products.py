import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.product import CategoryOut, ProductListOut, ProductOut
from app.services import product_service

router = APIRouter(tags=["Catalog"])


@router.get("/categories", response_model=list[CategoryOut])
def categories(db: Session = Depends(get_db)):
    return product_service.list_categories(db)


@router.get("/products", response_model=ProductListOut)
def products(
    q: str | None = Query(None, max_length=100, description="Search by name"),
    category: str | None = Query(None, description="Category slug, e.g. mango"),
    product_type: str | None = Query(None, pattern="^(FRUIT|JUICE|DRY_FRUIT)$"),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    available: bool = False,
    has_offer: bool = False,
    min_rating: float | None = Query(None, ge=0, le=5),
    sort: str = Query("name", pattern="^(name|price_asc|price_desc|rating|newest)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    return product_service.search_products(
        db, q, category, min_price, max_price,
        available, has_offer, min_rating, sort, page, page_size,
        product_type,
    )


@router.get("/products/{product_id}", response_model=ProductOut)
def product_detail(product_id: uuid.UUID, db: Session = Depends(get_db)):
    return product_service.get_product(db, product_id)