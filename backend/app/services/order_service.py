import logging
import secrets
from urllib.parse import urlencode
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.errors import AppError
from app.models import (
    Address, Cart, CartItem, Inventory, Order, OrderItem, OrderStatus,
    OrderStatusHistory, Payment, PaymentMethod, PaymentStatus, Product, ProductVariant, Store, User,
)
from app.schemas.order import (
    CheckoutOut, CheckoutRequest, ManualUpiReferenceRequest, OrderItemOut, OrderOut,
    PaymentInfoOut, StatusEventOut,
)
from app.services import address_service, cart_service, delivery_service
from app.services.payment_service import MockPaymentProvider, get_payment_provider

logger = logging.getLogger("fruithub.orders")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _history(db: Session, order_id, status: OrderStatus, user_id, note: str | None = None):
    db.add(OrderStatusHistory(order_id=order_id, status=status, changed_by=user_id, note=note))


def _order_out(db: Session, o: Order) -> OrderOut:
    items = db.scalars(select(OrderItem).where(OrderItem.order_id == o.id)).all()
    events = db.scalars(
        select(OrderStatusHistory).where(OrderStatusHistory.order_id == o.id)
        .order_by(OrderStatusHistory.created_at)
    ).all()
    pay_before = None
    if o.status == OrderStatus.PENDING_PAYMENT:
        manual_payment = db.scalar(
            select(Payment).where(
                Payment.order_id == o.id,
                Payment.provider == "manual_upi",
                Payment.provider_payment_id.is_not(None),
            ).order_by(Payment.created_at.desc())
        )
        if manual_payment is not None:
            pay_before = manual_payment.updated_at + timedelta(hours=24)
        else:
            pay_before = o.created_at + timedelta(minutes=settings.PAYMENT_EXPIRY_MINUTES)
    return OrderOut(
        id=str(o.id), order_number=o.order_number, status=o.status.value,
        payment_status=o.payment_status.value, payment_method=o.payment_method.value,
        items=[
            OrderItemOut(
                product_id=str(i.product_id) if i.product_id else None,
                variant_id=str(i.variant_id) if i.variant_id else None,
                name=i.product_name,
                unit=i.unit, variant_label=i.variant_label,
                original_price=i.original_price, unit_price=i.unit_price,
                quantity=i.quantity, line_total=i.line_total,
            ) for i in items
        ],
        subtotal=o.subtotal, discount_total=o.discount_total,
        delivery_fee=o.delivery_fee, total=o.total,
        delivery_line1=o.delivery_line1, delivery_line2=o.delivery_line2,
        delivery_city=o.delivery_city, delivery_pincode=o.delivery_pincode,
        distance_km=o.distance_km, seller_delivery_available=o.seller_delivery_available,
        created_at=o.created_at, pay_before=pay_before,
        history=[StatusEventOut(status=e.status.value, note=e.note, created_at=e.created_at)
                 for e in events],
    )


def _manual_upi_payment_info(db: Session, order: Order, payment: Payment) -> PaymentInfoOut:
    store = db.get(Store, order.store_id)
    if store is None or not store.upi_vpa:
        raise AppError(
            "STORE_UPI_NOT_CONFIGURED",
            "The store no longer has a UPI ID configured. Contact the store before paying.",
            409,
        )
    reference_submitted = payment.provider_payment_id is not None
    expiry_start = payment.updated_at if reference_submitted else order.created_at
    expiry_duration = (
        timedelta(hours=24) if reference_submitted
        else timedelta(minutes=settings.PAYMENT_EXPIRY_MINUTES)
    )
    return PaymentInfoOut(
        provider="manual_upi",
        provider_order_id=None,
        amount=payment.amount,
        currency=payment.currency,
        upi_vpa=store.upi_vpa,
        payee_name=store.name,
        payment_uri="upi://pay?" + urlencode({
            "pa": store.upi_vpa,
            "pn": store.name,
            "am": f"{payment.amount:.2f}",
            "cu": payment.currency,
            "tn": order.order_number,
            "tr": order.order_number,
        }),
        reference_submitted=reference_submitted,
        pay_before=expiry_start + expiry_duration,
    )


def _get_own_order(db: Session, user: User, order_id: uuid.UUID, lock: bool = False) -> Order:
    # The customer_id filter is the security rule: customers only reach their own orders.
    stmt = select(Order).where(Order.id == order_id, Order.customer_id == user.id)
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    o = db.scalar(stmt)
    if o is None:
        raise AppError("ORDER_NOT_FOUND", "This order was not found.", 404)
    return o


# ---------- checkout ----------

def place_order(db: Session, user: User, data: CheckoutRequest) -> CheckoutOut:
    if not user.phone_verified:
        raise AppError(
            "PHONE_NOT_VERIFIED",
            "Please verify your mobile number before placing an order.", 403,
      )
    address = db.scalar(
        select(Address).where(Address.id == data.address_id, Address.user_id == user.id)
    )
    if address is None:
        raise AppError("ADDRESS_NOT_FOUND", "This address was not found.", 404)
    if not address_service.address_is_complete(address):
        raise AppError(
            "ADDRESS_INCOMPLETE",
            "Please add street, city and pincode to this address before ordering.", 422,
        )

    cart = db.scalar(select(Cart).where(Cart.user_id == user.id))
    product_ids = []
    variant_ids = []
    if cart:
        product_ids = list(db.scalars(
            select(CartItem.product_id).where(CartItem.cart_id == cart.id)
        ).all())
        variant_ids = [v for v in db.scalars(
            select(CartItem.variant_id).where(CartItem.cart_id == cart.id, CartItem.variant_id.is_not(None))
        ).all() if v is not None]
    if not product_ids:
        raise AppError("CART_EMPTY", "Your cart is empty.", 422)

    # Lock the product rows (in a fixed order, so two checkouts can never deadlock).
    # Anyone else buying the same fruit waits here, so stock can never be oversold.
    locked = db.scalars(
        select(Product).where(Product.id.in_(product_ids)).order_by(Product.id)
        .with_for_update().execution_options(populate_existing=True)
    ).all()
    products = {p.id: p for p in locked}
    locked_variants = []
    if variant_ids:
        locked_variants = db.scalars(
            select(ProductVariant).where(ProductVariant.id.in_(variant_ids)).order_by(ProductVariant.id)
            .with_for_update().execution_options(populate_existing=True)
        ).all()
    variants = {v.id: v for v in locked_variants}

    summary = cart_service.build_cart(db, cart)
    if not summary.items:
        raise AppError("CART_EMPTY", "Your cart is empty.", 422)
    if summary.has_issues:
        raise AppError(
            "CART_HAS_ISSUES",
            "Some items in your cart are unavailable or low in stock. Please review your cart.",
            422,
        )

    store = db.get(Store, uuid.UUID(summary.store_id))
    if store is None or not store.is_active or not store.is_approved:
        raise AppError("STORE_UNAVAILABLE", "This store is not taking orders right now.", 422)

    distance = delivery_service.distance_to_store(store, address.latitude, address.longitude)
    seller_delivery_available = distance <= store.delivery_radius_km
    if not seller_delivery_available and not data.accept_self_delivery:
        raise AppError(
            "SELF_DELIVERY_ACK_REQUIRED",
            "The seller cannot deliver to this address. Confirm that you will arrange and pay for delivery separately.",
            422,
        )
    if data.payment_method == PaymentMethod.UPI_MANUAL and not store.upi_vpa:
        raise AppError(
            "STORE_UPI_NOT_CONFIGURED",
            "This store has not configured a UPI ID yet. Please contact the store or choose another payment method.",
            409,
        )

    # Beyond the seller's radius, FruitHub charges for products only; delivery is external.
    delivery_fee = summary.delivery_fee if seller_delivery_available else 0
    total = summary.subtotal - summary.discount_total + delivery_fee

    line2_parts = [address.line2, f"Near {address.landmark}" if address.landmark else None]
    line2 = " | ".join(p for p in line2_parts if p)[:200] or None

    order = Order(
        order_number=f"FH-{_now():%Y%m%d}-{secrets.token_hex(3).upper()}",
        customer_id=user.id, store_id=store.id,
        status=OrderStatus.PENDING_PAYMENT, payment_method=data.payment_method,
        payment_status=PaymentStatus.PENDING,
        delivery_line1=address.line1, delivery_line2=line2,
        delivery_city=address.city, delivery_pincode=address.pincode,
        delivery_latitude=address.latitude, delivery_longitude=address.longitude,
        distance_km=round(distance, 2),
        seller_delivery_available=seller_delivery_available,
        subtotal=summary.subtotal, discount_total=summary.discount_total,
        delivery_fee=delivery_fee, total=total,
    )
    db.add(order)
    db.flush()

    for ci in summary.items:
        p = products[uuid.UUID(ci.product_id)]
        variant = variants.get(uuid.UUID(ci.variant_id)) if ci.variant_id else None
        if variant is not None:
            variant.stock_quantity = variant.stock_quantity - ci.quantity
        else:
            p.stock_quantity = p.stock_quantity - ci.quantity
        db.add(OrderItem(
            order_id=order.id,
            product_id=p.id,
            variant_id=variant.id if variant else None,
            product_name=ci.name,
            unit=ci.unit,
            variant_label=ci.unit,
            unit_price=ci.unit_price,
            original_price=ci.original_price,
            quantity=ci.quantity,
            line_total=ci.line_total,
        ))
        db.add(Inventory(
            product_id=p.id, change_quantity=-ci.quantity, reason="ORDER",
            note=f"Order {order.order_number}", created_by=user.id,
        ))

    _history(db, order.id, OrderStatus.PENDING_PAYMENT, user.id, "Waiting for payment")

    if data.payment_method == PaymentMethod.UPI_MANUAL:
        payment = Payment(
            order_id=order.id, provider="manual_upi", provider_order_id=None,
            amount=order.total, currency="INR", status=PaymentStatus.PENDING,
        )
    else:
        provider = get_payment_provider()
        payment = Payment(
            order_id=order.id, provider=provider.name,
            provider_order_id=provider.create_order(order.order_number, order.total),
            amount=order.total, currency="INR", status=PaymentStatus.PENDING,
        )
    db.add(payment)
    db.query(CartItem).filter(CartItem.cart_id == cart.id).delete()
    db.commit()
    db.refresh(order)
    db.refresh(payment)

    return CheckoutOut(
        order=_order_out(db, order),
        payment=_manual_upi_payment_info(db, order, payment)
        if data.payment_method == PaymentMethod.UPI_MANUAL else PaymentInfoOut(
            provider=payment.provider, provider_order_id=payment.provider_order_id,
            amount=payment.amount, currency=payment.currency,
        ),
    )


# ---------- payment ----------

def confirm_payment(
    db: Session, user: User, provider_order_id: str, provider_payment_id: str, signature: str,
) -> OrderOut:
    payment = db.scalar(select(Payment).where(Payment.provider_order_id == provider_order_id))
    if payment is None:
        raise AppError("PAYMENT_NOT_FOUND", "This payment was not found.", 404)

    # Lock the order first (same lock order as cancel and expiry, so no deadlocks)
    order = _get_own_order(db, user, payment.order_id, lock=True)
    db.refresh(payment)

    if payment.status == PaymentStatus.PAID:
        return _order_out(db, order)          # already confirmed, safe to call twice

    if not get_payment_provider().verify(provider_order_id, provider_payment_id, signature):
        raise AppError("INVALID_PAYMENT_SIGNATURE", "Payment could not be verified.", 400)

    if order.status != OrderStatus.PENDING_PAYMENT:
        raise AppError(
            "ORDER_EXPIRED",
            "This order was cancelled because payment was not completed in time.", 409,
        )

    payment.status = PaymentStatus.PAID
    payment.provider_payment_id = provider_payment_id
    order.payment_status = PaymentStatus.PAID
    order.status = OrderStatus.PLACED
    _history(db, order.id, OrderStatus.PLACED, user.id, "Payment received")
    db.commit()
    db.refresh(order)
    return _order_out(db, order)


def mock_pay(db: Session, user: User, order_id: uuid.UUID) -> OrderOut:
    """Plays the part of the payment gateway. Only works when PAYMENT_PROVIDER=mock."""
    if settings.PAYMENT_PROVIDER != "mock":
        raise AppError("NOT_FOUND", "Not found.", 404)
    order = _get_own_order(db, user, order_id)
    payment = db.scalar(
        select(Payment).where(Payment.order_id == order.id, Payment.status == PaymentStatus.PENDING)
        .order_by(Payment.created_at.desc())
    )
    if payment is None:
        raise AppError("NO_PENDING_PAYMENT", "This order has no payment waiting.", 409)
    if payment.provider != "mock" or payment.provider_order_id is None:
        raise AppError(
            "MANUAL_PAYMENT_REQUIRED",
            "This order uses direct UPI. The store must verify the transfer.",
            409,
        )
    provider = MockPaymentProvider()
    payment_id = "mock_pay_" + secrets.token_hex(8)
    signature = provider.sign(payment.provider_order_id, payment_id)
    return confirm_payment(db, user, payment.provider_order_id, payment_id, signature)


def submit_manual_upi_reference(
    db: Session, user: User, order_id: uuid.UUID, data: ManualUpiReferenceRequest,
) -> OrderOut:
    order = _get_own_order(db, user, order_id, lock=True)
    if order.status != OrderStatus.PENDING_PAYMENT or order.payment_method != PaymentMethod.UPI_MANUAL:
        raise AppError("ORDER_NOT_AWAITING_UPI", "This order is not awaiting a UPI payment.", 409)
    payment = db.scalar(
        select(Payment).where(
            Payment.order_id == order.id,
            Payment.provider == "manual_upi",
            Payment.status == PaymentStatus.PENDING,
        ).order_by(Payment.created_at.desc()).with_for_update()
    )
    if payment is None:
        raise AppError("NO_PENDING_PAYMENT", "This order has no UPI payment waiting.", 409)
    reference = data.transaction_reference.strip()
    if payment.provider_payment_id:
        if payment.provider_payment_id == reference:
            return _order_out(db, order)
        raise AppError(
            "UPI_REFERENCE_ALREADY_SUBMITTED",
            "A payment reference has already been submitted for this order.",
            409,
        )
    duplicate = db.scalar(
        select(Payment.id).where(Payment.provider_payment_id == reference)
    )
    if duplicate is not None:
        raise AppError(
            "UPI_REFERENCE_ALREADY_USED",
            "This payment reference has already been submitted.",
            409,
        )
    payment.provider_payment_id = reference
    _history(
        db, order.id, OrderStatus.PENDING_PAYMENT, user.id,
        "Customer submitted a UPI transfer reference for store verification",
    )
    db.commit()
    db.refresh(order)
    return _order_out(db, order)


def get_manual_upi_payment_info(db: Session, user: User, order_id: uuid.UUID) -> PaymentInfoOut:
    order = _get_own_order(db, user, order_id)
    if order.status != OrderStatus.PENDING_PAYMENT or order.payment_method != PaymentMethod.UPI_MANUAL:
        raise AppError("ORDER_NOT_AWAITING_UPI", "This order is not awaiting a UPI payment.", 409)
    payment = db.scalar(
        select(Payment).where(
            Payment.order_id == order.id,
            Payment.provider == "manual_upi",
            Payment.status == PaymentStatus.PENDING,
        ).order_by(Payment.created_at.desc())
    )
    if payment is None:
        raise AppError("NO_PENDING_PAYMENT", "This order has no UPI payment waiting.", 409)
    return _manual_upi_payment_info(db, order, payment)


# ---------- cancel and expiry ----------

def _release_stock_and_cancel(db: Session, order: Order, changed_by, note: str) -> None:
    items = db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    ids = [i.product_id for i in items if i.product_id]
    products = {}
    if ids:
        products = {
            p.id: p for p in db.scalars(
                select(Product).where(Product.id.in_(ids)).order_by(Product.id).with_for_update()
            ).all()
        }
    for i in items:
        p = products.get(i.product_id)
        if p:
            p.stock_quantity = p.stock_quantity + i.quantity
            db.add(Inventory(
                product_id=p.id, change_quantity=i.quantity, reason="CANCELLED",
                note=f"Order {order.order_number}", created_by=changed_by,
            ))
    order.status = OrderStatus.CANCELLED
    if order.payment_status == PaymentStatus.PENDING:
        order.payment_status = PaymentStatus.FAILED
    for pay in db.scalars(
        select(Payment).where(Payment.order_id == order.id, Payment.status == PaymentStatus.PENDING)
    ).all():
        pay.status = PaymentStatus.FAILED
    _history(db, order.id, OrderStatus.CANCELLED, changed_by, note)


def cancel_own_order(db: Session, user: User, order_id: uuid.UUID) -> OrderOut:
    order = _get_own_order(db, user, order_id, lock=True)
    if order.status != OrderStatus.PENDING_PAYMENT:
        raise AppError(
            "CANNOT_CANCEL",
            "Only orders waiting for payment can be cancelled here. Please contact the store.", 409,
        )
    submitted_reference = db.scalar(
        select(Payment.id).where(
            Payment.order_id == order.id,
            Payment.provider == "manual_upi",
            Payment.provider_payment_id.is_not(None),
        )
    )
    if submitted_reference is not None:
        raise AppError(
            "UPI_PAYMENT_UNDER_REVIEW",
            "A UPI reference has been submitted. Contact the store instead of cancelling while it is being verified.",
            409,
        )
    _release_stock_and_cancel(db, order, user.id, "Cancelled by customer")
    db.commit()
    db.refresh(order)
    return _order_out(db, order)


def expire_unpaid_orders(db: Session) -> int:
    cutoff = _now() - timedelta(minutes=settings.PAYMENT_EXPIRY_MINUTES)
    recent_manual_references = select(Payment.order_id).where(
        Payment.provider == "manual_upi",
        Payment.provider_payment_id.is_not(None),
        Payment.updated_at >= _now() - timedelta(hours=24),
    )
    orders = db.scalars(
        select(Order).where(
            Order.status == OrderStatus.PENDING_PAYMENT,
            Order.created_at < cutoff,
            Order.id.not_in(recent_manual_references),
        )
        .with_for_update(skip_locked=True)
    ).all()
    for o in orders:
        _release_stock_and_cancel(db, o, None, "Payment not completed in time")
    db.commit()
    return len(orders)


def run_expiry_job() -> None:
    db = SessionLocal()
    try:
        count = expire_unpaid_orders(db)
        if count:
            logger.info("Expired %s unpaid order(s)", count)
    except Exception:
        db.rollback()
        logger.exception("Order expiry job failed")
    finally:
        db.close()


# ---------- reading orders ----------

def list_orders(db: Session, user: User, page: int, page_size: int) -> list[OrderOut]:
    rows = db.scalars(
        select(Order).where(Order.customer_id == user.id)
        .order_by(Order.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return [_order_out(db, o) for o in rows]


def get_order(db: Session, user: User, order_id: uuid.UUID) -> OrderOut:
    return _order_out(db, _get_own_order(db, user, order_id))


def confirm_external_delivery(db: Session, user: User, order_id: uuid.UUID) -> OrderOut:
    order = _get_own_order(db, user, order_id, lock=True)
    if order.seller_delivery_available:
        raise AppError("NOT_EXTERNAL_DELIVERY", "This order is being delivered by the seller.", 409)
    if order.payment_status != PaymentStatus.PAID:
        raise AppError("PAYMENT_REQUIRED", "Complete payment before confirming delivery.", 409)
    if order.status != OrderStatus.READY_FOR_DELIVERY:
        raise AppError(
            "ORDER_NOT_READY",
            "The store must mark the order ready for pickup before you confirm receipt.",
            409,
        )
    order.status = OrderStatus.DELIVERED
    _history(db, order.id, OrderStatus.DELIVERED, user.id, "Customer confirmed external delivery")
    db.commit()
    db.refresh(order)
    return _order_out(db, order)