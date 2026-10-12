from abc import ABC, abstractmethod

from app.core.config import settings


class SmsProvider(ABC):
    """Later: add MSG91Provider or TwilioProvider here. The rest of the app stays the same."""

    @abstractmethod
    def send(self, phone: str, message: str) -> None: ...


class ConsoleSmsProvider(SmsProvider):
    """Testing only: prints the message in the uvicorn terminal instead of sending an SMS."""

    def send(self, phone: str, message: str) -> None:
        print(f"\n[SMS to {phone}] {message}\n", flush=True)


def get_sms_provider() -> SmsProvider:
    if settings.SMS_PROVIDER == "console":
        return ConsoleSmsProvider()
    raise RuntimeError(f"Unknown SMS_PROVIDER: {settings.SMS_PROVIDER}")