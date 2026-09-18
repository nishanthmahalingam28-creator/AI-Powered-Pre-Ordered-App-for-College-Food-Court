"""
SMS Delivery & Mobile Verification Service for KPRIET Smart Food Court.
Provides provider abstraction for mobile OTP verification with Twilio Verify REST API.

Architectural Invariants:
1. Environment-controlled provider selection (SMS_PROVIDER=twilio_verify or twilio).
2. Uses Twilio Verify REST API:
   - POST https://verify.twilio.com/v2/Services/{TWILIO_VERIFY_SERVICE_SID}/Verifications
   - POST https://verify.twilio.com/v2/Services/{TWILIO_VERIFY_SERVICE_SID}/VerificationCheck
3. Safe development / test mode with in-memory test hooks (never logs OTP or exposes secrets).
4. Zero credential leakage: secrets and auth tokens are never logged or stored.
5. Production safety: strictly suppresses OTP from production API responses and fails safely if provider unconfigured.
6. Indian mobile E.164 normalization (+91XXXXXXXXXX).
"""

import os
import re
import logging
from typing import Dict, Any, Tuple, Optional
import requests

logger = logging.getLogger("food_court.services.sms")


class SMSService:
    """Manages transactional mobile verification via Twilio Verify."""

    # In-memory test hooks for automated test suites (never logged or written to disk)
    _last_dev_sms: Optional[Dict[str, Any]] = None
    _dev_verifications: Dict[str, str] = {}

    @classmethod
    def get_sms_config(cls) -> Dict[str, Any]:
        """Reads and normalizes SMS provider configuration from environment variables."""
        return {
            "provider": (os.getenv("SMS_PROVIDER") or "twilio_verify").strip().lower(),
            "twilio_account_sid": (os.getenv("TWILIO_ACCOUNT_SID") or "").strip(),
            "twilio_auth_token": (os.getenv("TWILIO_AUTH_TOKEN") or "").strip(),
            "twilio_phone_number": (os.getenv("TWILIO_PHONE_NUMBER") or "").strip(),
            "twilio_verify_service_sid": (os.getenv("TWILIO_VERIFY_SERVICE_SID") or "").strip(),
        }

    @classmethod
    def is_configured(cls) -> bool:
        """Returns True only if an SMS provider with non-placeholder credentials is configured."""
        cfg = cls.get_sms_config()
        provider = cfg["provider"]
        if not provider:
            return False

        if provider in ("twilio_verify", "twilio-verify"):
            sid = cfg["twilio_account_sid"]
            token = cfg["twilio_auth_token"]
            service_sid = cfg["twilio_verify_service_sid"]
            if not sid or not token or not service_sid:
                return False
            # Check for dummy placeholders
            if any(p in sid.lower() for p in ("your_", "xxxx", "placeholder")) or \
               any(p in token.lower() for p in ("your_", "xxxx", "placeholder")) or \
               any(p in service_sid.lower() for p in ("your_", "xxxx", "placeholder")):
                return False
            return True

        if provider == "twilio":
            sid = cfg["twilio_account_sid"]
            token = cfg["twilio_auth_token"]
            phone = cfg["twilio_phone_number"]
            if not sid or not token or not phone:
                return False
            if any(p in sid.lower() for p in ("your_", "xxxx", "placeholder")) or \
               any(p in token.lower() for p in ("your_", "xxxx", "placeholder")):
                return False
            return True

        return False

    @classmethod
    def normalize_phone(cls, mobile: str) -> Optional[str]:
        """
        Normalizes Indian 10-digit mobile numbers.
        Accepts: 9876543210, +919876543210, +91 98765 43210, 09876543210, 919876543210.
        Returns canonical 10-digit string starting with 6-9, or None if invalid.
        """
        if not mobile:
            return None
        cleaned = re.sub(r"[\s\-\(\)\+]", "", str(mobile).strip())
        if cleaned.startswith("91") and len(cleaned) == 12:
            cleaned = cleaned[2:]
        elif cleaned.startswith("0") and len(cleaned) == 11:
            cleaned = cleaned[1:]
        if re.match(r"^[6-9]\d{9}$", cleaned):
            return cleaned
        return None

    @classmethod
    def format_e164(cls, mobile: str) -> Optional[str]:
        """
        Formats a 10-digit Indian mobile number to E.164 standard (+91XXXXXXXXXX).
        """
        ten_digit = cls.normalize_phone(mobile)
        if ten_digit:
            return f"+91{ten_digit}"
        return None

    @classmethod
    def mask_phone(cls, phone: Optional[str]) -> str:
        """Safely masks phone number or email for logs, e.g. +91*****1234."""
        if not phone:
            return "N/A"
        clean = str(phone).strip()
        if "@" in clean:
            parts = clean.split("@", 1)
            name, domain = parts[0], parts[1] if len(parts) > 1 else ""
            masked_name = (name[0] + "***" + name[-1]) if len(name) > 2 else "***"
            return f"{masked_name}@{domain}"
        if len(clean) >= 8:
            return clean[:3] + "*****" + clean[-4:]
        return "*****"

    @classmethod
    def start_verification(cls, mobile: str) -> Tuple[bool, str]:
        """
        Requests Twilio Verify to deliver an OTP to the destination mobile number.
        Returns (success: bool, message: str).
        NEVER logs OTP values or exposes credentials.
        """
        if "@" in str(mobile):
            is_dev = os.getenv("FLASK_ENV", "production").lower() in ("development", "dev", "test", "testing")
            if is_dev:
                dev_otp = "123456"
                cls._dev_verifications[mobile] = dev_otp
                cls._last_dev_sms = {
                    "mobile": mobile,
                    "formatted_number": mobile,
                    "provider": "email_sim",
                    "dev_otp": dev_otp,
                }
                return True, "OTP sent successfully."
            if not cls.is_configured():
                return False, "SMS service is temporarily unavailable. Please try again later."
            return True, "OTP sent successfully."

        formatted_number = cls.format_e164(mobile)
        if not formatted_number:
            return False, "Enter a valid 10-digit Indian mobile number."

        cfg = cls.get_sms_config()
        provider = cfg["provider"]
        is_dev = os.getenv("FLASK_ENV", "production").lower() in ("development", "dev", "test", "testing")

        # 1. Twilio Verify Provider
        if provider in ("twilio_verify", "twilio-verify"):
            if not cls.is_configured():
                if is_dev:
                    dev_otp = "123456"
                    cls._dev_verifications[formatted_number] = dev_otp
                    cls._last_dev_sms = {
                        "mobile": mobile,
                        "formatted_number": formatted_number,
                        "provider": provider,
                        "dev_otp": dev_otp,
                    }
                    logger.info("Development mode: Twilio Verify simulation for target=%s", cls.mask_phone(formatted_number))
                    return True, "OTP sent successfully."
                logger.error("Twilio Verify requested but credentials (ACCOUNT_SID/AUTH_TOKEN/VERIFY_SERVICE_SID) are incomplete.")
                return False, "SMS service is temporarily unavailable. Please try again later."

            account_sid = cfg["twilio_account_sid"]
            auth_token = cfg["twilio_auth_token"]
            service_sid = cfg["twilio_verify_service_sid"]
            endpoint = f"https://verify.twilio.com/v2/Services/{service_sid}/Verifications"

            try:
                resp = requests.post(
                    endpoint,
                    auth=(account_sid, auth_token),
                    data={"To": formatted_number, "Channel": "sms"},
                    timeout=10,
                )
                if resp.status_code in (200, 201):
                    logger.info("Twilio Verify request accepted for target=%s", cls.mask_phone(formatted_number))
                    return True, "OTP sent successfully."
                else:
                    try:
                        err_json = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
                        twilio_code = err_json.get("code", "N/A")
                        twilio_msg = err_json.get("message", resp.text[:120])
                    except Exception:
                        twilio_code = "PARSE_ERR"
                        twilio_msg = resp.text[:120]
                    logger.error(
                        "Twilio Verify dispatch failed | provider=%s | http_status=%s | twilio_code=%s | twilio_msg=%s | target=%s",
                        provider, resp.status_code, twilio_code, twilio_msg, cls.mask_phone(formatted_number)
                    )
                    return False, "Unable to deliver verification code. Please check your mobile number and try again."
            except Exception as exc:
                logger.error(
                    "Twilio Verify network failure | provider=%s | error_type=%s | target=%s",
                    provider, type(exc).__name__, cls.mask_phone(formatted_number)
                )
                return False, "SMS gateway connectivity error. Please try again later."

        # 2. Legacy Twilio Programmable Messaging fallback
        if provider == "twilio":
            if not cls.is_configured():
                if is_dev:
                    dev_otp = "123456"
                    cls._dev_verifications[formatted_number] = dev_otp
                    return True, "OTP sent successfully."
                return False, "SMS service is temporarily unavailable. Please try again later."
            # In legacy twilio mode, generate standard 6-digit OTP
            import secrets
            otp_code = str(secrets.randbelow(900000) + 100000)
            return cls.send_otp_via_twilio(
                formatted_number, otp_code, cfg["twilio_account_sid"], cfg["twilio_auth_token"], cfg["twilio_phone_number"]
            )

        # 3. Development / Testing Mode fallback
        if is_dev:
            dev_otp = "123456"
            cls._dev_verifications[formatted_number] = dev_otp
            cls._last_dev_sms = {
                "mobile": mobile,
                "formatted_number": formatted_number,
                "provider": provider or "none",
                "dev_otp": dev_otp,
            }
            logger.info("Development mode: verification started for %s", formatted_number)
            return True, "OTP sent successfully."

        # 4. Production with no provider configured
        logger.error("Production SMS requested but SMS_PROVIDER is unconfigured.")
        return False, "SMS service is not currently configured. Please contact administrator."

    @classmethod
    def check_verification(cls, mobile: str, otp_code: str) -> Tuple[bool, str]:
        """
        Validates user-submitted OTP with Twilio Verify.
        Returns (approved: bool, message: str).
        NEVER logs OTP values or exposes credentials.
        """
        submitted_code = str(otp_code or "").strip()
        if not submitted_code:
            return False, "Please enter the verification code."

        if "@" in str(mobile):
            is_dev = os.getenv("FLASK_ENV", "production").lower() in ("development", "dev", "test", "testing")
            if is_dev:
                expected = cls._dev_verifications.get(mobile)
                if expected == submitted_code or submitted_code == "123456":
                    cls._dev_verifications.pop(mobile, None)
                    return True, "Mobile number verified successfully."
                return False, "Invalid or expired verification code. Please try again."
            return False, "Verification service is not configured for email."

        formatted_number = cls.format_e164(mobile)
        if not formatted_number:
            return False, "Enter a valid 10-digit Indian mobile number."

        cfg = cls.get_sms_config()
        provider = cfg["provider"]
        is_dev = os.getenv("FLASK_ENV", "production").lower() in ("development", "dev", "test", "testing")

        # 1. Twilio Verify Provider
        if provider in ("twilio_verify", "twilio-verify"):
            if not cls.is_configured():
                if is_dev:
                    expected = cls._dev_verifications.get(formatted_number)
                    if expected == submitted_code or submitted_code == "123456":
                        cls._dev_verifications.pop(formatted_number, None)
                        return True, "Mobile number verified successfully."
                    return False, "Invalid or expired verification code. Please try again."
                return False, "Verification service is temporarily unavailable. Please try again later."

            account_sid = cfg["twilio_account_sid"]
            auth_token = cfg["twilio_auth_token"]
            service_sid = cfg["twilio_verify_service_sid"]
            endpoint = f"https://verify.twilio.com/v2/Services/{service_sid}/VerificationCheck"

            try:
                resp = requests.post(
                    endpoint,
                    auth=(account_sid, auth_token),
                    data={"To": formatted_number, "Code": submitted_code},
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == "approved" and data.get("valid") is True:
                        logger.info("Twilio Verify check approved for target=%s", cls.mask_phone(formatted_number))
                        return True, "Mobile number verified successfully."
                    else:
                        logger.info("Twilio Verify check not approved for target=%s", cls.mask_phone(formatted_number))
                        return False, "Invalid or expired verification code. Please try again."
                else:
                    try:
                        err_json = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
                        twilio_code = err_json.get("code", "N/A")
                        twilio_msg = err_json.get("message", resp.text[:120])
                    except Exception:
                        twilio_code = "PARSE_ERR"
                        twilio_msg = resp.text[:120]
                    logger.error(
                        "Twilio VerificationCheck failed | provider=%s | http_status=%s | twilio_code=%s | twilio_msg=%s | target=%s",
                        provider, resp.status_code, twilio_code, twilio_msg, cls.mask_phone(formatted_number)
                    )
                    return False, "Invalid or expired verification code. Please try again."
            except Exception as exc:
                logger.error(
                    "Twilio VerificationCheck network failure | provider=%s | error_type=%s | target=%s",
                    provider, type(exc).__name__, cls.mask_phone(formatted_number)
                )
                return False, "Verification gateway connectivity error. Please try again later."

        # 2. Development / Testing Mode fallback
        if is_dev:
            expected = cls._dev_verifications.get(formatted_number)
            if expected == submitted_code or submitted_code == "123456":
                cls._dev_verifications.pop(formatted_number, None)
                return True, "Mobile number verified successfully."
            return False, "Invalid or expired verification code. Please try again."

        return False, "Verification service is not configured. Please contact administrator."

    @classmethod
    def send_otp_via_twilio(cls, to_mobile: str, otp_code: str, account_sid: str, auth_token: str, from_number: str) -> Tuple[bool, str]:
        """
        Legacy Programmable Messaging helper.
        """
        formatted_number = cls.format_e164(to_mobile) or to_mobile
        endpoint = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        message_body = (
            f"Your KPR Food Court verification code is: {otp_code}. "
            f"Valid for 5 minutes. Do not share this code with anyone."
        )
        try:
            resp = requests.post(
                endpoint,
                auth=(account_sid, auth_token),
                data={
                    "From": from_number,
                    "To": formatted_number,
                    "Body": message_body,
                },
                timeout=10,
            )
            if resp.status_code in (200, 201):
                return True, "OTP sent successfully via SMS."
            else:
                return False, "Failed to deliver SMS. Please verify your mobile number or try again later."
        except Exception:
            return False, "SMS gateway connectivity error. Please try again later."

    @classmethod
    def send_otp(cls, mobile: str, otp_code: str = "", purpose: str = "signup") -> Tuple[bool, str]:
        """
        Unified dispatch: routes to start_verification for Twilio Verify.
        """
        cfg = cls.get_sms_config()
        if cfg["provider"] in ("twilio_verify", "twilio-verify"):
            return cls.start_verification(mobile)

        # Legacy direct SMS delivery
        is_dev = os.getenv("FLASK_ENV", "production").lower() in ("development", "dev", "test", "testing")
        formatted_number = cls.format_e164(mobile) or mobile
        if is_dev:
            cls._dev_verifications[formatted_number] = otp_code or "123456"
            return True, "OTP sent successfully."
        if not cls.is_configured():
            return False, "SMS service is temporarily unavailable. Please try again later."
        return cls.send_otp_via_twilio(
            mobile, otp_code, cfg["twilio_account_sid"], cfg["twilio_auth_token"], cfg["twilio_phone_number"]
        )

    @classmethod
    def get_last_sms_for_testing(cls) -> Optional[Dict[str, Any]]:
        """Returns in-memory test hook data for test assertions."""
        return cls._last_dev_sms

    @classmethod
    def clear_testing_state(cls) -> None:
        """Resets the in-memory test hooks."""
        cls._last_dev_sms = None
        cls._dev_verifications.clear()
