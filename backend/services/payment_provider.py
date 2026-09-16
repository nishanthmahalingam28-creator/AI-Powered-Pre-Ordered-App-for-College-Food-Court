"""
Payment Provider Abstraction Layer for College Food Court Application.

Defines the pluggable PaymentProvider base class and the official RazorpayProvider implementation.
Supports:
- UPI (Google Pay, PhonePe, Paytm, BHIM)
- RuPay / Debit / Credit Cards
- NetBanking
- Test / Sandbox Mode with authentic HMAC-SHA256 cryptographic signature validation
- Strict Production Mode validation (rejects test/placeholder keys in production)
"""

import os
import hmac
import hashlib
import secrets
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger("food_court.payment_provider")

try:
    import razorpay
    RAZORPAY_INSTALLED = True
except ImportError:
    RAZORPAY_INSTALLED = False
    logger.warning("razorpay package not installed. Falling back to internal cryptographic routines.")


class PaymentProvider(ABC):
    """Abstract Base Class for Payment Gateway Providers."""

    @abstractmethod
    def create_order(self, amount_paise: int, currency: str = "INR", receipt: str = None, notes: dict = None) -> dict:
        """Creates a payment order at the payment gateway."""
        pass

    @abstractmethod
    def verify_payment_signature(self, gateway_order_id: str, gateway_payment_id: str, gateway_signature: str) -> bool:
        """Verifies the authenticity of the client payment signature server-side."""
        pass

    @abstractmethod
    def verify_webhook_signature(self, raw_body: bytes, webhook_signature: str) -> bool:
        """Verifies the webhook signature using the configured webhook secret."""
        pass

    @abstractmethod
    def fetch_payment(self, gateway_payment_id: str) -> dict:
        """Fetches authoritative payment record from gateway."""
        pass


class RazorpayProvider(PaymentProvider):
    """
    Official Razorpay Gateway Integration.
    Adheres strictly to Razorpay's official API specifications, paise currency conventions,
    and HMAC-SHA256 signature verification standards.
    """

    def __init__(self, key_id: str = None, key_secret: str = None, webhook_secret: str = None, environment: str = None):
        flask_env = os.getenv("FLASK_ENV", "production").lower()
        self.is_development = flask_env in ("development", "dev", "test", "testing")
        self.environment = environment or os.getenv("PAYMENT_ENVIRONMENT", "test" if self.is_development else "production").lower()
        is_prod = (not self.is_development) or (self.environment == "production")

        self.key_id = (key_id or os.getenv("RAZORPAY_KEY_ID") or "").strip()
        self.key_secret = (key_secret or os.getenv("RAZORPAY_KEY_SECRET") or "").strip()
        self.webhook_secret = (webhook_secret or os.getenv("RAZORPAY_WEBHOOK_SECRET") or "").strip()

        # Strict Production Guard: Fail closed if production lacks real credentials
        if is_prod:
            if not self.key_id or not self.key_secret:
                raise RuntimeError(
                    "FATAL: RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are required in production mode. "
                    "Refusing startup with missing payment credentials."
                )
            if self.key_id.startswith("rzp_test_") or "YourKey" in self.key_id:
                raise RuntimeError(
                    "FATAL: Production mode detected but test/placeholder RAZORPAY_KEY_ID was provided. "
                    "Live credentials (e.g. rzp_live_...) are strictly required."
                )
            if not self.webhook_secret or "YourWebhook" in self.webhook_secret:
                raise RuntimeError(
                    "FATAL: RAZORPAY_WEBHOOK_SECRET is required in production mode for webhook signature verification."
                )
        else:
            # Development / Sandbox fallbacks if not explicitly provided in environment
            if not self.key_id:
                self.key_id = "rzp_test_collegefoodcourt2026"
            if not self.key_secret:
                self.key_secret = "rzp_sec_kpriet_dev_secret_key_32b"
            if not self.webhook_secret:
                self.webhook_secret = "rzp_wh_sec_kpriet_webhook_32b_key"

        self.client = None
        if RAZORPAY_INSTALLED and self.key_id and self.key_secret:
            try:
                self.client = razorpay.Client(auth=(self.key_id, self.key_secret))
            except Exception as e:
                logger.error("Failed to initialize razorpay.Client: %s", e)

    def create_order(self, amount_paise: int, currency: str = "INR", receipt: str = None, notes: dict = None) -> dict:
        """
        Creates an authoritative gateway order.
        Amount must be an integer in paise (e.g., ₹150.00 = 15000 paise).
        """
        if amount_paise <= 0:
            raise ValueError("Order amount in paise must be strictly positive.")

        receipt_id = receipt or f"RCPT-{secrets.token_hex(6).upper()}"
        order_payload = {
            "amount": int(amount_paise),
            "currency": currency.upper(),
            "receipt": receipt_id,
            "payment_capture": 1,
            "notes": notes or {}
        }

        # If live client is configured and not running in offline test harness, call Razorpay API
        if self.client and not self.is_development:
            try:
                rzp_order = self.client.order.create(data=order_payload)
                return {
                    "gateway_order_id": rzp_order["id"],
                    "amount": rzp_order["amount"],
                    "currency": rzp_order["currency"],
                    "receipt": rzp_order["receipt"],
                    "status": rzp_order["status"],
                    "raw": rzp_order
                }
            except Exception as e:
                logger.error("Razorpay API order creation failed: %s", e)
                raise RuntimeError(f"Payment gateway order creation failed: {e}")

        # Sandbox / Local deterministic generation for development & testing
        gateway_order_id = f"order_{secrets.token_hex(8)}"
        return {
            "gateway_order_id": gateway_order_id,
            "amount": int(amount_paise),
            "currency": currency.upper(),
            "receipt": receipt_id,
            "status": "created",
            "raw": {
                "id": gateway_order_id,
                "entity": "order",
                "amount": int(amount_paise),
                "amount_paid": 0,
                "amount_due": int(amount_paise),
                "currency": currency.upper(),
                "receipt": receipt_id,
                "status": "created",
                "notes": notes or {}
            }
        }

    def verify_payment_signature(self, gateway_order_id: str, gateway_payment_id: str, gateway_signature: str) -> bool:
        """
        Verifies customer payment signature returned by Razorpay Checkout.
        Formula: HMAC-SHA256(order_id + "|" + payment_id, secret) == signature
        Uses constant-time comparison to prevent timing attacks.
        """
        if not gateway_order_id or not gateway_payment_id or not gateway_signature:
            return False

        message = f"{gateway_order_id}|{gateway_payment_id}".encode("utf-8")
        expected_signature = hmac.new(
            self.key_secret.encode("utf-8"),
            message,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(str(gateway_signature).strip(), str(expected_signature).strip())

    def verify_webhook_signature(self, raw_body: bytes, webhook_signature: str) -> bool:
        """
        Verifies the authenticity of Razorpay Webhook payloads.
        Formula: HMAC-SHA256(raw_request_body, webhook_secret) == X-Razorpay-Signature
        """
        if not raw_body or not webhook_signature:
            return False

        if isinstance(raw_body, str):
            raw_body = raw_body.encode("utf-8")

        expected_signature = hmac.new(
            self.webhook_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(str(webhook_signature).strip(), str(expected_signature).strip())

    def fetch_payment(self, gateway_payment_id: str) -> dict:
        """Fetches payment details from Razorpay or returns verified structure in test mode."""
        if not gateway_payment_id:
            raise ValueError("gateway_payment_id is required.")

        if self.client and not self.is_development:
            try:
                return self.client.payment.fetch(gateway_payment_id)
            except Exception as e:
                logger.error("Failed to fetch payment %s from Razorpay: %s", gateway_payment_id, e)
                raise RuntimeError(f"Gateway inquiry error: {e}")

        # Sandbox mock fetch
        return {
            "id": gateway_payment_id,
            "entity": "payment",
            "status": "captured",
            "currency": "INR",
            "method": "upi"
        }

    def generate_test_signature(self, gateway_order_id: str, gateway_payment_id: str) -> str:
        """Utility for automated and manual testing to generate valid HMAC-SHA256 signature."""
        msg = f"{gateway_order_id}|{gateway_payment_id}".encode("utf-8")
        return hmac.new(self.key_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

    def generate_test_webhook_signature(self, raw_body: bytes) -> str:
        """Utility for automated and manual testing to generate valid webhook signature."""
        if isinstance(raw_body, str):
            raw_body = raw_body.encode("utf-8")
        return hmac.new(self.webhook_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


# Singleton instance
_payment_provider = None


def get_payment_provider() -> PaymentProvider:
    """Returns the singleton PaymentProvider instance."""
    global _payment_provider
    if _payment_provider is None:
        provider_type = os.getenv("PAYMENT_PROVIDER", "razorpay").lower()
        if provider_type == "razorpay":
            _payment_provider = RazorpayProvider()
        else:
            raise ValueError(f"Unsupported payment provider: {provider_type}")
    return _payment_provider
