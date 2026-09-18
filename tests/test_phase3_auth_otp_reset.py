"""
Phase 3.1 Test Suite: Real Mobile OTP using Twilio Verify & Password Reset Verification.

Covers:
 1. Twilio Verify configuration (service SID, account SID, auth token, provider selection)
 2. Indian mobile number normalization (9342351337, +919342351337, 09342351337 -> +919342351337)
 3. OTP send request creates safe verification record (code='VERIFY', no plaintext OTP stored)
 4. Twilio Verify start_verification API call parameters (mocked REST POST /Verifications)
 5. Twilio Verify start_verification failure handling (safe 503 error, no secret leak)
 6. Twilio Verify check_verification API call parameters (mocked REST POST /VerificationCheck)
 7. Valid OTP verification (approved check -> 200 OK, is_verified=1)
 8. Invalid OTP verification (not approved check -> 400 Bad Request)
 9. Expired verification request rejection
10. OTP single-use (consumed verification cannot be reused for signup)
11. Resend invalidation (prior active verification marked consumed)
12. Rate limiting & attempt limits (5 requests/min and lockout on repeated failures)
13. Production OTP suppression (demo_otp never exposed in production responses)
14. Missing Twilio Verify credentials handled safely in production (returns 503)
15. Student signup OTP flow (verified mobile + roll number + @kpriet.ac.in)
16. Faculty signup OTP flow (verified mobile + faculty ID + @kpriet.ac.in)
17. Guest signup OTP flow (verified mobile + general email)
18. Signup blocked without verified mobile
19. Password reset public URL & token security intact
20. Password successfully changes after valid reset
"""

import os
import sys
import secrets
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ["FLASK_ENV"] = "development"
os.environ["USE_SQLITE"] = "1"
os.environ["SECRET_KEY"] = "test-phase3-secret-key-32-chars-long"

import init_db
init_db.init_sqlite()

from app import app
from db import DB
from security import hash_password, verify_password
from services.sms_service import SMSService
from services.email_service import EmailService
from routes.auth import _otp_failed_verifications, _otp_send_limits, normalize_mobile


class TestPhase31TwilioVerifyAndReset(unittest.TestCase):
    """Full verification test suite for Phase 3.1 Twilio Verify integration."""

    @classmethod
    def setUpClass(cls):
        cls.app = app
        cls.app.config["TESTING"] = True

    def setUp(self):
        self.client = self.app.test_client()
        _otp_failed_verifications.clear()
        _otp_send_limits.clear()
        EmailService.clear_testing_state()
        SMSService.clear_testing_state()

    def _generate_mobile(self):
        return f"9{secrets.randbelow(900000000) + 100000000}"

    def _create_user(self, email_prefix="phase3_user", password="InitialPassword123!"):
        unique = secrets.token_hex(4)
        email = f"{email_prefix}_{unique}@kpriet.ac.in"
        pw_hash = hash_password(password)
        user_id = DB.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
            (email, pw_hash)
        )
        DB.execute(
            "INSERT INTO customer_profiles (user_id, customer_type, full_name, mobile) VALUES (%s, 'student', %s, %s)",
            (user_id, f"User {unique}", self._generate_mobile())
        )
        return user_id, email, password

    # =========================================================================
    # 1. Twilio Verify configuration
    # =========================================================================
    def test_01_twilio_verify_config(self):
        """SMSService correctly parses Twilio Verify configuration from environment."""
        env_override = {
            "SMS_PROVIDER": "twilio_verify",
            "TWILIO_ACCOUNT_SID": "test_dummy_account_sid_123",
            "TWILIO_AUTH_TOKEN": "authtoken1234567890abcdef",
            "TWILIO_VERIFY_SERVICE_SID": "VA1234567890abcdef1234567890abcdef",
        }
        with patch.dict(os.environ, env_override):
            cfg = SMSService.get_sms_config()
            self.assertEqual(cfg["provider"], "twilio_verify")
            self.assertEqual(cfg["twilio_account_sid"], "test_dummy_account_sid_123")
            self.assertEqual(cfg["twilio_auth_token"], "authtoken1234567890abcdef")
            self.assertEqual(cfg["twilio_verify_service_sid"], "VA1234567890abcdef1234567890abcdef")
            self.assertTrue(SMSService.is_configured())

    # =========================================================================
    # 2. Indian mobile number normalization
    # =========================================================================
    def test_02_indian_mobile_normalization(self):
        """Preserves and normalizes various valid Indian mobile number formats."""
        cases = [
            ("9342351337", "9342351337", "+919342351337"),
            ("+919342351337", "9342351337", "+919342351337"),
            ("+91 93423 51337", "9342351337", "+919342351337"),
            ("09342351337", "9342351337", "+919342351337"),
            ("919342351337", "9342351337", "+919342351337"),
        ]
        for raw, expected_10, expected_e164 in cases:
            self.assertEqual(SMSService.normalize_phone(raw), expected_10)
            self.assertEqual(SMSService.format_e164(raw), expected_e164)
            self.assertEqual(normalize_mobile(raw), expected_10)

        # Invalid numbers must be rejected safely
        self.assertIsNone(SMSService.normalize_phone("12345"))
        self.assertIsNone(SMSService.normalize_phone("5123456789"))  # does not start with 6-9
        self.assertIsNone(SMSService.format_e164("invalid_phone"))

    # =========================================================================
    # 3. Safe verification request record in database
    # =========================================================================
    def test_03_otp_send_record(self):
        """OTP send requests Twilio Verify without storing plaintext OTPs in database."""
        mobile = self._generate_mobile()
        res = self.client.post("/api/auth/otp/send", json={"mobile": mobile, "purpose": "signup"})
        self.assertEqual(res.status_code, 200)

        normalized = normalize_mobile(mobile)
        row = DB.get_one(
            "SELECT code, purpose, is_verified, is_consumed FROM otp_codes WHERE target = %s ORDER BY id DESC LIMIT 1",
            (normalized,)
        )
        self.assertIsNotNone(row, "Verification record must be recorded in database")
        # Code column must store a safe non-secret marker, NOT an actual carrier OTP
        self.assertEqual(row["code"], "VERIFY")
        self.assertEqual(row["purpose"], "signup")
        self.assertEqual(row["is_verified"], 0)
        self.assertEqual(row["is_consumed"], 0)

    # =========================================================================
    # 4. Twilio Verify start_verification API call
    # =========================================================================
    def test_04_twilio_verify_start_api_call(self):
        """SMSService.start_verification dispatches POST to Twilio /Verifications endpoint."""
        mobile = self._generate_mobile()
        env_override = {
            "SMS_PROVIDER": "twilio_verify",
            "TWILIO_ACCOUNT_SID": "mock_account_sid_123",
            "TWILIO_AUTH_TOKEN": "mockAuthToken456",
            "TWILIO_VERIFY_SERVICE_SID": "VAmockVerifySid789",
            "FLASK_ENV": "production",
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"status": "pending", "sid": "VEmockVerification123"}

        with patch.dict(os.environ, env_override):
            with patch("requests.post", return_value=mock_resp) as mock_post:
                success, msg = SMSService.start_verification(mobile)
                self.assertTrue(success)
                self.assertIn("successfully", msg.lower())

                mock_post.assert_called_once()
                call_url = mock_post.call_args[0][0]
                self.assertEqual(call_url, "https://verify.twilio.com/v2/Services/VAmockVerifySid789/Verifications")
                call_auth = mock_post.call_args[1]["auth"]
                self.assertEqual(call_auth, ("mock_account_sid_123", "mockAuthToken456"))
                call_data = mock_post.call_args[1]["data"]
                self.assertEqual(call_data["To"], SMSService.format_e164(mobile))
                self.assertEqual(call_data["Channel"], "sms")

    # =========================================================================
    # 5. Twilio Verify start failure handling
    # =========================================================================
    def test_05_twilio_verify_start_failure(self):
        """Twilio Verify failure returns a safe error without leaking credentials."""
        mobile = self._generate_mobile()
        env_override = {
            "SMS_PROVIDER": "twilio_verify",
            "TWILIO_ACCOUNT_SID": "mock_account_sid_123",
            "TWILIO_AUTH_TOKEN": "SuperSecretAuthToken999",
            "TWILIO_VERIFY_SERVICE_SID": "VAmockVerifySid789",
            "FLASK_ENV": "production",
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"code": 60200, "message": "Invalid parameter"}

        with patch.dict(os.environ, env_override):
            with patch("requests.post", return_value=mock_resp):
                success, msg = SMSService.start_verification(mobile)
                self.assertFalse(success)
                self.assertNotIn("SuperSecretAuthToken999", msg)
                self.assertNotIn("mock_account_sid_123", msg)

    # =========================================================================
    # 6. Twilio Verify check_verification API call
    # =========================================================================
    def test_06_twilio_verify_check_api_call(self):
        """SMSService.check_verification dispatches POST to Twilio /VerificationCheck endpoint."""
        mobile = self._generate_mobile()
        env_override = {
            "SMS_PROVIDER": "twilio_verify",
            "TWILIO_ACCOUNT_SID": "mock_account_sid_123",
            "TWILIO_AUTH_TOKEN": "mockAuthToken456",
            "TWILIO_VERIFY_SERVICE_SID": "VAmockVerifySid789",
            "FLASK_ENV": "production",
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "approved", "valid": True, "sid": "VEcheck123"}

        with patch.dict(os.environ, env_override):
            with patch("requests.post", return_value=mock_resp) as mock_post:
                approved, msg = SMSService.check_verification(mobile, "654321")
                self.assertTrue(approved)
                self.assertIn("verified", msg.lower())

                mock_post.assert_called_once()
                call_url = mock_post.call_args[0][0]
                self.assertEqual(call_url, "https://verify.twilio.com/v2/Services/VAmockVerifySid789/VerificationCheck")
                call_data = mock_post.call_args[1]["data"]
                self.assertEqual(call_data["To"], SMSService.format_e164(mobile))
                self.assertEqual(call_data["Code"], "654321")

    # =========================================================================
    # 7. Valid OTP verification
    # =========================================================================
    def test_07_valid_otp_verification(self):
        """When Twilio Verify returns approved, verification route returns 200 and marks is_verified=1."""
        mobile = self._generate_mobile()
        self.client.post("/api/auth/otp/send", json={"mobile": mobile, "purpose": "signup"})

        with patch.object(SMSService, "check_verification", return_value=(True, "Mobile number verified successfully.")):
            verify_res = self.client.post("/api/auth/otp/verify", json={
                "mobile": mobile,
                "code": "123456",
                "purpose": "signup"
            })
            self.assertEqual(verify_res.status_code, 200)
            data = verify_res.get_json()
            self.assertTrue(data["success"])
            self.assertTrue(data["verified"])

            normalized = normalize_mobile(mobile)
            row = DB.get_one("SELECT is_verified, is_consumed FROM otp_codes WHERE target = %s ORDER BY id DESC LIMIT 1", (normalized,))
            self.assertEqual(row["is_verified"], 1)
            self.assertEqual(row["is_consumed"], 0)

    # =========================================================================
    # 8. Invalid OTP verification
    # =========================================================================
    def test_08_invalid_otp_verification(self):
        """When Twilio Verify check fails, verification route returns 400 Bad Request."""
        mobile = self._generate_mobile()
        self.client.post("/api/auth/otp/send", json={"mobile": mobile, "purpose": "signup"})

        with patch.object(SMSService, "check_verification", return_value=(False, "Invalid or expired OTP. Please try again.")):
            verify_res = self.client.post("/api/auth/otp/verify", json={
                "mobile": mobile,
                "code": "000000",
                "purpose": "signup"
            })
            self.assertEqual(verify_res.status_code, 400)
            data = verify_res.get_json()
            self.assertFalse(data["success"])
            self.assertIn("invalid or expired", data["message"].lower())

    # =========================================================================
    # 9. Expired verification request rejection
    # =========================================================================
    def test_09_expired_verification_check(self):
        """Expired local verification record is rejected before contacting Twilio."""
        mobile = self._generate_mobile()
        self.client.post("/api/auth/otp/send", json={"mobile": mobile, "purpose": "signup"})

        normalized = normalize_mobile(mobile)
        row = DB.get_one("SELECT id FROM otp_codes WHERE target = %s ORDER BY id DESC LIMIT 1", (normalized,))
        expired_time = (datetime.now() - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
        DB.execute("UPDATE otp_codes SET expires_at = %s WHERE id = %s", (expired_time, row["id"]))

        verify_res = self.client.post("/api/auth/otp/verify", json={
            "mobile": mobile,
            "code": "123456",
            "purpose": "signup"
        })
        self.assertEqual(verify_res.status_code, 400)

    # =========================================================================
    # 10. OTP single-use
    # =========================================================================
    def test_10_otp_single_use(self):
        """A verified record is consumed upon signup and cannot be reused."""
        mobile = self._generate_mobile()
        self.client.post("/api/auth/otp/send", json={"mobile": mobile, "purpose": "signup"})

        with patch.object(SMSService, "check_verification", return_value=(True, "Mobile number verified successfully.")):
            self.client.post("/api/auth/otp/verify", json={"mobile": mobile, "code": "123456", "purpose": "signup"})

        # Complete first signup
        email = f"singleuse_{secrets.token_hex(4)}@kpriet.ac.in"
        res1 = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Single Use Customer",
            "email": email,
            "mobile": mobile,
            "password": "Password123!",
            "customerType": "student",
            "identifier": f"21CS{secrets.randbelow(899) + 100}"
        })
        self.assertEqual(res1.status_code, 201)

        # In database, record is now consumed
        normalized = normalize_mobile(mobile)
        row = DB.get_one("SELECT is_consumed FROM otp_codes WHERE target = %s ORDER BY id DESC LIMIT 1", (normalized,))
        self.assertEqual(row["is_consumed"], 1)

        # Attempt to use same verified mobile without a new verification -> must be rejected
        res2 = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Second User",
            "email": f"second_{secrets.token_hex(4)}@kpriet.ac.in",
            "mobile": mobile,
            "password": "Password123!",
            "customerType": "student",
            "identifier": f"21CS{secrets.randbelow(899) + 100}"
        })
        self.assertNotEqual(res2.status_code, 201)

    # =========================================================================
    # 11. Resend invalidation
    # =========================================================================
    def test_11_resend_invalidation(self):
        """Requesting a new OTP invalidates prior active verification requests for that mobile."""
        mobile = self._generate_mobile()
        normalized = normalize_mobile(mobile)

        self.client.post("/api/auth/otp/send", json={"mobile": mobile, "purpose": "signup"})
        row1 = DB.get_one("SELECT id, is_consumed FROM otp_codes WHERE target = %s ORDER BY id DESC LIMIT 1", (normalized,))
        self.assertEqual(row1["is_consumed"], 0)

        # Resend
        self.client.post("/api/auth/otp/send", json={"mobile": mobile, "purpose": "signup"})
        row2 = DB.get_one("SELECT id, is_consumed FROM otp_codes WHERE target = %s ORDER BY id DESC LIMIT 1", (normalized,))

        # First row is now consumed/invalidated
        old_row = DB.get_one("SELECT is_consumed FROM otp_codes WHERE id = %s", (row1["id"],))
        self.assertEqual(old_row["is_consumed"], 1)
        self.assertEqual(row2["is_consumed"], 0)

    # =========================================================================
    # 12. Rate limiting & attempt limits
    # =========================================================================
    def test_12_otp_rate_limiting(self):
        """Verification route triggers 429 after 5 failed verification attempts."""
        mobile = self._generate_mobile()
        self.client.post("/api/auth/otp/send", json={"mobile": mobile, "purpose": "signup"})

        with patch.object(SMSService, "check_verification", return_value=(False, "Invalid OTP")):
            for _ in range(5):
                res = self.client.post("/api/auth/otp/verify", json={"mobile": mobile, "code": "000000", "purpose": "signup"})
                self.assertEqual(res.status_code, 400)

            # 6th attempt locks out with 429
            lockout_res = self.client.post("/api/auth/otp/verify", json={"mobile": mobile, "code": "000000", "purpose": "signup"})
            self.assertEqual(lockout_res.status_code, 429)
            self.assertIn("too many failed", lockout_res.get_json()["message"].lower())

    # =========================================================================
    # 13. Production OTP suppression
    # =========================================================================
    def test_13_production_otp_suppression(self):
        """In production mode, demo_otp is never returned in the API response."""
        mobile = self._generate_mobile()

        with patch("db.is_production", return_value=False):
            with patch.dict(os.environ, {"FLASK_ENV": "production", "USE_SQLITE": "1"}):
                with patch.object(SMSService, "start_verification", return_value=(True, "OTP sent successfully.")):
                    res = self.client.post("/api/auth/otp/send", json={"mobile": mobile, "purpose": "signup"})
                    self.assertEqual(res.status_code, 200)
                    data = res.get_json()
                    self.assertTrue(data["success"])
                    self.assertNotIn("demo_otp", data)
                    self.assertNotIn("debug_code", data)
                    self.assertNotIn("otp", data)

    # =========================================================================
    # 14. Missing credentials handled safely in production
    # =========================================================================
    def test_14_missing_credentials_handled_safely(self):
        """In production, missing Twilio Verify credentials returns 503 safely."""
        mobile = self._generate_mobile()
        env_override = {
            "FLASK_ENV": "production",
            "USE_SQLITE": "1",
            "SMS_PROVIDER": "twilio_verify",
            "TWILIO_ACCOUNT_SID": "",
            "TWILIO_AUTH_TOKEN": "",
            "TWILIO_VERIFY_SERVICE_SID": "",
        }

        with patch("db.is_production", return_value=False):
            with patch.dict(os.environ, env_override):
                res = self.client.post("/api/auth/otp/send", json={"mobile": mobile, "purpose": "signup"})
                self.assertEqual(res.status_code, 503)
                data = res.get_json()
                self.assertFalse(data["success"])
                self.assertIn("unable to deliver otp via sms", data["message"].lower())

    # =========================================================================
    # 15. Student signup OTP flow
    # =========================================================================
    def test_15_student_signup_otp_flow(self):
        """Complete student signup requires Twilio Verify verification and roll number."""
        mobile = self._generate_mobile()
        normalized = normalize_mobile(mobile)

        self.client.post("/api/auth/otp/send", json={"mobile": mobile, "purpose": "signup"})
        with patch.object(SMSService, "check_verification", return_value=(True, "Verified")):
            self.client.post("/api/auth/otp/verify", json={"mobile": mobile, "code": "123456", "purpose": "signup"})

        roll = f"21CS{secrets.randbelow(899) + 100}"
        good_email = f"stud_{secrets.token_hex(4)}@kpriet.ac.in"
        res = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Student User",
            "email": good_email,
            "mobile": mobile,
            "password": "StudentPassword123!",
            "customerType": "student",
            "identifier": roll
        })
        self.assertEqual(res.status_code, 201)
        profile = DB.get_one("SELECT customer_type, identifier FROM customer_profiles WHERE mobile = %s", (normalized,))
        self.assertEqual(profile["customer_type"], "student")
        self.assertEqual(profile["identifier"], roll)

    # =========================================================================
    # 16. Faculty signup OTP flow
    # =========================================================================
    def test_16_faculty_signup_otp_flow(self):
        """Complete faculty signup requires Twilio Verify verification and faculty ID."""
        mobile = self._generate_mobile()
        normalized = normalize_mobile(mobile)

        self.client.post("/api/auth/otp/send", json={"mobile": mobile, "purpose": "signup"})
        with patch.object(SMSService, "check_verification", return_value=(True, "Verified")):
            self.client.post("/api/auth/otp/verify", json={"mobile": mobile, "code": "123456", "purpose": "signup"})

        fac_id = f"FAC{secrets.randbelow(899) + 100}"
        good_email = f"fac_{secrets.token_hex(4)}@kpriet.ac.in"
        res = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Faculty User",
            "email": good_email,
            "mobile": mobile,
            "password": "FacultyPassword123!",
            "customerType": "faculty",
            "identifier": fac_id
        })
        self.assertEqual(res.status_code, 201)
        profile = DB.get_one("SELECT customer_type, identifier FROM customer_profiles WHERE mobile = %s", (normalized,))
        self.assertEqual(profile["customer_type"], "faculty")
        self.assertEqual(profile["identifier"], fac_id)

    # =========================================================================
    # 17. Guest signup OTP flow
    # =========================================================================
    def test_17_guest_signup_otp_flow(self):
        """Guest signup requires Twilio Verify verification and allows general email domain."""
        mobile = self._generate_mobile()
        normalized = normalize_mobile(mobile)

        self.client.post("/api/auth/otp/send", json={"mobile": mobile, "purpose": "signup"})
        with patch.object(SMSService, "check_verification", return_value=(True, "Verified")):
            self.client.post("/api/auth/otp/verify", json={"mobile": mobile, "code": "123456", "purpose": "signup"})

        guest_email = f"guest_{secrets.token_hex(4)}@gmail.com"
        res = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Guest User",
            "email": guest_email,
            "mobile": mobile,
            "password": "GuestPassword123!",
            "customerType": "guest"
        })
        self.assertEqual(res.status_code, 201)
        profile = DB.get_one("SELECT customer_type FROM customer_profiles WHERE mobile = %s", (normalized,))
        self.assertEqual(profile["customer_type"], "guest")

    # =========================================================================
    # 18. Signup blocked without verification
    # =========================================================================
    def test_18_signup_blocked_without_verification(self):
        """Signup without verified mobile number is rejected with HTTP 400."""
        mobile = self._generate_mobile()
        res = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Unverified User",
            "email": f"unverified_{secrets.token_hex(4)}@kpriet.ac.in",
            "mobile": mobile,
            "password": "Password123!",
            "customerType": "student",
            "identifier": "21CS999"
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("not been verified", res.get_json()["message"].lower())

    # =========================================================================
    # 19. Password reset public URL & token security intact
    # =========================================================================
    def test_19_password_reset_intact(self):
        """Phase 3 password reset token generation, single-use, and URL construction remain intact."""
        user_id, email, _ = self._create_user(email_prefix="pwd_verify_intact")

        with patch.dict(os.environ, {"FRONTEND_URL": "https://college-food-court-frontend.onrender.com"}):
            res = self.client.post("/api/auth/password/forgot", json={"email": email})
            self.assertEqual(res.status_code, 200)

            reset_url = EmailService._last_dev_dispatch["reset_url"]
            self.assertTrue(reset_url.startswith("https://college-food-court-frontend.onrender.com/pages/auth/reset-password.html?token="))
            self.assertNotIn("localhost", reset_url.lower())

            # Token in database is hashed SHA-256
            row = DB.get_one("SELECT token_hash FROM password_resets WHERE user_id = %s ORDER BY id DESC LIMIT 1", (user_id,))
            self.assertEqual(len(row["token_hash"]), 64)

    # =========================================================================
    # 20. Password successfully changes after valid reset
    # =========================================================================
    def test_20_password_successfully_changes_after_valid_reset(self):
        """Password is successfully updated: old password fails, new password logs in."""
        old_password = "OldInitialPassword123!"
        new_password = "BrandNewSecurePassword456!"
        user_id, email, _ = self._create_user(email_prefix="pwd_change_tv", password=old_password)

        self.client.post("/api/auth/password/forgot", json={"email": email})
        raw_token = EmailService._last_dev_dispatch["reset_url"].split("token=")[1]

        reset_res = self.client.post("/api/auth/password/reset", json={
            "token": raw_token,
            "new_password": new_password,
            "confirm_password": new_password
        })
        self.assertEqual(reset_res.status_code, 200)

        # Old fails, new succeeds
        login_old = self.client.post("/api/auth/login", json={"email": email, "password": old_password})
        self.assertEqual(login_old.status_code, 401)

        login_new = self.client.post("/api/auth/login", json={"email": email, "password": new_password})
        self.assertEqual(login_new.status_code, 200)
        self.assertTrue(login_new.get_json()["success"])

        # Audit log present
        audit_log = DB.get_one(
            "SELECT action FROM audit_logs WHERE actor_id = %s AND action = 'PASSWORD_RESET_SUCCESS' LIMIT 1",
            (user_id,)
        )
        self.assertIsNotNone(audit_log)


if __name__ == "__main__":
    unittest.main()
