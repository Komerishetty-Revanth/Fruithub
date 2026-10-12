import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Order, OrderItem, OrderStatus, Product, Review, User
from app.schemas.review import ReviewCreate, ReviewListOut, ReviewOut
from app.services import product_service


def _display_name(u: User | None) -> str:
    if u is None:
        return "Customer"
    parts = u.full_name.split()
    if not parts:
        return "Customer"
    return parts[0] if len(parts) == 1 else f"{parts[0]} {parts[-1][0]}."


def _out(r: Review, u: User | None) -> ReviewOut:
    return ReviewOut(
        id=str(r.id), rating=r.rating, comment=r.comment,
        reviewer_name=_display_name(u), created_at=r.created_at,
    )


def _recalculate(db: Session, product_id: uuid.UUID) -> None:
    avg, count = db.execute(
        select(func.avg(Review.rating), func.count(Review.id)).where(Review.product_id == product_id)
    ).one()
    p = db.get(Product, product_id)
    p.rating = round(float(avg), 1) if avg else 0
    p.rating_count = count or 0


def list_reviews(db: Session, product_id: uuid.UUID, page: int, page_size: int) -> ReviewListOut:
    product_service.get_product(db, product_id)       # 404 if not publicly visible
    total = db.scalar(select(func.count(Review.id)).where(Review.product_id == product_id)) or 0
    rows = db.execute(
        select(Review, User).join(User, Review.user_id == User.id)
        .where(Review.product_id == product_id)
        .order_by(Review.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return ReviewListOut(
        items=[_out(r, u) for r, u in rows], page=page, page_size=page_size, total=total,
    )


def save_review(db: Session, user: User, product_id: uuid.UUID, data: ReviewCreate) -> ReviewOut:
    product_service.get_product(db, product_id)
    bought = db.scalar(
        select(OrderItem.id).join(Order, OrderItem.order_id == Order.id).where(
            Order.customer_id == user.id, Order.status == OrderStatus.DELIVERED,
            OrderItem.product_id == product_id,
        ).limit(1)
    )
    if bought is None:
        raise AppError(
            "NOT_PURCHASED", "You can review a product after you have received it.", 403
        )
    comment = (data.comment or "").strip() or None
    review = db.scalar(
        select(Review).where(Review.user_id == user.id, Review.product_id == product_id)
    )
    if review:
        review.rating, review.comment = data.rating, comment
    else:
        review = Review(user_id=user.id, product_id=product_id, rating=data.rating, comment=comment)
        db.add(review)
    db.flush()
    _recalculate(db, product_id)
    db.commit()
    db.refresh(review)
    return _out(review, user)


def delete_review(db: Session, user: User, product_id: uuid.UUID) -> None:
    review = db.scalar(
        select(Review).where(Review.user_id == user.id, Review.product_id == product_id)
    )
    if review is None:
        raise AppError("REVIEW_NOT_FOUND", "You have not reviewed this product.", 404)
    db.delete(review)
    db.flush()
    _recalculate(db, product_id)
    db.commit()