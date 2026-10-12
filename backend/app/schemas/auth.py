from pydantic import BaseModel, EmailStr, Field, field_validator

from app.utils.phone import normalize_indian_phone


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=10, max_length=20)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, v: str) -> str:
        phone = normalize_indian_phone(v)
        if phone is None:
            raise ValueError("Enter a valid 10-digit Indian mobile number")
        return phone


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class ProfileUpdate(BaseModel):
    """Phone cannot be changed here. A change would need a new OTP check."""
    full_name: str | None = Field(default=None, min_length=2, max_length=120)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class VerifyOtpRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class OtpSentOut(BaseModel):
    sent: bool
    expires_in_seconds: int
    resend_after_seconds: int
    dev_otp: str | None = None     # only filled when OTP_DEV_MODE=true


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    phone: str | None
    phone_verified: bool
    role: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
    otp: OtpSentOut | None = None