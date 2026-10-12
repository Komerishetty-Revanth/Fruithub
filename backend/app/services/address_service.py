import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Address, User
from app.schemas.address import AddressCreate, AddressOut, AddressUpdate
from app.services import delivery_service

MAX_ADDRESSES = 10


def address_is_complete(a: Address) -> bool:
    """Checkout calls this. An order needs the full address, not just the pin."""
    return bool(a.line1 and a.city and a.pincode)


def _clean(value):
    if isinstance(value, str):
        return value.strip() or None
    return value


def _out(db: Session, a: Address) -> AddressOut:
    # The 5 km result is measured from the store's pin to this address's pin
    try:
        delivery = delivery_service.check_location(db, a.latitude, a.longitude, None)
    except AppError:
        delivery = None
    return AddressOut(
        id=str(a.id), label=a.label, latitude=a.latitude, longitude=a.longitude,
        location_label=a.location_label, location_source=a.location_source,
        line1=a.line1, line2=a.line2, landmark=a.landmark, city=a.city,
        pincode=a.pincode, is_default=a.is_default,
        is_complete=address_is_complete(a), delivery=delivery,
    )


def _get_own(db: Session, user: User, address_id: uuid.UUID) -> Address:
    # The user_id filter is the security rule: customers only reach their own addresses.
    a = db.scalar(select(Address).where(Address.id == address_id, Address.user_id == user.id))
    if a is None:
        raise AppError("ADDRESS_NOT_FOUND", "This address was not found.", 404)
    return a


def list_addresses(db: Session, user: User) -> list[AddressOut]:
    rows = db.scalars(
        select(Address).where(Address.user_id == user.id)
        .order_by(Address.is_default.desc(), Address.created_at.desc())
    ).all()
    return [_out(db, a) for a in rows]


def create_address(db: Session, user: User, data: AddressCreate) -> AddressOut:
    count = db.scalar(select(func.count(Address.id)).where(Address.user_id == user.id)) or 0
    if count >= MAX_ADDRESSES:
        raise AppError("TOO_MANY_ADDRESSES", f"You can save up to {MAX_ADDRESSES} addresses.", 422)
    make_default = data.is_default or count == 0
    if make_default:
        db.execute(update(Address).where(Address.user_id == user.id).values(is_default=False))
    a = Address(
        user_id=user.id, label=data.label.strip(),
        latitude=data.latitude, longitude=data.longitude,
        location_label=_clean(data.location_label), location_source=data.location_source,
        line1=_clean(data.line1), line2=_clean(data.line2), landmark=_clean(data.landmark),
        city=_clean(data.city), pincode=data.pincode, is_default=make_default,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return _out(db, a)


def update_address(db: Session, user: User, address_id: uuid.UUID, data: AddressUpdate) -> AddressOut:
    a = _get_own(db, user, address_id)
    changes = data.model_dump(exclude_unset=True)

    for field in ("label", "latitude", "longitude", "location_source"):
        if field in changes and changes[field] is None:
            raise AppError("VALIDATION_ERROR", f"{field} cannot be empty.", 422)

    make_default = changes.pop("is_default", None)
    for field, value in changes.items():
        setattr(a, field, _clean(value))
    if not a.label:
        db.rollback()
        raise AppError("VALIDATION_ERROR", "label cannot be empty.", 422)

    if make_default:
        db.execute(update(Address).where(Address.user_id == user.id).values(is_default=False))
        a.is_default = True

    db.commit()
    db.refresh(a)
    return _out(db, a)


def set_default(db: Session, user: User, address_id: uuid.UUID) -> AddressOut:
    a = _get_own(db, user, address_id)
    db.execute(update(Address).where(Address.user_id == user.id).values(is_default=False))
    a.is_default = True
    db.commit()
    db.refresh(a)
    return _out(db, a)


def delete_address(db: Session, user: User, address_id: uuid.UUID) -> None:
    a = _get_own(db, user, address_id)
    was_default = a.is_default
    db.delete(a)
    db.flush()
    if was_default:
        nxt = db.scalar(
            select(Address).where(Address.user_id == user.id).order_by(Address.created_at.desc())
        )
        if nxt:
            nxt.is_default = True
    db.commit()