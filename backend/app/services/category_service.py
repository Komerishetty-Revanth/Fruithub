import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Category, Product
from app.schemas.category import CategoryAdminOut, CategoryUpdate
from app.utils.text import slugify


def _out(db: Session, c: Category) -> CategoryAdminOut:
    count = db.scalar(select(func.count(Product.id)).where(Product.category_id == c.id)) or 0
    return CategoryAdminOut(
        id=str(c.id), name=c.name, slug=c.slug, product_type=c.product_type,
        is_active=c.is_active, product_count=count
    )


def _conflict(db: Session, name: str, slug: str, exclude: uuid.UUID | None = None) -> bool:
    stmt = select(Category.id).where(
        or_(func.lower(Category.name) == name.lower(), Category.slug == slug)
    )
    if exclude:
        stmt = stmt.where(Category.id != exclude)
    return db.scalar(stmt) is not None


def list_all(db: Session) -> list[CategoryAdminOut]:
    return [_out(db, c) for c in db.scalars(select(Category).order_by(Category.name)).all()]


def create_category(db: Session, name: str, product_type: str = "FRUIT") -> CategoryAdminOut:
    name = name.strip()
    slug = slugify(name)
    if not slug:
        raise AppError("VALIDATION_ERROR", "Please use letters or numbers in the name.", 422)
    if product_type not in {"FRUIT", "JUICE", "DRY_FRUIT"}:
        raise AppError("VALIDATION_ERROR", "product_type must be FRUIT, JUICE or DRY_FRUIT.", 422)
    if _conflict(db, name, slug):
        raise AppError("CATEGORY_EXISTS", "A category with this name already exists.", 409)
    c = Category(name=name, slug=slug, product_type=product_type)
    db.add(c)
    db.commit()
    db.refresh(c)
    return _out(db, c)


def update_category(db: Session, category_id: uuid.UUID, data: CategoryUpdate) -> CategoryAdminOut:
    c = db.get(Category, category_id)
    if c is None:
        raise AppError("CATEGORY_NOT_FOUND", "This category was not found.", 404)
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes:
        if changes["name"] is None or not changes["name"].strip():
            raise AppError("VALIDATION_ERROR", "Name cannot be empty.", 422)
        name = changes["name"].strip()
        slug = slugify(name)
        if not slug:
            raise AppError("VALIDATION_ERROR", "Please use letters or numbers in the name.", 422)
        if _conflict(db, name, slug, exclude=c.id):
            raise AppError("CATEGORY_EXISTS", "A category with this name already exists.", 409)
        c.name, c.slug = name, slug
    if "product_type" in changes:
        if changes["product_type"] not in {"FRUIT", "JUICE", "DRY_FRUIT"}:
            raise AppError("VALIDATION_ERROR", "product_type must be FRUIT, JUICE or DRY_FRUIT.", 422)
        c.product_type = changes["product_type"]
    if "is_active" in changes:
        if changes["is_active"] is None:
            raise AppError("VALIDATION_ERROR", "is_active cannot be empty.", 422)
        c.is_active = changes["is_active"]
    db.commit()
    db.refresh(c)
    return _out(db, c)


def delete_category(db: Session, category_id: uuid.UUID) -> None:
    c = db.get(Category, category_id)
    if c is None:
        raise AppError("CATEGORY_NOT_FOUND", "This category was not found.", 404)
    in_use = db.scalar(select(func.count(Product.id)).where(Product.category_id == c.id)) or 0
    if in_use:
        raise AppError(
            "CATEGORY_IN_USE",
            "This category has products. Deactivate it instead of deleting it.", 409,
        )
    db.delete(c)
    db.commit()