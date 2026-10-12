import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import (
    Order, OrderItem, OrderStatus, Payment, PaymentMethod, PaymentStatus, Product, User,
)
from app.schemas.owner_order import (
    ManualPaymentOut, ManualPaymentReject, OrderStatusChange, OwnerOrderListOut,
    OwnerOrderOut,
)
from app.services import offer_service, order_service
from app.services.owner_service import get_owner_store

S = OrderStatus
TRANSITIONS = {
    S.PLACED: [S.CONFIRMED, S.CANCELLED],
    S.CONFIRMED: [S.PACKING, S.CANCELLED],
    S.PACKING: [S.READY_FOR_DELIVERY, S.CANCELLED],
    S.READY_FOR_DELIVERY: [S.OUT_FOR_DELIVERY],
    S.OUT_FOR_DELIVERY: [S.DELIVERED],
}
NOTES = {
    S.CONFIRMED: "Order accepted by the store",
    S.PACKING: "Store is packing your order",
    S.READY_FOR_DELIVERY: "Order is packed and ready",
    S.OUT_FOR_DELIVERY: "Order is out for delivery",
    S.DELIVERED: "Order delivered",
}
LOW_STOCK_LIMIT = 10
IST = timezone(timedelta(hours=5, minutes=30))


def _out(db: Session, o: Order) -> OwnerOrderOut:
    base = order_service._order_out(db, o)
    customer = db.get(User, o.customer_id)
    allowed_next = TRANSITIONS.get(o.status, [])
    if not o.seller_delivery_available:
        allowed_next = [status for status in allowed_next if status != S.OUT_FOR_DELIVERY]
    return OwnerOrderOut(
        **base.model_dump(),
        customer_name=customer.full_name if customer else "Customer",
        customer_phone=customer.phone if customer else None,
        allowed_next=[s.value for s in allowed_next],
    )


def _get_store_order(db: Session, store, order_id: uuid.UUID, lock: bool = False) -> Order:
    # The store_id filter is the security rule: owners only reach their own store's orders.
    stmt = select(Order).where(
        Order.id == order_id, Order.store_id == store.id,
        Order.status != OrderStatus.PENDING_PAYMENT,
    )
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    o = db.scalar(stmt)
    if o is None:
        raise AppError("ORDER_NOT_FOUND", "This order was not found.", 404)
    return o


def list_orders(db: Session, user: User, status: OrderStatus | None,
                page: int, page_size: int) -> OwnerOrderListOut:
    store = get_owner_store(db, user)
    filters = [Order.store_id == store.id, Order.status != OrderStatus.PENDING_PAYMENT]
    if status:
        filters.append(Order.status == status)
    total = db.scalar(select(func.count(Order.id)).where(*filters)) or 0
    rows = db.scalars(
        select(Order).where(*filters).order_by(Order.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return OwnerOrderListOut(
        items=[_out(db, o) for o in rows], page=page, page_size=page_size, total=total,
    )


def get_order(db: Session, user: User, order_id: uuid.UUID) -> OwnerOrderOut:
    store = get_owner_store(db, user)
    return _out(db, _get_store_order(db, store, order_id))


def list_manual_payments(db: Session, user: User) -> list[ManualPaymentOut]:
    store = get_owner_store(db, user)
    rows = db.execute(
        select(Order, Payment, User.full_name)
        .join(Payment, Payment.order_id == Order.id)
        .join(User, User.id == Order.customer_id)
        .where(
            Order.store_id == store.id,
            Order.status == OrderStatus.PENDING_PAYMENT,
            Payment.provider == "manual_upi",
            Payment.status == PaymentStatus.PENDING,
            Payment.provider_payment_id.is_not(None),
        )
        .order_by(Payment.updated_at.asc())
        .limit(100)
    ).all()
    return [
        ManualPaymentOut(
            order_id=str(order.id), order_number=order.order_number,
            customer_name=customer_name, amount=payment.amount,
            transaction_reference=payment.provider_payment_id,
            submitted_at=payment.updated_at,
        )
        for order, payment, customer_name in rows
    ]


def _get_manual_payment(db: Session, store, order_id: uuid.UUID):
    order = db.scalar(
        select(Order).where(
            Order.id == order_id,
            Order.store_id == store.id,
            Order.status == OrderStatus.PENDING_PAYMENT,
            Order.payment_method == PaymentMethod.UPI_MANUAL,
        ).with_for_update().execution_options(populate_existing=True)
    )
    if order is None:
        raise AppError("ORDER_NOT_FOUND", "This pending UPI order was not found.", 404)
    payment = db.scalar(
        select(Payment).where(
            Payment.order_id == order.id,
            Payment.provider == "manual_upi",
            Payment.status == PaymentStatus.PENDING,
            Payment.provider_payment_id.is_not(None),
        ).with_for_update()
    )
    if payment is None:
        raise AppError(
            "UPI_REFERENCE_NOT_SUBMITTED",
            "The customer has not submitted a UPI transfer reference for this order.",
            409,
        )
    return order, payment


def confirm_manual_payment(db: Session, user: User, order_id: uuid.UUID) -> OwnerOrderOut:
    store = get_owner_store(db, user)
    order, payment = _get_manual_payment(db, store, order_id)
    payment.status = PaymentStatus.PAID
    order.payment_status = PaymentStatus.PAID
    order.status = OrderStatus.PLACED
    order_service._history(
        db, order.id, OrderStatus.PLACED, user.id,
        f"UPI payment manually verified by store (reference {payment.provider_payment_id})",
    )
    db.commit()
    db.refresh(order)
    return _out(db, order)


def reject_manual_payment(
    db: Session, user: User, order_id: uuid.UUID, data: ManualPaymentReject,
) -> OwnerOrderOut:
    store = get_owner_store(db, user)
    order, payment = _get_manual_payment(db, store, order_id)
    payment.status = PaymentStatus.FAILED
    order.payment_status = PaymentStatus.FAILED
    order_service._release_stock_and_cancel(
        db, order, user.id,
        data.note or "Store could not verify the submitted UPI payment reference",
    )
    db.commit()
    db.refresh(order)
    return _out(db, order)


def change_status(db: Session, user: User, order_id: uuid.UUID,
                  data: OrderStatusChange) -> OwnerOrderOut:
    store = get_owner_store(db, user)
    order = _get_store_order(db, store, order_id, lock=True)
    allowed = TRANSITIONS.get(order.status, [])
    if not order.seller_delivery_available:
        allowed = [status for status in allowed if status != S.OUT_FOR_DELIVERY]
    if data.status not in allowed:
        raise AppError(
            "INVALID_STATUS_CHANGE",
            f"An order that is {order.status.value} cannot be changed to {data.status.value}.",
            409,
        )

    if data.status == OrderStatus.CANCELLED:
        note = data.note or "Cancelled by the store"
        if order.payment_method == PaymentMethod.UPI_MANUAL:
            note += ". Any received direct UPI payment must be refunded by the store outside FruitHub."
        order_service._release_stock_and_cancel(db, order, user.id, note)
        if order.payment_method != PaymentMethod.UPI_MANUAL:
            order.payment_status = PaymentStatus.REFUNDED   # mock gateway: no real money moves
            for pay in db.scalars(
                select(Payment).where(Payment.order_id == order.id, Payment.status == PaymentStatus.PAID)
            ).all():
                pay.status = PaymentStatus.REFUNDED
    else:
        order.status = data.status
        order_service._history(db, order.id, data.status, user.id,
                               data.note or NOTES.get(data.status))

    db.commit()
    db.refresh(order)
    return _out(db, order)


def analytics(db: Session, user: User) -> dict:
    store = get_owner_store(db, user)
    now_ist = datetime.now(IST)
    today_start = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=6)

    real = [Order.store_id == store.id, Order.status != OrderStatus.PENDING_PAYMENT]
    earned = real + [Order.status != OrderStatus.CANCELLED,
                     Order.payment_status == PaymentStatus.PAID]

    orders_today = db.scalar(
        select(func.count(Order.id)).where(*real, Order.created_at >= today_start)) or 0
    revenue_today = db.scalar(
        select(func.coalesce(func.sum(Order.total), 0)).where(*earned, Order.created_at >= today_start))
    revenue_total = db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(*earned))
    orders_total = db.scalar(select(func.count(Order.id)).where(*real)) or 0
    awaiting = db.scalar(
        select(func.count(Order.id)).where(*real, Order.status == OrderStatus.PLACED)) or 0

    active_products = db.scalar(
        select(func.count(Product.id)).where(Product.store_id == store.id, Product.is_active.is_(True))) or 0
    low = db.scalars(
        select(Product).where(
            Product.store_id == store.id, Product.is_active.is_(True),
            Product.stock_quantity < LOW_STOCK_LIMIT,
        ).order_by(Product.stock_quantity)
    ).all()

    best = db.execute(
        select(OrderItem.product_name, func.sum(OrderItem.quantity), func.sum(OrderItem.line_total))
        .join(Order, OrderItem.order_id == Order.id)
        .where(*earned).group_by(OrderItem.product_name)
        .order_by(func.sum(OrderItem.quantity).desc()).limit(5)
    ).all()

    # Last 7 days, grouped by Indian date
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
        "today": {
            "orders": orders_today, "revenue": float(revenue_today),
            "awaiting_acceptance": awaiting,
        },
        "totals": {"orders": orders_total, "revenue": float(revenue_total)},
        "products": {"active": active_products, "low_stock_count": len(low)},
        "low_stock": [
            {"id": str(p.id), "name": p.name, "stock": float(p.stock_quantity), "unit": p.unit}
            for p in low[:10]
        ],
        "active_offers": len(offer_service.live_offers(db, store.id)),
        "best_sellers": [
            {"name": n, "quantity_sold": float(q), "revenue": float(r)} for n, q, r in best
        ],
        "last_7_days": [{"date": d, **v} for d, v in days.items()],
    }