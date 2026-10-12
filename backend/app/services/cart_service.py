import uuid
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.models import Cart, CartItem, Product, ProductVariant, Store, User
from app.schemas.cart import CartItemAdd, CartItemOut, CartItemUpdate, CartOut
from app.services import offer_service

CENT = Decimal("0.01")
MAX_QTY = Decimal("50")


def _money(x: Decimal) -> Decimal:
    return x.quantize(CENT, ROUND_HALF_UP)


def _get_or_create_cart(db: Session, user: User) -> Cart:
    cart = db.scalar(select(Cart).where(Cart.user_id == user.id))
    if cart is None:
        cart = Cart(user_id=user.id)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    return cart


def _buyable_product(db: Session, product_id: uuid.UUID) -> Product:
    """A product customers are allowed to buy: active, in an approved and active store."""
    p = db.scalar(
        select(Product).join(Store, Product.store_id == Store.id).where(
            Product.id == product_id, Product.is_active.is_(True),
            Store.is_active.is_(True), Store.is_approved.is_(True),
        )
    )
    if p is None:
        raise AppError("PRODUCT_NOT_FOUND", "This product was not found.", 404)
    return p


def _get_variant_for_product(db: Session, product_id: uuid.UUID, variant_id: uuid.UUID | None) -> ProductVariant | None:
    if variant_id is None:
        return None
    variant = db.scalar(
        select(ProductVariant).where(
            ProductVariant.id == variant_id,
            ProductVariant.product_id == product_id,
        )
    )
    if variant is None:
        raise AppError("VARIANT_NOT_FOUND", "This product variant does not exist for this product.", 404)
    return variant


def _check_quantity(p: Product, qty: Decimal) -> None:
    unit = p.unit
    if unit in ("piece", "dozen", "bottle", "pack") and qty != qty.to_integral_value():
        raise AppError("INVALID_QUANTITY", f"Quantity must be a whole number for {unit}.", 422)


def _check_stock(p: Product, qty: Decimal) -> None:
    if not p.is_available or p.stock_quantity <= 0:
        raise AppError("OUT_OF_STOCK", f"{p.name} is out of stock.", 422)
    if qty > p.stock_quantity:
        raise AppError(
            "INSUFFICIENT_STOCK", f"Only {p.stock_quantity.normalize():f} {p.unit} of {p.name} available.", 422
        )


def _check_variant_stock(v: ProductVariant, qty: Decimal, name: str) -> None:
    if not v.is_active or v.stock_quantity <= 0:
        raise AppError("OUT_OF_STOCK", f"{name} is out of stock.", 422)
    if qty > v.stock_quantity:
        raise AppError(
            "INSUFFICIENT_STOCK",
            f"Only {v.stock_quantity.normalize():f} {v.size_unit} of {name} available.",
            422,
        )


def build_cart(db: Session, cart: Cart) -> CartOut:
    """Calculates all prices. Checkout will reuse this, so the cart and the order always match."""
    rows = db.execute(
        select(CartItem, Product, ProductVariant)
        .join(Product, CartItem.product_id == Product.id)
        .outerjoin(ProductVariant, ProductVariant.id == CartItem.variant_id)
        .where(CartItem.cart_id == cart.id)
        .order_by(Product.name)
    ).all()

    if not rows:
        zero = Decimal("0.00")
        return CartOut(store_id=None, items=[], item_count=0, subtotal=zero,
                       discount_total=zero, delivery_fee=zero, total=zero, has_issues=False)

    store_id = rows[0][1].store_id
    offers = offer_service.live_offers(db, store_id)

    items: list[CartItemOut] = []
    original_total = Decimal(0)
    net_total = Decimal(0)
    has_issues = False

    for item, p, v in rows:
        if v is not None:
            original_price = v.price
            unit_price = v.discount_price if v.discount_price is not None else v.price
            stock = v.stock_quantity
            unit = v.label
            issue = None
            if not p.is_active:
                issue = "This product is no longer available."
            elif not v.is_active:
                issue = "This variant is no longer available."
            elif stock <= 0:
                issue = "Out of stock."
            elif item.quantity > stock:
                issue = f"Only {stock.normalize():f} {v.label} left."
            if issue:
                has_issues = True
            items.append(CartItemOut(
                product_id=str(p.id), variant_id=str(v.id), name=p.name, unit=unit,
                image_url=p.image_url, asset_3d_url=p.asset_3d_url, original_price=original_price,
                unit_price=unit_price, quantity=item.quantity,
                line_total=_money(unit_price * item.quantity),
                available_stock=stock, is_available=issue is None, issue=issue,
            ))
            original_total += _money(original_price * item.quantity)
            net_total += _money(unit_price * item.quantity)
            continue

        unit_price = offer_service.unit_price_for(db, p, offers)
        line_total = _money(unit_price * item.quantity)
        original_total += _money(p.price * item.quantity)
        net_total += line_total

        issue = None
        if not p.is_active:
            issue = "This product is no longer available."
        elif not p.is_available or p.stock_quantity <= 0:
            issue = "Out of stock."
        elif item.quantity > p.stock_quantity:
            issue = f"Only {p.stock_quantity.normalize():f} {p.unit} left."
        if issue:
            has_issues = True

        items.append(CartItemOut(
            product_id=str(p.id), variant_id=None, name=p.name, unit=p.unit, image_url=p.image_url,
            asset_3d_url=p.asset_3d_url,
            original_price=p.price, unit_price=unit_price, quantity=item.quantity,
            line_total=line_total, available_stock=p.stock_quantity,
            is_available=issue is None, issue=issue,
        ))

    fixed = _money(offer_service.best_fixed_discount(offers, store_id, net_total))
    after_discount = net_total - fixed
    fee = Decimal(str(settings.DELIVERY_FEE))
    if after_discount >= Decimal(str(settings.FREE_DELIVERY_ABOVE)):
        fee = Decimal(0)

    return CartOut(
        store_id=str(store_id), items=items, item_count=len(items),
        subtotal=_money(original_total),
        discount_total=_money(original_total - net_total + fixed),
        delivery_fee=_money(fee), total=_money(after_discount + fee),
        has_issues=has_issues,
    )


def get_cart(db: Session, user: User) -> CartOut:
    return build_cart(db, _get_or_create_cart(db, user))


def add_item(db: Session, user: User, data: CartItemAdd) -> CartOut:
    p = _buyable_product(db, data.product_id)
    variant = _get_variant_for_product(db, p.id, data.variant_id)
    _check_quantity(p, data.quantity)
    cart = _get_or_create_cart(db, user)

    other_store = db.scalar(
        select(Product.store_id).join(CartItem, CartItem.product_id == Product.id)
        .where(CartItem.cart_id == cart.id, Product.store_id != p.store_id).limit(1)
    )
    if other_store is not None:
        raise AppError(
            "CART_STORE_MISMATCH",
            "Your cart has items from another store. Clear it to add this item.", 409,
        )

    item = db.scalar(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.product_id == p.id,
            CartItem.variant_id == data.variant_id,
        )
    )
    new_qty = (item.quantity if item else Decimal(0)) + data.quantity
    if new_qty > MAX_QTY:
        raise AppError("QUANTITY_TOO_HIGH", f"You can order up to {MAX_QTY:g} per item.", 422)
    if variant is not None:
        _check_variant_stock(variant, new_qty, p.name)
    else:
        _check_stock(p, new_qty)

    if item:
        item.quantity = new_qty
    else:
        db.add(CartItem(
            cart_id=cart.id,
            product_id=p.id,
            variant_id=data.variant_id,
            quantity=new_qty,
            variant_label=variant.label if variant else None,
            variant_price=(variant.discount_price if variant and variant.discount_price is not None else variant.price) if variant else None,
        ))
    db.commit()
    return build_cart(db, cart)


def update_item(db: Session, user: User, product_id: uuid.UUID, data: CartItemUpdate, variant_id: uuid.UUID | None = None) -> CartOut:
    cart = _get_or_create_cart(db, user)
    item = db.scalar(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.product_id == product_id,
            CartItem.variant_id == variant_id,
        )
    )
    if item is None:
        raise AppError("ITEM_NOT_IN_CART", "This item is not in your cart.", 404)
    p = _buyable_product(db, product_id)
    variant = _get_variant_for_product(db, p.id, variant_id)
    _check_quantity(p, data.quantity)
    if variant is not None:
        _check_variant_stock(variant, data.quantity, p.name)
    else:
        _check_stock(p, data.quantity)
    item.quantity = data.quantity
    item.variant_label = variant.label if variant else item.variant_label
    item.variant_price = (variant.discount_price if variant and variant.discount_price is not None else variant.price) if variant else item.variant_price
    db.commit()
    return build_cart(db, cart)


def remove_item(db: Session, user: User, product_id: uuid.UUID, variant_id: uuid.UUID | None = None) -> CartOut:
    cart = _get_or_create_cart(db, user)
    item = db.scalar(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.product_id == product_id,
            CartItem.variant_id == variant_id,
        )
    )
    if item is None:
        raise AppError("ITEM_NOT_IN_CART", "This item is not in your cart.", 404)
    db.delete(item)
    db.commit()
    return build_cart(db, cart)


def clear_cart(db: Session, user: User) -> CartOut:
    cart = _get_or_create_cart(db, user)
    db.query(CartItem).filter(CartItem.cart_id == cart.id).delete()
    db.commit()
    return build_cart(db, cart)