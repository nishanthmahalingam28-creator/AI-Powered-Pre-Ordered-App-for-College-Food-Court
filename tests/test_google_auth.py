"""
Comprehensive Automated Test Suite for Google Identity Services (GIS) Authentication.

Validates:
1. Successful Google Login: server-side verification, user provisioning/linking, session cookie creation.
2. Cancelled / Empty Google Login: rejected with 400 Bad Request, no session created.
3. Invalid Credential: invalid/expired/tampered tokens rejected with 401 Unauthorized.
4. Existing Account: existing database accounts are matched and authenticated without duplicate creation.
5. New Google Account: unseen Google accounts are created in users & customer_profiles with bcrypt password hash.
6. Logout: terminates Google session, subsequent requests to protected endpoints return 401.
7. Accessing Protected Pages: verified Google session can access /profile, /orders, /cart, /ai; unauthenticated gets 401.
8. Google Config Endpoint: exposes safe public client configuration without leaking secrets.
"""

import os
import sys
import unittest
from unittest.mock import patch
import bcrypt

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ["FLASK_ENV"] = "development"
os.environ["USE_SQLITE"] = "1"
os.environ["SECRET_KEY"] = "google-auth-test-key-32b-secret-min"
os.environ["GOOGLE_CLIENT_ID"] = "test-google-client-id.apps.googleusercontent.com"

import init_db
init_db.init_sqlite()

from db import DB
from app import app
from services.google_auth import GoogleAuthService, GoogleTokenVerificationError


class TestGoogleAuthentication(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()

    # -------------------------------------------------------------
    # Configuration Endpoint
    # -------------------------------------------------------------
    def test_google_config_endpoint(self):
        """GET /api/auth/google/config returns public configuration without exposing secrets."""
        res = self.client.get("/api/auth/google/config")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("client_id"), "test-google-client-id.apps.googleusercontent.com")
        self.assertTrue(data.get("enabled"))
        # Must never expose client secrets
        self.assertNotIn("secret", str(data).lower())
        self.assertNotIn("client_secret", data)

    # -------------------------------------------------------------
    # Test Case 1: Successful Google Login
    # -------------------------------------------------------------
    @patch.object(GoogleAuthService, "verify_token")
    def test_case_1_successful_google_login(self, mock_verify):
        """Valid Google credential establishes authenticated session with HttpOnly cookie."""
        mock_verify.return_value = {
            "sub": "google-user-123456789",
            "email": "verified.student@kpriet.ac.in",
            "name": "Verified Google Student",
            "picture": "https://lh3.googleusercontent.com/a/test-pic",
            "email_verified": True
        }

        res = self.client.post("/api/auth/google", json={
            "credential": "valid.google.id.token.jwt"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data["user"]["email"], "verified.student@kpriet.ac.in")
        self.assertEqual(data["user"]["auth_provider"], "google")

        # Verify HttpOnly session cookie was issued
        cookie_header = res.headers.get("Set-Cookie")
        self.assertIsNotNone(cookie_header)
        self.assertIn("session=", cookie_header)
        self.assertIn("HttpOnly", cookie_header)

        # Verify /auth/me returns authenticated state
        me_res = self.client.get("/api/auth/me")
        self.assertEqual(me_res.status_code, 200)
        me_data = me_res.get_json()
        self.assertTrue(me_data.get("authenticated"))
        self.assertEqual(me_data["user"]["email"], "verified.student@kpriet.ac.in")

    # -------------------------------------------------------------
    # Test Case 2: Cancelled / Empty Google Login
    # -------------------------------------------------------------
    def test_case_2_cancelled_or_empty_google_login(self):
        """Empty, whitespace, or missing token returns 400 Bad Request and does NOT log in."""
        # 1. Missing credential
        res1 = self.client.post("/api/auth/google", json={})
        self.assertEqual(res1.status_code, 400)
        self.assertFalse(res1.get_json().get("success"))
        self.assertIn("required", res1.get_json().get("message", "").lower())

        # 2. Empty string credential
        res2 = self.client.post("/api/auth/google", json={"credential": "   "})
        self.assertEqual(res2.status_code, 400)
        self.assertFalse(res2.get_json().get("success"))

        # Verify session was NOT created
        me_res = self.client.get("/api/auth/me")
        self.assertFalse(me_res.get_json().get("authenticated"))

    # -------------------------------------------------------------
    # Test Case 3: Invalid Credential
    # -------------------------------------------------------------
    @patch.object(GoogleAuthService, "verify_token")
    def test_case_3_invalid_credential(self, mock_verify):
        """Invalid, expired, or tampered token returns 401 Unauthorized and rejects login."""
        mock_verify.side_effect = GoogleTokenVerificationError(
            "Google authentication failed: Invalid, expired, or tampered token."
        )

        res = self.client.post("/api/auth/google", json={
            "credential": "tampered.or.expired.fake.token"
        })
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertFalse(data.get("success"))
        self.assertIn("invalid", data.get("message", "").lower())

        # Verify session was NOT created
        me_res = self.client.get("/api/auth/me")
        self.assertFalse(me_res.get_json().get("authenticated"))

    # -------------------------------------------------------------
    # Test Case 4: Existing Account Matching
    # -------------------------------------------------------------
    @patch.object(GoogleAuthService, "verify_token")
    def test_case_4_existing_account(self, mock_verify):
        """Existing user in database logging in via Google is matched and not duplicated."""
        # 'student@kpriet.ac.in' is seeded in init_db
        existing_user = DB.get_one("SELECT id, email FROM users WHERE email = 'student@kpriet.ac.in'")
        self.assertIsNotNone(existing_user)
        original_user_id = existing_user["id"]

        mock_verify.return_value = {
            "sub": "google-existing-sub-999",
            "email": "student@kpriet.ac.in",
            "name": "Original Student Name",
            "email_verified": True
        }

        res = self.client.post("/api/auth/google", json={"credential": "mock.jwt.existing"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data["user"]["id"], original_user_id)
        self.assertEqual(data["user"]["email"], "student@kpriet.ac.in")

        # Verify no duplicate user was inserted
        user_rows = DB.get_all("SELECT id FROM users WHERE email = 'student@kpriet.ac.in'")
        self.assertEqual(len(user_rows), 1, "User record must not be duplicated")

    # -------------------------------------------------------------
    # Test Case 5: New Google Account Provisioning
    # -------------------------------------------------------------
    @patch.object(GoogleAuthService, "verify_token")
    def test_case_5_new_google_account(self, mock_verify):
        """Unseen Google account is safely provisioned in database with bcrypt hash and profile."""
        new_email = "new.google.guest.2026@gmail.com"
        # Ensure user does not pre-exist
        DB.execute("DELETE FROM users WHERE email = %s", (new_email,))

        mock_verify.return_value = {
            "sub": "google-new-sub-777",
            "email": new_email,
            "name": "New Google Visitor",
            "email_verified": True
        }

        res = self.client.post("/api/auth/google", json={
            "credential": "mock.jwt.new.user",
            "customerType": "guest"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data["user"]["customer_type"], "guest")
        self.assertEqual(data["user"]["full_name"], "New Google Visitor")

        # Verify user in database
        db_user = DB.get_one("SELECT id, email, password_hash, role, is_active FROM users WHERE email = %s", (new_email,))
        self.assertIsNotNone(db_user, "User must be created in the database")
        self.assertEqual(db_user["role"], "customer")
        self.assertEqual(db_user["is_active"], 1)

        # Verify password is secure bcrypt hash (never plaintext)
        pw_hash = db_user["password_hash"]
        self.assertTrue(pw_hash.startswith("$2b$") or pw_hash.startswith("$2a$"))
        self.assertEqual(len(pw_hash), 60)

        # Verify customer profile
        db_profile = DB.get_one("SELECT customer_type, full_name, wallet_balance FROM customer_profiles WHERE user_id = %s", (db_user["id"],))
        self.assertIsNotNone(db_profile)
        self.assertEqual(db_profile["customer_type"], "guest")
        self.assertEqual(db_profile["full_name"], "New Google Visitor")

    # -------------------------------------------------------------
    # Test Case 6: Logout
    # -------------------------------------------------------------
    @patch.object(GoogleAuthService, "verify_token")
    def test_case_6_logout_after_google_login(self, mock_verify):
        """Logging out invalidates Google authenticated session."""
        mock_verify.return_value = {
            "sub": "google-logout-sub-111",
            "email": "logout.test@kpriet.ac.in",
            "name": "Logout Tester",
            "email_verified": True
        }

        login_res = self.client.post("/api/auth/google", json={"credential": "mock.jwt.logout"})
        self.assertEqual(login_res.status_code, 200)

        # Verify active session
        me_res1 = self.client.get("/api/auth/me")
        self.assertTrue(me_res1.get_json().get("authenticated"))

        # Logout
        logout_res = self.client.post("/api/auth/logout")
        self.assertEqual(logout_res.status_code, 200)
        self.assertTrue(logout_res.get_json().get("success"))

        # Invalidate verification: /auth/me returns 401 unauthenticated
        me_res2 = self.client.get("/api/auth/me")
        self.assertEqual(me_res2.status_code, 401)
        self.assertFalse(me_res2.get_json().get("authenticated"))

    # -------------------------------------------------------------
    # Test Case 7: Accessing Protected Pages after Google Login
    # -------------------------------------------------------------
    @patch.object(GoogleAuthService, "verify_token")
    def test_case_7_accessing_protected_pages(self, mock_verify):
        """Google authenticated session has access to protected APIs; unauthenticated gets 401."""
        unauthed_client = self.app.test_client()
        # Verify unauthenticated client cannot access protected APIs
        self.assertEqual(unauthed_client.get("/api/customer/profile").status_code, 401)
        self.assertEqual(unauthed_client.get("/api/orders/my-orders").status_code, 401)
        self.assertEqual(unauthed_client.get("/api/cart").status_code, 401)
        self.assertEqual(unauthed_client.get("/api/ai/recommendations").status_code, 401)

        # Authenticate via Google
        mock_verify.return_value = {
            "sub": "google-protected-sub-222",
            "email": "protected.tester@kpriet.ac.in",
            "name": "Protected Page Tester",
            "email_verified": True
        }
        login_res = self.client.post("/api/auth/google", json={"credential": "mock.jwt.protected"})
        self.assertEqual(login_res.status_code, 200)

        # Authenticated client CAN access protected APIs
        prof_res = self.client.get("/api/customer/profile")
        self.assertEqual(prof_res.status_code, 200)
        self.assertTrue(prof_res.get_json().get("success"))

        orders_res = self.client.get("/api/orders/my-orders")
        self.assertEqual(orders_res.status_code, 200)
        self.assertTrue(orders_res.get_json().get("success"))

        cart_res = self.client.get("/api/cart")
        self.assertEqual(cart_res.status_code, 200)
        self.assertTrue(cart_res.get_json().get("success"))

        ai_res = self.client.get("/api/ai/recommendations")
        self.assertEqual(ai_res.status_code, 200)
        self.assertTrue(ai_res.get_json().get("success"))

    # -------------------------------------------------------------
    # Deactivated Account Security Check
    # -------------------------------------------------------------
    @patch.object(GoogleAuthService, "verify_token")
    def test_deactivated_account_rejected(self, mock_verify):
        """Deactivated accounts cannot authenticate via Google (returns 403)."""
        deact_email = "deactivated.user@kpriet.ac.in"
        pw_hash = bcrypt.hashpw(b"test12345", bcrypt.gensalt(12)).decode("utf-8")
        DB.execute("DELETE FROM users WHERE email = %s", (deact_email,))
        DB.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 0)",
            (deact_email, pw_hash)
        )

        mock_verify.return_value = {
            "sub": "google-deact-sub-000",
            "email": deact_email,
            "name": "Deactivated User",
            "email_verified": True
        }

        res = self.client.post("/api/auth/google", json={"credential": "mock.jwt.deact"})
        self.assertEqual(res.status_code, 403)
        self.assertFalse(res.get_json().get("success"))
        self.assertIn("deactivated", res.get_json().get("message", "").lower())

    # -------------------------------------------------------------
    # Client ID Formatting & Quoting Resilience
    # -------------------------------------------------------------
    def test_client_id_quotes_and_whitespace_stripped(self):
        """GOOGLE_CLIENT_ID handles whitespace, double quotes, and single quotes from deployment configs."""
        with patch.dict(os.environ, {"GOOGLE_CLIENT_ID": '  "quoted-client-id.apps.googleusercontent.com"  '}):
            self.assertEqual(GoogleAuthService.get_client_id(), "quoted-client-id.apps.googleusercontent.com")

        with patch.dict(os.environ, {"GOOGLE_CLIENT_ID": " 'single-quoted-id.apps.googleusercontent.com' "}):
            self.assertEqual(GoogleAuthService.get_client_id(), "single-quoted-id.apps.googleusercontent.com")

    # -------------------------------------------------------------
    # Token Audience Verification with List and String aud Claims
    # -------------------------------------------------------------
    @patch("services.google_auth.id_token.verify_oauth2_token")
    def test_verify_token_aud_list_accepted(self, mock_verify):
        """Token with list audience containing the configured client_id is accepted."""
        test_client_id = GoogleAuthService.get_client_id()
        mock_verify.return_value = {
            "iss": "https://accounts.google.com",
            "aud": [test_client_id, "secondary-app-id"],
            "sub": "sub-12345",
            "email": "test.aud.list@kpriet.ac.in",
            "email_verified": True,
            "name": "Aud List User"
        }

        claims = GoogleAuthService.verify_token("mock.jwt.aud.list")
        self.assertEqual(claims["email"], "test.aud.list@kpriet.ac.in")

    @patch("services.google_auth.id_token.verify_oauth2_token")
    def test_verify_token_aud_mismatch_rejected(self, mock_verify):
        """Token with audience not matching configured client_id raises GoogleTokenVerificationError."""
        mock_verify.return_value = {
            "iss": "https://accounts.google.com",
            "aud": "different-unauthorized-client-id.apps.googleusercontent.com",
            "sub": "sub-12345",
            "email": "mismatch@kpriet.ac.in",
            "email_verified": True,
            "name": "Mismatch User"
        }

        with self.assertRaises(GoogleTokenVerificationError):
            GoogleAuthService.verify_token("mock.jwt.mismatch")


if __name__ == "__main__":
    unittest.main()

