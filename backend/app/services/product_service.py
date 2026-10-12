import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Category, Product, Store
from app.schemas.product import CategoryOut, ProductListOut, ProductOut


def to_product_out(p: Product, c: Category, s: Store) -> ProductOut:
    final_price = p.discount_price if p.discount_price is not None else p.price
    percent = 0
    if p.discount_price is not None and p.price > 0:
        percent = int(round((p.price - p.discount_price) / p.price * 100))
    return ProductOut(
        id=str(p.id), store_id=str(p.store_id), store_name=s.name,
        category=CategoryOut(id=str(c.id), name=c.name, slug=c.slug, product_type=c.product_type),
        name=p.name, description=p.description, origin=p.origin, nutrition=p.nutrition,
        ingredients=p.ingredients, allergens=p.allergens, is_veg=p.is_veg,
        shelf_life_days=p.shelf_life_days, best_before=p.best_before.isoformat() if p.best_before else None,
        storage_note=p.storage_note, sugar_info=p.sugar_info, is_made_to_order=p.is_made_to_order,
        price=p.price, discount_price=p.discount_price, final_price=final_price,
        discount_percent=percent, unit=p.unit, stock_quantity=p.stock_quantity,
        image_url=p.image_url, asset_3d_url=p.asset_3d_url,
        is_available=p.is_available and p.stock_quantity > 0,
        is_active=p.is_active,
        rating=p.rating, rating_count=p.rating_count,
    )


def list_categories(db: Session) -> list[CategoryOut]:
    rows = db.scalars(
        select(Category).where(Category.is_active.is_(True)).order_by(Category.name)
    ).all()
    return [CategoryOut(id=str(c.id), name=c.name, slug=c.slug, product_type=c.product_type) for c in rows]


def search_products(
    db: Session, q, category, min_price, max_price,
    available, has_offer, min_rating, sort, page, page_size,
    product_type: str | None = None,
) -> ProductListOut:
    # Only show products that are active, in an approved and active store
    filters = [
        Product.is_active.is_(True),
        Store.is_active.is_(True),
        Store.is_approved.is_(True),
    ]
    if q:
        filters.append(Product.name.ilike(f"%{q.strip()}%"))
    if category:
        filters.append(Category.slug == category)
    if product_type:
        filters.append(Category.product_type == product_type)
    if min_price is not None:
        filters.append(func.coalesce(Product.discount_price, Product.price) >= min_price)
    if max_price is not None:
        filters.append(func.coalesce(Product.discount_price, Product.price) <= max_price)
    if available:
        filters.append(Product.is_available.is_(True))
        filters.append(Product.stock_quantity > 0)
    if has_offer:
        filters.append(Product.discount_price.is_not(None))
    if min_rating is not None:
        filters.append(Product.rating >= min_rating)

    total = db.scalar(
        select(func.count(Product.id))
        .join(Category, Product.category_id == Category.id)
        .join(Store, Product.store_id == Store.id)
        .where(*filters)
    )

    order = {
        "price_asc": func.coalesce(Product.discount_price, Product.price).asc(),
        "price_desc": func.coalesce(Product.discount_price, Product.price).desc(),
        "rating": Product.rating.desc(),
        "newest": Product.created_at.desc(),
    }.get(sort, Product.name.asc())

    rows = db.execute(
        select(Product, Category, Store)
        .join(Category, Product.category_id == Category.id)
        .join(Store, Product.store_id == Store.id)
        .where(*filters)
        .order_by(order)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return ProductListOut(
        items=[to_product_out(p, c, s) for p, c, s in rows],
        page=page, page_size=page_size, total=total or 0,
    )


def get_product(db: Session, product_id: uuid.UUID) -> ProductOut:
    row = db.execute(
        select(Product, Category, Store)
        .join(Category, Product.category_id == Category.id)
        .join(Store, Product.store_id == Store.id)
        .where(
            Product.id == product_id,
            Product.is_active.is_(True),
            Store.is_active.is_(True),
            Store.is_approved.is_(True),
        )
    ).first()
    if row is None:
        raise AppError("PRODUCT_NOT_FOUND", "This product was not found.", 404)
    return to_product_out(*row)


def related_products(db: Session, product_id: uuid.UUID, limit: int = 6) -> list[ProductOut]:
    """Other fruits from the same category."""
    base = get_product(db, product_id)
    rows = db.execute(
        select(Product, Category, Store)
        .join(Category, Product.category_id == Category.id)
        .join(Store, Product.store_id == Store.id)
        .where(
            Product.category_id == uuid.UUID(base.category.id),
            Product.id != product_id,
            Product.is_active.is_(True),
            Store.is_active.is_(True),
            Store.is_approved.is_(True),
        )
        .order_by(Product.rating.desc(), Product.name)
        .limit(limit)
    ).all()
    return [to_product_out(p, c, s) for p, c, s in rows]