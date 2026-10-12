import hashlib
import hmac
import secrets
from abc import ABC, abstractmethod
from decimal import Decimal

from app.core.config import settings


class PaymentProvider(ABC):
    """Later: add RazorpayProvider here. The rest of the app stays the same."""
    name: str

    @abstractmethod
    def create_order(self, order_number: str, amount: Decimal) -> str:
        """Creates the payment at the gateway and returns the gateway's order id."""

    @abstractmethod
    def verify(self, provider_order_id: str, provider_payment_id: str, signature: str) -> bool:
        """True only if the gateway really signed this payment."""


class MockPaymentProvider(PaymentProvider):
    """Fake gateway for local testing. No signup, no real money."""
    name = "mock"

    def create_order(self, order_number: str, amount: Decimal) -> str:
        return "mock_order_" + secrets.token_hex(8)

    def sign(self, provider_order_id: str, provider_payment_id: str) -> str:
        message = f"{provider_order_id}|{provider_payment_id}".encode()
        return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()

    def verify(self, provider_order_id: str, provider_payment_id: str, signature: str) -> bool:
        expected = self.sign(provider_order_id, provider_payment_id)
        return hmac.compare_digest(expected, signature)


def get_payment_provider() -> PaymentProvider:
    if settings.PAYMENT_PROVIDER == "mock":
        return MockPaymentProvider()
    raise RuntimeError(f"Unknown PAYMENT_PROVIDER: {settings.PAYMENT_PROVIDER}")