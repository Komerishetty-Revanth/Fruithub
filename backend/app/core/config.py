from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    CORS_ORIGINS: str = ""
    DEFAULT_DELIVERY_RADIUS_KM: float = 5.0
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_MB: int = 5
    DELIVERY_FEE: float = 20.0
    FREE_DELIVERY_ABOVE: float = 500.0
    PAYMENT_PROVIDER: str = "mock"
    PAYMENT_EXPIRY_MINUTES: int = 15

    # Phone verification
    SMS_PROVIDER: str = "console"       # "console" prints the OTP in the terminal
    OTP_DEV_MODE: bool = True           # True: API also returns the OTP. MUST be False in production
    OTP_EXPIRY_MINUTES: int = 5
    OTP_RESEND_SECONDS: int = 30
    OTP_MAX_ATTEMPTS: int = 5
    OTP_MAX_PER_HOUR: int = 5

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()