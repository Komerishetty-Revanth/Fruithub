from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.errors import AppError
from app.core.rate_limit import limiter
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User, UserRole
from app.schemas.auth import (
    ChangePasswordRequest, LoginRequest, OtpSentOut, ProfileUpdate, RegisterRequest,
    TokenOut, UserOut, VerifyOtpRequest,
)
from app.services import otp_service

router = APIRouter(prefix="/auth", tags=["Auth"])


def user_out(u: User) -> UserOut:
    return UserOut(
        id=str(u.id), email=u.email, full_name=u.full_name, phone=u.phone,
        phone_verified=u.phone_verified, role=u.role.value,
    )


@router.post("/register", response_model=TokenOut, status_code=201)
@limiter.limit("20/hour")
def register(request: Request, data: RegisterRequest, db: Session = Depends(get_db)):
    email = data.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise AppError("EMAIL_EXISTS", "An account with this email already exists.", 409)
    if db.scalar(select(User).where(User.phone == data.phone)):
        raise AppError("PHONE_EXISTS", "An account with this mobile number already exists.", 409)

    # Public registration always creates a CUSTOMER. Owners are created by the admin.
    user = User(
        email=email, full_name=data.full_name.strip(), phone=data.phone, phone_verified=False,
        password_hash=hash_password(data.password), role=UserRole.CUSTOMER,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError("ACCOUNT_EXISTS", "An account with this email or mobile number already exists.", 409)
    db.refresh(user)

    otp = otp_service.send_otp(db, user)
    token = create_access_token(str(user.id), user.role.value)
    return TokenOut(access_token=token, user=user_out(user), otp=otp)


@router.post("/login", response_model=TokenOut)
@limiter.limit("10/minute")
def login(request: Request, data: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    # Same message for wrong email or wrong password, so attackers learn nothing.
    if user is None or not verify_password(data.password, user.password_hash):
        raise AppError("INVALID_CREDENTIALS", "Incorrect email or password.", 401)
    if not user.is_active:
        raise AppError("ACCOUNT_DISABLED", "This account has been disabled.", 403)
    token = create_access_token(str(user.id), user.role.value)
    return TokenOut(access_token=token, user=user_out(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.patch("/me", response_model=UserOut)
def update_me(data: ProfileUpdate, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    changes = data.model_dump(exclude_unset=True)
    if "full_name" in changes:
        if not changes["full_name"] or not changes["full_name"].strip():
            raise AppError("VALIDATION_ERROR", "Name cannot be empty.", 422)
        user.full_name = changes["full_name"].strip()
    db.commit()
    db.refresh(user)
    return user_out(user)


@router.post("/phone/send", response_model=OtpSentOut)
@limiter.limit("10/hour")
def send_phone_otp(request: Request, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """Sends a new OTP to the logged-in user's mobile number."""
    return otp_service.send_otp(db, user)


@router.post("/phone/verify", response_model=UserOut)
@limiter.limit("20/hour")
def verify_phone(request: Request, data: VerifyOtpRequest,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return user_out(otp_service.verify_otp(db, user, data.code))


@router.post("/change-password")
@limiter.limit("5/minute")
def change_password(request: Request, data: ChangePasswordRequest,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(data.current_password, user.password_hash):
        raise AppError("INVALID_CREDENTIALS", "Your current password is incorrect.", 400)
    if data.current_password == data.new_password:
        raise AppError("VALIDATION_ERROR", "Choose a new password that is different.", 422)
    user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"success": True, "message": "Password changed."}