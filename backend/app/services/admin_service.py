import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import hash_password
from app.models import (
    Category, Offer, Order, OrderStatus, Payment, PaymentMethod, PaymentStatus, Product,
    Store, User, UserRole,
)
from app.schemas.admin import (
    AdminOfferListOut, AdminOfferOut, AdminOrderListOut, AdminOrderOut, AdminStoreCreate,
    AdminStoreListOut, AdminStoreOut, AdminStoreUpdate, AdminUserListOut, AdminUserOut,
    AdminUserUpdate, OrderResolve, OwnerCreate,
)
from app.schemas.product import ProductListOut
from app.services import offer_service, order_service
from app.services.product_service import to_product_out

IST = timezone(timedelta(hours=5, minutes=30))


# =====================================================================
# Users
# =====================================================================

def _user_out(db: Session, u: User) -> AdminUserOut:
    store_id = db.scalar(select(Store.id).where(Store.owner_id == u.id))
    return AdminUserOut(
        id=str(u.id), email=u.email, full_name=u.full_name, phone=u.phone,
        role=u.role.value, is_active=u.is_active,
        store_id=str(store_id) if store_id else None, created_at=u.created_at,
    )


def _get_user(db: Session, user_id: uuid.UUID) -> User:
    u = db.get(User, user_id)
    if u is None:
        raise AppError("USER_NOT_FOUND", "This user was not found.", 404)
    return u


def list_users(db: Session, role: UserRole | None, q: str | None, is_active: bool | None,
               page: int, page_size: int) -> AdminUserListOut:
    filters = []
    if role:
        filters.append(User.role == role)
    if is_active is not None:
        filters.append(User.is_active.is_(is_active))
    if q:
        like = f"%{q.strip()}%"
        filters.append(or_(User.email.ilike(like), User.full_name.ilike(like)))
    total = db.scalar(select(func.count(User.id)).where(*filters)) or 0
    rows = db.scalars(
        select(User).where(*filters).order_by(User.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return AdminUserListOut(
        items=[_user_out(db, u) for u in rows], page=page, page_size=page_size, total=total,
    )


def get_user(db: Session, user_id: uuid.UUID) -> AdminUserOut:
    return _user_out(db, _get_user(db, user_id))


def create_owner(db: Session, data: OwnerCreate) -> AdminUserOut:
    email = data.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise AppError("EMAIL_EXISTS", "An account with this email already exists.", 409)
    if db.scalar(select(User).where(User.phone == data.phone)):
        raise AppError("PHONE_EXISTS", "An account with this mobile number already exists.", 409)
    u = User(
        email=email, full_name=data.full_name.strip(), phone=data.phone,
        phone_verified=True,   # the admin vouches for owner accounts
        password_hash=hash_password(data.password), role=UserRole.OWNER,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return _user_out(db, u)


def update_user(db: Session, admin: User, user_id: uuid.UUID, data: AdminUserUpdate) -> AdminUserOut:
    target = _get_user(db, user_id)
    changes = data.model_dump(exclude_unset=True)

    if target.role == UserRole.ADMIN:
        raise AppError("FORBIDDEN", "Admin accounts cannot be changed here.", 403)
    if target.id == admin.id:
        raise AppError("CANNOT_MODIFY_SELF", "You cannot change your own account here.", 403)

    if "full_name" in changes:
        if not changes["full_name"] or not changes["full_name"].strip():
            raise AppError("VALIDATION_ERROR", "Name cannot be empty.", 422)
        target.full_name = changes["full_name"].strip()
    if "is_active" in changes:
        if changes["is_active"] is None:
            raise AppError("VALIDATION_ERROR", "is_active cannot be empty.", 422)
        target.is_active = changes["is_active"]
    if "role" in changes:
        new_role = UserRole(changes["role"])
        if new_role != target.role:
            if new_role == UserRole.CUSTOMER and db.scalar(
                select(Store.id).where(Store.owner_id == target.id)
            ):
                raise AppError(
                    "OWNER_HAS_STORE",
                    "This owner has a store. Disable the store or reassign it first.", 409,
                )
            target.role = new_role

    db.commit()
    db.refresh(target)
    return _user_out(db, target)


# =====================================================================
# Stores
# =====================================================================

def _store_out(db: Session, s: Store) -> AdminStoreOut:
    owner = db.get(User, s.owner_id)
    count = db.scalar(select(func.count(Product.id)).where(Product.store_id == s.id)) or 0
    return AdminStoreOut(
        id=str(s.id), name=s.name, address=s.address, latitude=s.latitude,
        longitude=s.longitude, delivery_radius_km=s.delivery_radius_km,
        fssai_number=s.fssai_number, is_approved=s.is_approved, is_active=s.is_active,
        owner_id=str(s.owner_id), owner_name=owner.full_name if owner else "",
        owner_email=owner.email if owner else "", product_count=count, created_at=s.created_at,
    )


def _get_store(db: Session, store_id: uuid.UUID) -> Store:
    s = db.get(Store, store_id)
    if s is None:
        raise AppError("STORE_NOT_FOUND", "This store was not found.", 404)
    return s


def list_stores(db: Session, q: str | None, is_approved: bool | None, is_active: bool | None,
                page: int, page_size: int) -> AdminStoreListOut:
    filters = []
    if q:
        filters.append(Store.name.ilike(f"%{q.strip()}%"))
    if is_approved is not None:
        filters.append(Store.is_approved.is_(is_approved))
    if is_active is not None:
        filters.append(Store.is_active.is_(is_active))
    total = db.scalar(select(func.count(Store.id)).where(*filters)) or 0
    rows = db.scalars(
        select(Store).where(*filters).order_by(Store.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return AdminStoreListOut(
        items=[_store_out(db, s) for s in rows], page=page, page_size=page_size, total=total,
    )


def get_store(db: Session, store_id: uuid.UUID) -> AdminStoreOut:
    return _store_out(db, _get_store(db, store_id))


def create_store(db: Session, data: AdminStoreCreate) -> AdminStoreOut:
    owner = db.get(User, data.owner_id)
    if owner is None or owner.role != UserRole.OWNER or not owner.is_active:
        raise AppError("INVALID_OWNER", "Choose an active user with the OWNER role.", 422)
    if db.scalar(select(Store.id).where(Store.owner_id == owner.id)):
        raise AppError("OWNER_HAS_STORE", "This owner already has a store.", 409)
    if data.is_approved and not (data.fssai_number or "").strip():
        raise AppError("FSSAI_REQUIRED", "FSSAI licence number is required before approving a store.", 422)
    s = Store(
        owner_id=owner.id, name=data.name.strip(), address=data.address,
        latitude=data.latitude, longitude=data.longitude,
        delivery_radius_km=data.delivery_radius_km,
        fssai_number=(data.fssai_number or "").strip() or None,
        is_approved=data.is_approved,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _store_out(db, s)


def update_store(db: Session, store_id: uuid.UUID, data: AdminStoreUpdate) -> AdminStoreOut:
    s = _get_store(db, store_id)
    changes = data.model_dump(exclude_unset=True)
    for field in ("name", "latitude", "longitude", "delivery_radius_km",
                  "is_approved", "is_active"):
        if field in changes and changes[field] is None:
            raise AppError("VALIDATION_ERROR", f"{field} cannot be empty.", 422)
    if "name" in changes:
        changes["name"] = changes["name"].strip()
    if "address" in changes:
        changes["address"] = (changes["address"] or "").strip() or None
    if "fssai_number" in changes:
        changes["fssai_number"] = (changes["fssai_number"] or "").strip() or None
    if "is_approved" in changes and changes["is_approved"] is True:
        effective_fssai = (changes.get("fssai_number") if "fssai_number" in changes else s.fssai_number) or ""
        if not effective_fssai.strip():
            raise AppError("FSSAI_REQUIRED", "FSSAI licence number is required before approving a store.", 422)
    for field, value in changes.items():
        setattr(s, field, value)
    db.commit()
    db.refresh(s)
    return _store_out(db, s)


# =====================================================================
# Products
# =====================================================================

def list_products(db: Session, q: str | None, store_id: uuid.UUID | None,
                  category: str | None, is_active: bool | None,
                  page: int, page_size: int) -> ProductListOut:
    filters = []
    if q:
        filters.append(Product.name.ilike(f"%{q.strip()}%"))
    if store_id:
        filters.append(Product.store_id == store_id)
    if category:
        filters.append(Category.slug == category)
    if is_active is not None:
        filters.append(Product.is_active.is_(is_active))
    total = db.scalar(
        select(func.count(Product.id)).join(Category, Product.category_id == Category.id)
        .where(*filters)
    ) or 0
    rows = db.execute(
        select(Product, Category, Store)
        .join(Category, Product.category_id == Category.id)
        .join(Store, Product.store_id == Store.id)
        .where(*filters).order_by(Product.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return ProductListOut(
        items=[to_product_out(p, c, s) for p, c, s in rows],
        page=page, page_size=page_size, total=total,
    )


def _get_product(db: Session, product_id: uuid.UUID) -> Product:
    p = db.get(Product, product_id)
    if p is None:
        raise AppError("PRODUCT_NOT_FOUND", "This product was not found.", 404)
    return p


def set_product_active(db: Session, product_id: uuid.UUID, active: bool):
    p = _get_product(db, product_id)
    p.is_active = active
    db.commit()
    db.refresh(p)
    return to_product_out(p, db.get(Category, p.category_id), db.get(Store, p.store_id))


def delete_product(db: Session, product_id: uuid.UUID) -> None:
    """Permanent. Past orders keep their own copy of the name and price."""
    p = _get_product(db, product_id)
    db.delete(p)
    db.commit()


# =====================================================================
# Orders
# =====================================================================

def _order_out(db: Session, o: Order) -> AdminOrderOut:
    base = order_service._order_out(db, o)
    customer = db.get(User, o.customer_id)
    store = db.get(Store, o.store_id)
    return AdminOrderOut(
        **base.model_dump(),
        customer_name=customer.full_name if customer else "",
        customer_email=customer.email if customer else "",
        customer_phone=customer.phone if customer else None,
        store_id=str(o.store_id), store_name=store.name if store else "",
    )


def list_orders(db: Session, status: OrderStatus | None, store_id: uuid.UUID | None,
                q: str | None, date_from: date | None, date_to: date | None,
                page: int, page_size: int) -> AdminOrderListOut:
    filters = []
    if status:
        filters.append(Order.status == status)
    if store_id:
        filters.append(Order.store_id == store_id)
    if q:
        like = f"%{q.strip()}%"
        filters.append(or_(Order.order_number.ilike(like), User.email.ilike(like),
                           User.full_name.ilike(like)))
    if date_from:
        filters.append(Order.created_at >= datetime.combine(date_from, time.min, tzinfo=IST))
    if date_to:
        filters.append(
            Order.created_at < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=IST)
        )
    total = db.scalar(
        select(func.count(Order.id)).join(User, Order.customer_id == User.id).where(*filters)
    ) or 0
    rows = db.scalars(
        select(Order).join(User, Order.customer_id == User.id).where(*filters)
        .order_by(Order.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return AdminOrderListOut(
        items=[_order_out(db, o) for o in rows], page=page, page_size=page_size, total=total,
    )


def get_order(db: Session, order_id: uuid.UUID) -> AdminOrderOut:
    o = db.get(Order, order_id)
    if o is None:
        raise AppError("ORDER_NOT_FOUND", "This order was not found.", 404)
    return _order_out(db, o)


def resolve_order(db: Session, admin: User, order_id: uuid.UUID, data: OrderResolve) -> AdminOrderOut:
    """Admin override for support cases. A note is always required and saved in the history."""
    order = db.scalar(
        select(Order).where(Order.id == order_id)
        .with_for_update().execution_options(populate_existing=True)
    )
    if order is None:
        raise AppError("ORDER_NOT_FOUND", "This order was not found.", 404)
    if order.status in (OrderStatus.DELIVERED, OrderStatus.CANCELLED):
        raise AppError("ORDER_CLOSED", f"This order is already {order.status.value}.", 409)
    if data.status == OrderStatus.PENDING_PAYMENT:
        raise AppError("INVALID_STATUS_CHANGE", "An order cannot go back to pending payment.", 409)

    note = f"Admin: {data.note.strip()}"
    if data.status == OrderStatus.CANCELLED:
        was_paid = order.payment_status == PaymentStatus.PAID
        manual_upi_paid = was_paid and order.payment_method == PaymentMethod.UPI_MANUAL
        if manual_upi_paid:
            note += ". Direct UPI payment must be refunded by the store outside FruitHub."
        order_service._release_stock_and_cancel(db, order, admin.id, note)
        if was_paid and not manual_upi_paid:
            order.payment_status = PaymentStatus.REFUNDED   # mock gateway: no real money moves
            for pay in db.scalars(
                select(Payment).where(Payment.order_id == order.id,
                                      Payment.status == PaymentStatus.PAID)
            ).all():
                pay.status = PaymentStatus.REFUNDED
    else:
        if order.payment_status != PaymentStatus.PAID:
            raise AppError("NOT_PAID", "This order has not been paid yet.", 409)
        order.status = data.status
        order_service._history(db, order.id, data.status, admin.id, note)

    db.commit()
    db.refresh(order)
    return _order_out(db, order)


# =====================================================================
# Offers
# =====================================================================

def _offer_out(db: Session, o: Offer) -> AdminOfferOut:
    store = db.get(Store, o.store_id)
    return AdminOfferOut(**offer_service._out(db, o).model_dump(),
                         store_name=store.name if store else "")


def list_offers(db: Session, store_id: uuid.UUID | None, live_only: bool) -> AdminOfferListOut:
    stmt = select(Offer).order_by(Offer.starts_at.desc())
    if store_id:
        stmt = stmt.where(Offer.store_id == store_id)
    offers = db.scalars(stmt).all()
    items = [_offer_out(db, o) for o in offers]
    if live_only:
        items = [i for i in items if i.is_live]
    return AdminOfferListOut(items=items)


def set_offer_active(db: Session, offer_id: uuid.UUID, active: bool) -> AdminOfferOut:
    o = db.get(Offer, offer_id)
    if o is None:
        raise AppError("OFFER_NOT_FOUND", "This offer was not found.", 404)
    o.is_active = active
    db.commit()
    db.refresh(o)
    return _offer_out(db, o)


# =====================================================================
# Analytics
# =====================================================================

def analytics(db: Session) -> dict:
    now_ist = datetime.now(IST)
    today_start = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=6)

    real = [Order.status != OrderStatus.PENDING_PAYMENT]
    earned = real + [Order.status != OrderStatus.CANCELLED,
                     Order.payment_status == PaymentStatus.PAID]

    def count_users(role):
        return db.scalar(select(func.count(User.id)).where(User.role == role)) or 0

    by_status = {
        s.value: n for s, n in db.execute(
            select(Order.status, func.count(Order.id)).group_by(Order.status)
        ).all()
    }

    days = {(week_start + timedelta(days=i)).date().isoformat(): {"orders": 0, "revenue": 0.0}
            for i in range(7)}
    for created, total, pay_status, status in db.execute(
        select(Order.created_at, Order.total, Order.payment_status, Order.status)
        .where(*real, Order.created_at >= week_start)
    ).all():
        key = created.astimezone(IST).date().isoformat()
        if key in days:
            days[key]["orders"] += 1
            if pay_status == PaymentStatus.PAID and status != OrderStatus.CANCELLED:
                days[key]["revenue"] += float(total)

    return {
        "total_customers": count_users(UserRole.CUSTOMER),
        "total_owners": count_users(UserRole.OWNER),
        "total_products": db.scalar(select(func.count(Product.id))) or 0,
        "total_orders": db.scalar(select(func.count(Order.id)).where(*real)) or 0,
        "revenue": float(db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(*earned))),
        "revenue_today": float(db.scalar(
            select(func.coalesce(func.sum(Order.total), 0)).where(*earned, Order.created_at >= today_start))),
        "active_stores": db.scalar(select(func.count(Store.id)).where(
            Store.is_active.is_(True), Store.is_approved.is_(True))) or 0,
        "stores_awaiting_approval": db.scalar(
            select(func.count(Store.id)).where(Store.is_approved.is_(False))) or 0,
        "orders_by_status": by_status,
        "last_7_days": [{"date": d, **v} for d, v in days.items()],
    }