import io
import uuid

from fastapi import BackgroundTasks
from PIL import Image
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.errors import AppError
from app.models import (
    AssetStatus, AssetType, Product, Product3DAsset, ProductImage, User,
)
from app.services.image_service import encode_webp, load_image
from app.services.image_to_3d import get_image_to_3d_service
from app.services.owner_service import _get_owned_product, get_owner_store
from app.services.storage_service import get_storage


def process_asset(asset_id: uuid.UUID, source_key: str, base_key: str) -> None:
    """Runs in the background after the upload response is sent."""
    db = SessionLocal()
    try:
        asset = db.get(Product3DAsset, asset_id)
        if asset is None:
            return
        try:
            storage = get_storage()
            image = Image.open(io.BytesIO(storage.read(source_key))).convert("RGB")
            manifest_key = get_image_to_3d_service().generate(image, base_key, storage)
            asset.storage_key = manifest_key
            asset.status = AssetStatus.READY
            product = db.get(Product, asset.product_id)
            product.asset_3d_url = storage.url(manifest_key)
        except Exception:
            asset.status = AssetStatus.FAILED
        db.commit()
    finally:
        db.close()


def save_product_image(
    db: Session, user: User, product_id: uuid.UUID,
    filename: str | None, content_type: str | None, data: bytes,
    background_tasks: BackgroundTasks,
) -> dict:
    store = get_owner_store(db, user)
    product = _get_owned_product(db, store, product_id)   # owners only reach their own products
    image = load_image(filename, content_type, data)

    storage = get_storage()
    base = f"products/{product.id}/{uuid.uuid4().hex}"     # random name, never the user's filename
    main_key = f"{base}/main.webp"
    storage.save(main_key, encode_webp(image))
    thumb = image.copy()
    thumb.thumbnail((400, 400))
    storage.save(f"{base}/thumb.webp", encode_webp(thumb, 80))

    db.execute(
        update(ProductImage).where(ProductImage.product_id == product.id).values(is_primary=False)
    )
    db.add(ProductImage(product_id=product.id, storage_key=main_key, is_primary=True))
    product.image_url = storage.url(main_key)
    product.asset_3d_url = None   # old 3D visual no longer matches the new photo

    asset = Product3DAsset(
        product_id=product.id, asset_type=AssetType.LAYERED_IMAGE, status=AssetStatus.PENDING
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    background_tasks.add_task(process_asset, asset.id, main_key, f"{base}/3d")
    return {
        "success": True,
        "image_url": product.image_url,
        "asset_status": asset.status.value,
        "message": "Image uploaded. The 3D visual is being generated.",
    }


def get_asset_status(db: Session, user: User, product_id: uuid.UUID) -> dict:
    store = get_owner_store(db, user)
    product = _get_owned_product(db, store, product_id)
    asset = db.scalar(
        select(Product3DAsset)
        .where(Product3DAsset.product_id == product.id)
        .order_by(Product3DAsset.created_at.desc())
    )
    if asset is None:
        raise AppError("ASSET_NOT_FOUND", "No 3D visual has been created yet.", 404)
    return {
        "success": True,
        "asset_status": asset.status.value,
        "asset_3d_url": product.asset_3d_url,
        "enabled": product.asset_3d_url is not None,
    }


def regenerate_product_asset(
    db: Session, user: User, product_id: uuid.UUID, background_tasks: BackgroundTasks,
) -> dict:
    store = get_owner_store(db, user)
    product = _get_owned_product(db, store, product_id)
    image = db.scalar(
        select(ProductImage)
        .where(ProductImage.product_id == product.id, ProductImage.is_primary.is_(True))
        .order_by(ProductImage.created_at.desc())
    )
    if image is None:
        raise AppError("PRODUCT_IMAGE_REQUIRED", "Upload a product image before generating its animated view.", 422)

    asset = Product3DAsset(
        product_id=product.id, asset_type=AssetType.LAYERED_IMAGE, status=AssetStatus.PENDING
    )
    product.asset_3d_url = None
    db.add(asset)
    db.commit()
    db.refresh(asset)
    background_tasks.add_task(
        process_asset, asset.id, image.storage_key,
        f"products/{product.id}/{uuid.uuid4().hex}/3d",
    )
    return {"success": True, "asset_status": asset.status.value, "enabled": True}


def remove_product_asset(db: Session, user: User, product_id: uuid.UUID) -> dict:
    store = get_owner_store(db, user)
    product = _get_owned_product(db, store, product_id)
    product.asset_3d_url = None
    db.commit()
    return {"success": True, "enabled": False}