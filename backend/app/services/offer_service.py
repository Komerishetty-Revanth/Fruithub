import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import (
    Category, DiscountType, Offer, OfferProduct, Product, Store, User,
)
from app.schemas.offer import (
    OfferCreate, OfferListOut, OfferOut, OfferUpdate, TodaysOffersOut,
)
from app.services.owner_service import get_owner_store
from app.services.product_service import to_product_out

CENT = Decimal("0.01")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _live(o: Offer, now: datetime) -> bool:
    return o.is_active and o.starts_at <= now <= o.ends_at


def _product_ids(db: Session, offer_id: uuid.UUID) -> list[uuid.UUID]:
    return list(db.scalars(
        select(OfferProduct.product_id).where(OfferProduct.offer_id == offer_id)
    ).all())


def _out(db: Session, o: Offer) -> OfferOut:
    return OfferOut(
        id=str(o.id), store_id=str(o.store_id), title=o.title,
        description=o.description, discount_type=o.discount_type.value,
        discount_value=o.discount_value, min_order_amount=o.min_order_amount,
        starts_at=o.starts_at, ends_at=o.ends_at, is_active=o.is_active,
        is_live=_live(o, _now()),
        product_ids=[str(i) for i in _product_ids(db, o.id)],
    )


def _check_products(db: Session, store: Store, ids: list[uuid.UUID]) -> list[uuid.UUID]:
    ids = list(dict.fromkeys(ids))  # remove duplicates, keep order
    if not ids:
        return ids
    found = set(db.scalars(
        select(Product.id).where(Product.id.in_(ids), Product.store_id == store.id)
    ).all())
    if len(found) != len(ids):
        # Security: an owner can only attach their own products
        raise AppError("PRODUCT_NOT_FOUND", "One or more products were not found.", 404)
    return ids


def _get_owned_offer(db: Session, store: Store, offer_id: uuid.UUID) -> Offer:
    o = db.scalar(select(Offer).where(Offer.id == offer_id, Offer.store_id == store.id))
    if o is None:
        raise AppError("OFFER_NOT_FOUND", "This offer was not found.", 404)
    return o


# ---------- owner ----------

def create_offer(db: Session, user: User, data: OfferCreate) -> OfferOut:
    store = get_owner_store(db, user)
    ids = _check_products(db, store, data.product_ids)
    o = Offer(
        store_id=store.id, title=data.title.strip(), description=data.description,
        discount_type=data.discount_type, discount_value=data.discount_value,
        min_order_amount=data.min_order_amount,
        starts_at=_aware(data.starts_at), ends_at=_aware(data.ends_at),
    )
    db.add(o)
    db.flush()
    db.add_all([OfferProduct(offer_id=o.id, product_id=pid) for pid in ids])
    db.commit()
    db.refresh(o)
    return _out(db, o)


def list_offers(db: Session, user: User) -> OfferListOut:
    store = get_owner_store(db, user)
    rows = db.scalars(
        select(Offer).where(Offer.store_id == store.id).order_by(Offer.starts_at.desc())
    ).all()
    return OfferListOut(items=[_out(db, o) for o in rows])


def update_offer(db: Session, user: User, offer_id: uuid.UUID, data: OfferUpdate) -> OfferOut:
    store = get_owner_store(db, user)
    o = _get_owned_offer(db, store, offer_id)
    changes = data.model_dump(exclude_unset=True)

    for field in ("title", "discount_value", "starts_at", "ends_at"):
        if field in changes and changes[field] is None:
            raise AppError("VALIDATION_ERROR", f"{field} cannot be empty.", 422)

    product_ids = changes.pop("product_ids", "unchanged")
    for field, value in changes.items():
        if field in ("starts_at", "ends_at"):
            value = _aware(value)
        if field == "title":
            value = value.strip()
        setattr(o, field, value)

    if o.ends_at <= o.starts_at:
        db.rollback()
        raise AppError("INVALID_DATES", "End time must be after start time.", 422)
    if o.discount_type == DiscountType.PERCENTAGE and o.discount_value > 100:
        db.rollback()
        raise AppError("INVALID_DISCOUNT", "Percentage cannot be more than 100.", 422)

    if product_ids != "unchanged":
        try:
            ids = _check_products(db, store, product_ids or [])
        except AppError:
            db.rollback()
            raise
        db.query(OfferProduct).filter(OfferProduct.offer_id == o.id).delete()
        db.add_all([OfferProduct(offer_id=o.id, product_id=pid) for pid in ids])

    db.commit()
    db.refresh(o)
    return _out(db, o)


def set_offer_active(db: Session, user: User, offer_id: uuid.UUID, active: bool) -> OfferOut:
    store = get_owner_store(db, user)
    o = _get_owned_offer(db, store, offer_id)
    o.is_active = active
    db.commit()
    db.refresh(o)
    return _out(db, o)


# ---------- public ----------

def live_offers(db: Session, store_id: uuid.UUID | None = None) -> list[Offer]:
    """Offers that are active right now, from approved and active stores."""
    now = _now()
    stmt = (
        select(Offer).join(Store, Offer.store_id == Store.id)
        .where(
            Offer.is_active.is_(True), Offer.starts_at <= now, Offer.ends_at >= now,
            Store.is_active.is_(True), Store.is_approved.is_(True),
        )
        .order_by(Offer.ends_at.asc())
    )
    if store_id:
        stmt = stmt.where(Offer.store_id == store_id)
    return list(db.scalars(stmt).all())


def todays_offers(db: Session) -> TodaysOffersOut:
    offers = live_offers(db)
    wanted: dict[uuid.UUID, Product] = {}
    for o in offers:
        ids = _product_ids(db, o.id)
        stmt = select(Product).where(Product.store_id == o.store_id, Product.is_active.is_(True))
        if ids:
            stmt = stmt.where(Product.id.in_(ids))
        # percentage offers apply to products; fixed cart offers are listed without products
        if o.discount_type == DiscountType.PERCENTAGE or ids:
            for p in db.scalars(stmt).all():
                wanted[p.id] = p
    for p in db.scalars(
        select(Product).join(Store, Product.store_id == Store.id).where(
            Product.is_active.is_(True), Product.discount_price.is_not(None),
            Store.is_active.is_(True), Store.is_approved.is_(True),
        )
    ).all():
        wanted[p.id] = p   # products with their own sale price also count

    items = []
    for p in wanted.values():
        cat = db.get(Category, p.category_id)
        store = db.get(Store, p.store_id)
        out = to_product_out(p, cat, store)
        # show the price after any live percentage offer
        pct = best_percentage(db, p, offers)
        if pct > 0:
            base = p.discount_price if p.discount_price is not None else p.price
            out.final_price = (base * (Decimal(100) - pct) / Decimal(100)).quantize(
                CENT, ROUND_HALF_UP)
            out.discount_percent = int(round((p.price - out.final_price) / p.price * 100))
        items.append(out)
    return TodaysOffersOut(offers=[_out(db, o) for o in offers], products=items)


# ---------- discount calculation (reused by the cart and checkout later) ----------

def best_percentage(db: Session, product: Product, offers: list[Offer]) -> Decimal:
    """Highest live percentage that applies to this product (0 if none)."""
    best = Decimal(0)
    now = _now()
    for o in offers:
        if o.store_id != product.store_id or o.discount_type != DiscountType.PERCENTAGE:
            continue
        if not _live(o, now):
            continue
        ids = _product_ids(db, o.id)
        if ids and product.id not in ids:
            continue
        best = max(best, Decimal(o.discount_value))
    return best


def unit_price_for(db: Session, product: Product, offers: list[Offer]) -> Decimal:
    """Price per unit after the product's own sale price and the best live percentage."""
    base = product.discount_price if product.discount_price is not None else product.price
    pct = best_percentage(db, product, offers)
    if pct > 0:
        base = base * (Decimal(100) - pct) / Decimal(100)
    return base.quantize(CENT, ROUND_HALF_UP)


def best_fixed_discount(offers: list[Offer], store_id: uuid.UUID, subtotal: Decimal) -> Decimal:
    """Best live flat discount on the cart subtotal, respecting the minimum order."""
    best = Decimal(0)
    now = _now()
    for o in offers:
        if o.store_id != store_id or o.discount_type != DiscountType.FIXED or not _live(o, now):
            continue
        if o.min_order_amount is not None and subtotal < o.min_order_amount:
            continue
        best = max(best, Decimal(o.discount_value))
    return min(best, subtotal)