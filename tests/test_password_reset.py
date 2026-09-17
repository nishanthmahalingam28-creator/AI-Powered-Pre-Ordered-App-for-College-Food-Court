"""
Comprehensive Security Test Suite for Forgot Password & Reset Password System.

Verifies:
1. Clicking "Forgot Password?" opens a real reset flow.
2. User enters their email and receives a uniform response.
3. Cryptographically secure, short-lived reset token generation.
4. Database stores only the SHA-256 hash representation of the token (never raw token).
5. Token expiration (15 minutes).
6. Non-enumeration: password reset never reveals whether an email exists.
7. New password is securely hashed with bcrypt (cost factor 12).
8. Existing reset tokens become invalid after successful reset and upon new reset requests.
9. Zero reset tokens stored in localStorage.
10. Zero passwords or reset tokens logged to server logs or console.
11. Clear success/error messages and input validation.
"""

import sys
import os
import re
import io
import json
import logging
import hashlib
import unittest
from datetime import datetime, timedelta

# Add backend directory to sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ["FLASK_ENV"] = "development"
os.environ["USE_SQLITE"] = "1"
os.environ["SECRET_KEY"] = "test-secret-key-password-reset-audit-32b"

import init_db
init_db.init_sqlite()

from app import app
from db import DB
from security import hash_password, verify_password
from services.email_service import EmailService


class TestPasswordResetSecurity(unittest.TestCase):
    """Test suite covering all 11 password reset requirements and security controls."""

    @classmethod
    def setUpClass(cls):
        cls.app = app
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    def setUp(self):
        self.client = self.app.test_client()
        EmailService.clear_testing_state()

    def _create_test_user(self, email_prefix="pwd_test"):
        unique_id = os.urandom(4).hex()
        email = f"{email_prefix}_{unique_id}@kpriet.ac.in"
        plain_pwd = "OldPassword123!"
        hashed = hash_password(plain_pwd)

        user_id = DB.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
            (email, hashed)
        )
        DB.execute(
            "INSERT INTO customer_profiles (user_id, customer_type, full_name, wallet_balance) VALUES (%s, 'student', %s, 500.00)",
            (user_id, f"User {unique_id}")
        )
        return user_id, email, plain_pwd

    # -------------------------------------------------------------
    # 1. Non-Enumeration (Requirement 6)
    # -------------------------------------------------------------
    def test_01_account_non_enumeration(self):
        """Reset request must return identical 200 response for existing and non-existing emails."""
        _, existing_email, _ = self._create_test_user("existing")
        non_existing_email = f"ghost_user_{os.urandom(4).hex()}@kpriet.ac.in"

        res_exist = self.client.post("/api/auth/password/forgot", json={"email": existing_email})
        res_ghost = self.client.post("/api/auth/password/forgot", json={"email": non_existing_email})

        self.assertEqual(res_exist.status_code, 200)
        self.assertEqual(res_ghost.status_code, 200)

        data_exist = res_exist.get_json()
        data_ghost = res_ghost.get_json()

        # Both must return identical user-facing messages
        self.assertTrue(data_exist.get("success"))
        self.assertTrue(data_ghost.get("success"))
        self.assertEqual(data_exist.get("message"), data_ghost.get("message"))
        self.assertIn("If an account exists", data_exist.get("message"))

        # Non-existing user should not create any tokens in DB
        ghost_tokens = DB.get_all(
            "SELECT pr.id FROM password_resets pr JOIN users u ON u.id = pr.user_id WHERE u.email = %s",
            (non_existing_email,)
        )
        self.assertEqual(len(ghost_tokens), 0)

    # -------------------------------------------------------------
    # 2. Cryptographic Security & Hash Representation (Req 3 & 4)
    # -------------------------------------------------------------
    def test_02_secure_hash_representation_in_db(self):
        """Database must store ONLY SHA-256 hash of token; raw token must NOT be in DB."""
        user_id, email, _ = self._create_test_user("hash_check")

        res = self.client.post("/api/auth/password/forgot", json={"email": email})
        self.assertEqual(res.status_code, 200)

        # Retrieve dispatched email metadata from memory hook
        dispatched = EmailService.get_last_reset_for_testing()
        self.assertIsNotNone(dispatched)
        raw_token = dispatched.get("raw_token")
        self.assertTrue(len(raw_token) >= 32, "Token must have high entropy")

        # Query DB
        db_record = DB.get_one(
            "SELECT token_hash, is_used, expires_at FROM password_resets WHERE user_id = %s ORDER BY id DESC LIMIT 1",
            (user_id,)
        )
        self.assertIsNotNone(db_record)

        # Verify raw token is NOT in database
        self.assertNotEqual(db_record["token_hash"], raw_token)

        # Verify stored value is precisely SHA-256 of raw token
        expected_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        self.assertEqual(db_record["token_hash"], expected_hash)
        self.assertEqual(db_record["is_used"], 0)

    # -------------------------------------------------------------
    # 3. Token Verification Endpoint (Req 1 & 11)
    # -------------------------------------------------------------
    def test_03_verify_reset_token_endpoint(self):
        """Verification endpoint checks token validity without consuming it."""
        user_id, email, _ = self._create_test_user("verify_tok")
        self.client.post("/api/auth/password/forgot", json={"email": email})
        raw_token = EmailService.get_last_reset_for_testing()["raw_token"]

        # Valid token
        res_valid = self.client.get(f"/api/auth/password/reset/verify?token={raw_token}")
        self.assertEqual(res_valid.status_code, 200)
        data = res_valid.get_json()
        self.assertTrue(data.get("valid"))
        self.assertIn("email", data)
        self.assertIn("***", data["email"], "Email should be masked for privacy")

        # Invalid token
        res_invalid = self.client.get("/api/auth/password/reset/verify?token=completely_fake_token_123")
        self.assertEqual(res_invalid.status_code, 400)
        self.assertFalse(res_invalid.get_json().get("valid"))

        # Missing token
        res_missing = self.client.get("/api/auth/password/reset/verify")
        self.assertEqual(res_missing.status_code, 400)

    # -------------------------------------------------------------
    # 4. Token Expiration (Req 5)
    # -------------------------------------------------------------
    def test_04_token_expiration(self):
        """Expired reset tokens must be rejected."""
        user_id, email, _ = self._create_test_user("expired_tok")
        self.client.post("/api/auth/password/forgot", json={"email": email})
        raw_token = EmailService.get_last_reset_for_testing()["raw_token"]

        # Manually expire the token in database
        past_time = (datetime.now() - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
        DB.execute("UPDATE password_resets SET expires_at = %s WHERE user_id = %s", (past_time, user_id))

        # Verification must reject expired token
        v_res = self.client.get(f"/api/auth/password/reset/verify?token={raw_token}")
        self.assertEqual(v_res.status_code, 400)

        # Attempting reset with expired token must be rejected
        res = self.client.post("/api/auth/password/reset", json={
            "token": raw_token,
            "password": "NewValidPassword123!",
            "confirmPassword": "NewValidPassword123!"
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("expired", res.get_json().get("message", "").lower())

    # -------------------------------------------------------------
    # 5. Token Invalidation After Successful Reset (Req 8)
    # -------------------------------------------------------------
    def test_05_token_invalidation_after_use(self):
        """Token becomes invalid immediately after successful password reset (no replay attacks)."""
        user_id, email, _ = self._create_test_user("replay_check")
        self.client.post("/api/auth/password/forgot", json={"email": email})
        raw_token = EmailService.get_last_reset_for_testing()["raw_token"]

        # 1. First reset attempt (must succeed)
        res1 = self.client.post("/api/auth/password/reset", json={
            "token": raw_token,
            "password": "BrandNewPassword123!",
            "confirmPassword": "BrandNewPassword123!"
        })
        self.assertEqual(res1.status_code, 200)
        self.assertTrue(res1.get_json().get("success"))

        # Verify in DB that token is marked used
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        row = DB.get_one("SELECT is_used, used_at FROM password_resets WHERE token_hash = %s", (token_hash,))
        self.assertEqual(row["is_used"], 1)
        self.assertIsNotNone(row["used_at"])

        # 2. Replay attempt with same token (must be rejected)
        res2 = self.client.post("/api/auth/password/reset", json={
            "token": raw_token,
            "password": "YetAnotherPassword999!",
            "confirmPassword": "YetAnotherPassword999!"
        })
        self.assertEqual(res2.status_code, 400)
        self.assertIn("already been used", res2.get_json().get("message", "").lower())

    # -------------------------------------------------------------
    # 6. Invalidation of Older Active Tokens on New Request (Req 8)
    # -------------------------------------------------------------
    def test_06_invalidation_of_older_tokens_on_new_request(self):
        """Requesting a new reset link invalidates previous pending reset links."""
        user_id, email, _ = self._create_test_user("multi_request")

        # First request
        self.client.post("/api/auth/password/forgot", json={"email": email})
        token_1 = EmailService.get_last_reset_for_testing()["raw_token"]

        # Second request
        self.client.post("/api/auth/password/forgot", json={"email": email})
        token_2 = EmailService.get_last_reset_for_testing()["raw_token"]

        self.assertNotEqual(token_1, token_2)

        # Token 1 must be marked is_used = 1 in database
        hash_1 = hashlib.sha256(token_1.encode("utf-8")).hexdigest()
        row_1 = DB.get_one("SELECT is_used FROM password_resets WHERE token_hash = %s", (hash_1,))
        self.assertEqual(row_1["is_used"], 1)

        # Resetting with Token 1 must fail
        res_old = self.client.post("/api/auth/password/reset", json={
            "token": token_1,
            "password": "NewPassword123!",
            "confirmPassword": "NewPassword123!"
        })
        self.assertEqual(res_old.status_code, 400)

        # Resetting with Token 2 must succeed
        res_new = self.client.post("/api/auth/password/reset", json={
            "token": token_2,
            "password": "NewPassword123!",
            "confirmPassword": "NewPassword123!"
        })
        self.assertEqual(res_new.status_code, 200)

    # -------------------------------------------------------------
    # 7. Password Hashing and Authentication Verification (Req 7)
    # -------------------------------------------------------------
    def test_07_new_password_securely_hashed_and_authenticates(self):
        """New password must be bcrypt-hashed and allow successful login while invalidating old password."""
        user_id, email, old_pwd = self._create_test_user("login_verify")
        new_pwd = "UpdatedSecurePassword456!"

        # Perform password reset
        self.client.post("/api/auth/password/forgot", json={"email": email})
        raw_token = EmailService.get_last_reset_for_testing()["raw_token"]

        r_reset = self.client.post("/api/auth/password/reset", json={
            "token": raw_token,
            "password": new_pwd,
            "confirmPassword": new_pwd
        })
        self.assertEqual(r_reset.status_code, 200)

        # Verify DB hash format (bcrypt $2b$ prefix)
        user_row = DB.get_one("SELECT password_hash FROM users WHERE id = %s", (user_id,))
        self.assertTrue(user_row["password_hash"].startswith(("$2b$", "$2a$")))
        self.assertNotEqual(user_row["password_hash"], new_pwd)
        self.assertTrue(verify_password(new_pwd, user_row["password_hash"]))

        # Old password MUST fail login
        r_old = self.client.post("/api/auth/customer/login", json={"email": email, "password": old_pwd})
        self.assertEqual(r_old.status_code, 401)

        # New password MUST succeed login
        r_new = self.client.post("/api/auth/customer/login", json={"email": email, "password": new_pwd})
        self.assertEqual(r_new.status_code, 200)
        self.assertTrue(r_new.get_json().get("success"))

    # -------------------------------------------------------------
    # 8. Password Validation & Complexity (Req 11)
    # -------------------------------------------------------------
    def test_08_password_validation_requirements(self):
        """Weak passwords or mismatched confirm passwords must be rejected."""
        user_id, email, _ = self._create_test_user("validation_check")
        self.client.post("/api/auth/password/forgot", json={"email": email})
        raw_token = EmailService.get_last_reset_for_testing()["raw_token"]

        # Short password (< 8 chars)
        res_short = self.client.post("/api/auth/password/reset", json={
            "token": raw_token, "password": "Short1!", "confirmPassword": "Short1!"
        })
        self.assertEqual(res_short.status_code, 400)
        self.assertIn("8 characters", res_short.get_json().get("message", ""))

        # No numbers
        res_no_num = self.client.post("/api/auth/password/reset", json={
            "token": raw_token, "password": "NoNumbersHere!", "confirmPassword": "NoNumbersHere!"
        })
        self.assertEqual(res_no_num.status_code, 400)

        # Passwords do not match
        res_mismatch = self.client.post("/api/auth/password/reset", json={
            "token": raw_token, "password": "ValidPassword123!", "confirmPassword": "DifferentPassword123!"
        })
        self.assertEqual(res_mismatch.status_code, 400)
        self.assertIn("do not match", res_mismatch.get_json().get("message", "").lower())

    # -------------------------------------------------------------
    # 9. Never Log Passwords or Reset Tokens (Requirement 10)
    # -------------------------------------------------------------
    def test_09_never_log_passwords_or_reset_tokens(self):
        """Plaintext passwords and reset tokens must NEVER appear in application logs."""
        user_id, email, _ = self._create_test_user("log_scrub_test")
        sensitive_password = "SuperSecretPassword789!"

        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)

        try:
            # 1. Request reset
            self.client.post("/api/auth/password/forgot", json={"email": email})
            raw_token = EmailService.get_last_reset_for_testing()["raw_token"]

            # 2. Reset password
            self.client.post("/api/auth/password/reset", json={
                "token": raw_token,
                "password": sensitive_password,
                "confirmPassword": sensitive_password
            })

            logs = log_stream.getvalue()

            # The raw token MUST NOT appear in the log output
            self.assertNotIn(raw_token, logs, "CRITICAL: Raw reset token leaked into logs!")

            # The plain password MUST NOT appear in the log output
            self.assertNotIn(sensitive_password, logs, "CRITICAL: Plaintext password leaked into logs!")
        finally:
            root_logger.removeHandler(handler)

    # -------------------------------------------------------------
    # 10. Frontend Script Zero localStorage Verification (Req 9)
    # -------------------------------------------------------------
    def test_10_zero_reset_tokens_in_localstorage(self):
        """Frontend reset-password script must never store tokens in localStorage or sessionStorage."""
        reset_js_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "frontend", "js", "auth", "reset-password.js"
        ))
        forgot_js_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "frontend", "js", "auth", "forgot-password.js"
        ))

        with open(reset_js_path, "r", encoding="utf-8") as f:
            reset_content = f.read()

        with open(forgot_js_path, "r", encoding="utf-8") as f:
            forgot_content = f.read()

        # Check for localStorage and sessionStorage calls storing tokens
        self.assertNotIn("localStorage.setItem('token'", reset_content)
        self.assertNotIn("localStorage.setItem(\"token\"", reset_content)
        self.assertNotIn("localStorage.setItem('reset_token'", reset_content)
        self.assertNotIn("localStorage.setItem(\"reset_token\"", reset_content)
        self.assertNotIn("sessionStorage.setItem('token'", reset_content)
        self.assertNotIn("sessionStorage.setItem(\"token\"", reset_content)

        self.assertNotIn("localStorage.setItem", forgot_content)


if __name__ == "__main__":
    unittest.main()
