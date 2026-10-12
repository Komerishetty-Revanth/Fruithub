import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.models import PhoneOtp, User
from app.schemas.auth import OtpSentOut
from app.services.sms_service import get_sms_provider


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(phone: str, code: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def send_otp(db: Session, user: User) -> OtpSentOut:
    if not user.phone:
        raise AppError("NO_PHONE", "This account has no mobile number.", 422)
    if user.phone_verified:
        raise AppError("ALREADY_VERIFIED", "Your mobile number is already verified.", 409)

    now = _now()
    last = db.scalar(
        select(PhoneOtp).where(PhoneOtp.user_id == user.id).order_by(PhoneOtp.created_at.desc())
    )
    if last is not None:
        wait = settings.OTP_RESEND_SECONDS - (now - last.created_at).total_seconds()
        if wait > 0:
            raise AppError("OTP_TOO_SOON", f"Please wait {int(wait) + 1} seconds before asking for a new code.", 429)

    sent_last_hour = db.scalar(
        select(func.count(PhoneOtp.id)).where(
            PhoneOtp.user_id == user.id, PhoneOtp.created_at > now - timedelta(hours=1)
        )
    ) or 0
    if sent_last_hour >= settings.OTP_MAX_PER_HOUR:
        raise AppError("OTP_LIMIT", "Too many codes requested. Please try again in an hour.", 429)

    code = f"{secrets.randbelow(10**6):06d}"
    db.execute(  # older codes stop working
        update(PhoneOtp).where(PhoneOtp.user_id == user.id, PhoneOtp.consumed.is_(False)).values(consumed=True)
    )
    db.add(PhoneOtp(
        user_id=user.id, phone=user.phone, code_hash=_hash(user.phone, code),
        expires_at=now + timedelta(minutes=settings.OTP_EXPIRY_MINUTES),
    ))
    db.commit()

    get_sms_provider().send(
        user.phone, f"Your FruitHub code is {code}. It is valid for {settings.OTP_EXPIRY_MINUTES} minutes."
    )
    return OtpSentOut(
        sent=True,
        expires_in_seconds=settings.OTP_EXPIRY_MINUTES * 60,
        resend_after_seconds=settings.OTP_RESEND_SECONDS,
        dev_otp=code if settings.OTP_DEV_MODE else None,
    )


def verify_otp(db: Session, user: User, code: str) -> User:
    if user.phone_verified:
        return user
    otp = db.scalar(
        select(PhoneOtp).where(
            PhoneOtp.user_id == user.id, PhoneOtp.phone == user.phone, PhoneOtp.consumed.is_(False)
        ).order_by(PhoneOtp.created_at.desc())
    )
    if otp is None:
        raise AppError("OTP_NOT_FOUND", "Please ask for a new code.", 400)
    if otp.expires_at < _now():
        raise AppError("OTP_EXPIRED", "This code has expired. Please ask for a new one.", 400)
    if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
        raise AppError("OTP_LOCKED", "Too many wrong tries. Please ask for a new code.", 429)

    otp.attempts += 1
    if not hmac.compare_digest(otp.code_hash, _hash(user.phone, code)):
        db.commit()   # keep the failed attempt
        raise AppError("INVALID_OTP", "That code is not correct.", 400)

    otp.consumed = True
    user.phone_verified = True
    db.commit()
    db.refresh(user)
    return user