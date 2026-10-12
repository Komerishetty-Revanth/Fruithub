import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import require_owner
from app.models import OrderStatus, User
from app.schemas.offer import OfferCreate, OfferListOut, OfferOut, OfferUpdate
from app.schemas.owner import ProductCreate, ProductUpdate, StockAdjust
from app.schemas.owner_order import (
    ManualPaymentOut, ManualPaymentReject, OrderStatusChange, OwnerOrderListOut,
    OwnerOrderOut,
)
from app.schemas.product import ProductListOut, ProductOut
from app.services import offer_service, owner_order_service, owner_service, upload_service

router = APIRouter(prefix="/owner", tags=["Owner"])


# ---------- products ----------

@router.get("/products", response_model=ProductListOut)
def my_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    return owner_service.list_products(db, user, page, page_size)


@router.post("/products", response_model=ProductOut, status_code=201)
def add_product(data: ProductCreate, user: User = Depends(require_owner), db: Session = Depends(get_db)):
    return owner_service.create_product(db, user, data)


@router.get("/products/{product_id}", response_model=ProductOut)
def my_product(product_id: uuid.UUID, user: User = Depends(require_owner), db: Session = Depends(get_db)):
    return owner_service.get_product(db, user, product_id)


@router.patch("/products/{product_id}", response_model=ProductOut)
def edit_product(product_id: uuid.UUID, data: ProductUpdate,
                 user: User = Depends(require_owner), db: Session = Depends(get_db)):
    return owner_service.update_product(db, user, product_id, data)


@router.post("/products/{product_id}/deactivate", response_model=ProductOut)
def deactivate(product_id: uuid.UUID, user: User = Depends(require_owner), db: Session = Depends(get_db)):
    return owner_service.set_active(db, user, product_id, False)


@router.post("/products/{product_id}/activate", response_model=ProductOut)
def activate(product_id: uuid.UUID, user: User = Depends(require_owner), db: Session = Depends(get_db)):
    return owner_service.set_active(db, user, product_id, True)


@router.post("/products/{product_id}/stock", response_model=ProductOut)
def change_stock(product_id: uuid.UUID, data: StockAdjust,
                 user: User = Depends(require_owner), db: Session = Depends(get_db)):
    return owner_service.adjust_stock(db, user, product_id, data)


@router.post("/products/{product_id}/image", status_code=202)
def upload_image(
    product_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    # Read at most limit + 1 bytes, so huge files are never fully loaded
    data = file.file.read(settings.MAX_UPLOAD_MB * 1024 * 1024 + 1)
    return upload_service.save_product_image(
        db, user, product_id, file.filename, file.content_type, data, background_tasks
    )


@router.get("/products/{product_id}/3d-status")
def asset_status(product_id: uuid.UUID, user: User = Depends(require_owner), db: Session = Depends(get_db)):
    return upload_service.get_asset_status(db, user, product_id)


@router.post("/products/{product_id}/3d")
def regenerate_asset(
    product_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    return upload_service.regenerate_product_asset(db, user, product_id, background_tasks)


@router.delete("/products/{product_id}/3d")
def remove_asset(product_id: uuid.UUID, user: User = Depends(require_owner), db: Session = Depends(get_db)):
    return upload_service.remove_product_asset(db, user, product_id)


# ---------- offers ----------

@router.get("/offers", response_model=OfferListOut)
def my_offers(user: User = Depends(require_owner), db: Session = Depends(get_db)):
    return offer_service.list_offers(db, user)


@router.post("/offers", response_model=OfferOut, status_code=201)
def add_offer(data: OfferCreate, user: User = Depends(require_owner), db: Session = Depends(get_db)):
    return offer_service.create_offer(db, user, data)


@router.patch("/offers/{offer_id}", response_model=OfferOut)
def edit_offer(offer_id: uuid.UUID, data: OfferUpdate,
               user: User = Depends(require_owner), db: Session = Depends(get_db)):
    return offer_service.update_offer(db, user, offer_id, data)


@router.post("/offers/{offer_id}/deactivate", response_model=OfferOut)
def deactivate_offer(offer_id: uuid.UUID, user: User = Depends(require_owner), db: Session = Depends(get_db)):
    return offer_service.set_offer_active(db, user, offer_id, False)


@router.post("/offers/{offer_id}/activate", response_model=OfferOut)
def activate_offer(offer_id: uuid.UUID, user: User = Depends(require_owner), db: Session = Depends(get_db)):
    return offer_service.set_offer_active(db, user, offer_id, True)


# ---------- orders ----------

@router.get("/orders/manual-payments", response_model=list[ManualPaymentOut])
def manual_payment_queue(user: User = Depends(require_owner), db: Session = Depends(get_db)):
    return owner_order_service.list_manual_payments(db, user)


@router.post("/orders/{order_id}/manual-payment/confirm", response_model=OwnerOrderOut)
def confirm_manual_payment(
    order_id: uuid.UUID, user: User = Depends(require_owner), db: Session = Depends(get_db),
):
    return owner_order_service.confirm_manual_payment(db, user, order_id)


@router.post("/orders/{order_id}/manual-payment/reject", response_model=OwnerOrderOut)
def reject_manual_payment(
    order_id: uuid.UUID,
    data: ManualPaymentReject,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    return owner_order_service.reject_manual_payment(db, user, order_id, data)


@router.get("/orders", response_model=OwnerOrderListOut)
def store_orders(
    status: OrderStatus | None = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    return owner_order_service.list_orders(db, user, status, page, page_size)


@router.get("/orders/{order_id}", response_model=OwnerOrderOut)
def store_order(order_id: uuid.UUID, user: User = Depends(require_owner), db: Session = Depends(get_db)):
    return owner_order_service.get_order(db, user, order_id)


@router.post("/orders/{order_id}/status", response_model=OwnerOrderOut)
def change_order_status(order_id: uuid.UUID, data: OrderStatusChange,
                        user: User = Depends(require_owner), db: Session = Depends(get_db)):
    """Accept, reject, pack, dispatch or deliver. One step at a time."""
    return owner_order_service.change_status(db, user, order_id, data)


# ---------- analytics ----------

@router.get("/analytics")
def store_analytics(user: User = Depends(require_owner), db: Session = Depends(get_db)):
    return owner_order_service.analytics(db, user)