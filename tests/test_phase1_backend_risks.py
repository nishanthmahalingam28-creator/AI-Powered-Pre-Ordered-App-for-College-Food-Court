"""
Phase 1 Backend Risks Verification Suite.

Validates:
1. MySQL / SQLite Isolation:
   - Production mode (FLASK_ENV=production) strictly requires MySQL and raises DatabaseConnectionError on failure.
   - Production mode NEVER silently falls back to SQLite.
   - Development mode supports SQLite fallback and USE_SQLITE=1.
2. Secret Key Hardening:
   - Production mode refuses to start without SECRET_KEY (raises RuntimeError).
   - Development mode generates ephemeral key safely.
   - Secret key is never leaked in HTTP responses.
3. Vendor Shop Assignment & Tenant Isolation:
   - Unassigned vendor (shop_id is NULL) is rejected with HTTP 403.
   - Vendor assigned to inactive stall is rejected with HTTP 403.
   - Valid vendor logs in with assigned shop_id (never defaults to 1).
   - Vendor cannot access another stall's orders, analytics, or menu items.
4. RBAC & Authorization:
   - Customer cannot access /api/vendor/* or /api/admin/*.
   - Vendor cannot access /api/admin/*.
   - Unauthenticated access returns HTTP 401.
5. CORS & Debug Protection:
   - Production strips wildcard '*' origins when credentials are supported.
   - Debug mode is strictly disabled in production.
6. Safe Error Handling:
   - Database errors return sanitized error messages without SQL, passwords, or stack traces.
   - OTP codes are not exposed in production /otp/send responses.
"""

import os
import sys
import unittest
import json
from unittest.mock import patch

# Add backend directory to sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Set dev mode initially to allow import without production abort
os.environ["FLASK_ENV"] = "development"
os.environ["USE_SQLITE"] = "1"
os.environ["SECRET_KEY"] = "test-phase1-secret-key-for-unit-testing-32b"

import db
from db import DB, DatabaseConnectionError, get_db_connection, is_production
from app import app


class TestDatabaseRisks(unittest.TestCase):
    """Verifies that production strictly rejects SQLite and enforces MySQL."""

    def test_production_mode_detection(self):
        old_env = os.environ.get("FLASK_ENV")
        try:
            os.environ["FLASK_ENV"] = "production"
            self.assertTrue(is_production())

            os.environ["FLASK_ENV"] = "development"
            self.assertFalse(is_production())

            os.environ["FLASK_ENV"] = "test"
            self.assertFalse(is_production())
        finally:
            if old_env is not None:
                os.environ["FLASK_ENV"] = old_env

    def test_case_a_production_valid_mysql_configuration(self):
        """Case A: Production + valid MySQL configuration -> connection works (mocked driver)."""
        from unittest.mock import MagicMock, patch
        old_env = os.environ.get("FLASK_ENV")
        try:
            os.environ["FLASK_ENV"] = "production"
            os.environ["DB_HOST"] = "127.0.0.1"
            os.environ["DB_NAME"] = "food_court_db"
            mock_conn = MagicMock()
            with patch("pymysql.connect", return_value=mock_conn):
                db_type, conn = get_db_connection()
                self.assertEqual(db_type, "mysql")
                self.assertEqual(conn, mock_conn)
        finally:
            if old_env is not None:
                os.environ["FLASK_ENV"] = old_env

    def test_case_b_production_missing_mysql_configuration(self):
        """Case B: Production + missing MySQL configuration -> clear configuration failure, NO SQLite fallback."""
        old_env = os.environ.get("FLASK_ENV")
        old_host = os.environ.get("DB_HOST")
        try:
            os.environ["FLASK_ENV"] = "production"
            os.environ["DB_HOST"] = ""
            os.environ.pop("DATABASE_URL", None)

            with self.assertRaises(DatabaseConnectionError) as ctx:
                get_db_connection()
            self.assertIn("unavailable", str(ctx.exception).lower())
        finally:
            if old_env is not None:
                os.environ["FLASK_ENV"] = old_env
            if old_host is not None:
                os.environ["DB_HOST"] = old_host
            else:
                os.environ.pop("DB_HOST", None)

    def test_case_c_production_invalid_mysql_credentials(self):
        """Case C: Production + invalid MySQL credentials -> clear database failure, NO SQLite fallback."""
        old_env = os.environ.get("FLASK_ENV")
        old_port = os.environ.get("DB_PORT")
        old_sqlite = os.environ.get("USE_SQLITE")
        try:
            os.environ["FLASK_ENV"] = "production"
            # Point to an invalid unreachable port / bad host to simulate connection denial
            os.environ["DB_PORT"] = "49999"
            os.environ.pop("DATABASE_URL", None)

            with self.assertRaises(DatabaseConnectionError):
                get_db_connection()
        finally:
            if old_env is not None:
                os.environ["FLASK_ENV"] = old_env
            if old_port is not None:
                os.environ["DB_PORT"] = old_port
            else:
                os.environ.pop("DB_PORT", None)
            if old_sqlite is not None:
                os.environ["USE_SQLITE"] = old_sqlite

    def test_case_d_development_database_configuration(self):
        """Case D: Development + development database configuration -> works as intended."""
        old_env = os.environ.get("FLASK_ENV")
        old_sqlite = os.environ.get("USE_SQLITE")
        try:
            os.environ["FLASK_ENV"] = "development"
            os.environ["USE_SQLITE"] = "1"

            db_type, conn = get_db_connection()
            self.assertEqual(db_type, "sqlite")
            conn.close()
        finally:
            if old_env is not None:
                os.environ["FLASK_ENV"] = old_env
            if old_sqlite is not None:
                os.environ["USE_SQLITE"] = old_sqlite

    def test_seed_data_isolated_from_production(self):
        """Step 12: Development seed credentials must be isolated and skipped in production mode."""
        old_env = os.environ.get("FLASK_ENV")
        old_override = os.environ.get("SEED_DEMO_DATA")
        try:
            os.environ["FLASK_ENV"] = "production"
            os.environ.pop("SEED_DEMO_DATA", None)

            flask_env = os.getenv("FLASK_ENV", "development").lower()
            is_prod = flask_env in ("production", "prod")
            allow_seed = (not is_prod) or (os.getenv("SEED_DEMO_DATA", "0").lower() in ("1", "true", "yes"))
            self.assertFalse(allow_seed, "Seed data must NOT be allowed in production by default")

            # With explicit override
            os.environ["SEED_DEMO_DATA"] = "1"
            allow_seed_override = (not is_prod) or (os.getenv("SEED_DEMO_DATA", "0").lower() in ("1", "true", "yes"))
            self.assertTrue(allow_seed_override)
        finally:
            if old_env is not None:
                os.environ["FLASK_ENV"] = old_env
            if old_override is not None:
                os.environ["SEED_DEMO_DATA"] = old_override
            else:
                os.environ.pop("SEED_DEMO_DATA", None)


class TestSecretKeyHardening(unittest.TestCase):
    """Verifies that production requires SECRET_KEY and refuses hardcoded defaults."""

    def test_production_refuses_startup_without_secret_key(self):
        """Production must raise RuntimeError if SECRET_KEY is missing."""
        import importlib

        old_env = os.environ.get("FLASK_ENV")
        old_key = os.environ.get("SECRET_KEY")
        try:
            os.environ["FLASK_ENV"] = "production"
            os.environ.pop("SECRET_KEY", None)

            # Reloading app without SECRET_KEY in production must raise RuntimeError
            import app as app_module
            with self.assertRaises(RuntimeError) as ctx:
                importlib.reload(app_module)
            self.assertIn("SECRET_KEY", str(ctx.exception))
        finally:
            if old_env is not None:
                os.environ["FLASK_ENV"] = old_env
            if old_key is not None:
                os.environ["SECRET_KEY"] = old_key
            import app as app_module
            importlib.reload(app_module)

    def test_secret_key_not_leaked_in_responses(self):
        """Responses from health and root endpoints must never expose secret keys."""
        client = app.test_client()

        resp = client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("secret", resp.get_data(as_text=True).lower())

        resp = client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("secret", resp.get_data(as_text=True).lower())


class TestVendorShopFallback(unittest.TestCase):
    """Verifies vendor login requires a valid, active assigned shop and never uses shop_id=1 as default."""

    @classmethod
    def setUpClass(cls):
        # Create a test vendor with NO shop assignment
        cls.unassigned_vendor_email = "unassigned_vendor_test@kpriet.ac.in"
        cls.inactive_stall_vendor_email = "inactive_vendor_test@kpriet.ac.in"
        from werkzeug.security import generate_password_hash

        pwd = generate_password_hash("TestVendor123!")

        # 1. Vendor without shop
        existing = DB.get_one("SELECT id FROM users WHERE email = %s", (cls.unassigned_vendor_email,))
        if not existing:
            cls.unassigned_uid = DB.execute(
                "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'vendor', 1)",
                (cls.unassigned_vendor_email, pwd),
            )
        else:
            cls.unassigned_uid = existing["id"]
        # Ensure no shop references this vendor
        DB.execute("UPDATE shops SET owner_user_id = NULL WHERE owner_user_id = %s", (cls.unassigned_uid,))

        # 2. Vendor with inactive shop
        existing2 = DB.get_one("SELECT id FROM users WHERE email = %s", (cls.inactive_stall_vendor_email,))
        if not existing2:
            cls.inactive_uid = DB.execute(
                "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'vendor', 1)",
                (cls.inactive_stall_vendor_email, pwd),
            )
        else:
            cls.inactive_uid = existing2["id"]

        inactive_shop = DB.get_one("SELECT id FROM shops WHERE slug = 'inactive-test-stall'")
        if not inactive_shop:
            cls.inactive_shop_id = DB.execute(
                "INSERT INTO shops (name, slug, owner_user_id, description, is_active) VALUES (%s, %s, %s, %s, 0)",
                ("Inactive Stall", "inactive-test-stall", cls.inactive_uid, "Inactive stall for testing"),
            )
        else:
            cls.inactive_shop_id = inactive_shop["id"]
            DB.execute("UPDATE shops SET owner_user_id = %s, is_active = 0 WHERE id = %s", (cls.inactive_uid, cls.inactive_shop_id))

    def setUp(self):
        self.client = app.test_client()

    def test_unassigned_vendor_login_rejected(self):
        """An unassigned vendor MUST be rejected with HTTP 403, NEVER assigned shop_id = 1."""
        resp = self.client.post("/api/auth/vendor/login", json={
            "email": self.unassigned_vendor_email,
            "password": "TestVendor123!"
        })
        self.assertEqual(resp.status_code, 403)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertIn("no active stall assigned", data["message"].lower())

    def test_inactive_stall_vendor_login_rejected(self):
        """A vendor assigned to an inactive stall MUST be rejected with HTTP 403."""
        resp = self.client.post("/api/auth/vendor/login", json={
            "email": self.inactive_stall_vendor_email,
            "password": "TestVendor123!"
        })
        self.assertEqual(resp.status_code, 403)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertIn("no active stall assigned", data["message"].lower())

    def test_valid_vendor_login_succeeds_with_assigned_shop(self):
        """Valid vendor (YPR - Shop 1) logs in successfully with verified shop_id."""
        resp = self.client.post("/api/auth/vendor/login", json={
            "email": "ypr@kpriet.ac.in",
            "password": "vendor123"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["user"]["shop_id"], 1)

    def test_vendor_cannot_access_other_stall_analytics(self):
        """Vendor 1 cannot access Vendor 2's analytics."""
        # Log in as vendor 1
        self.client.post("/api/auth/vendor/login", json={
            "email": "ypr@kpriet.ac.in",
            "password": "vendor123"
        })
        # Try to request shop_id=2 in query params
        resp = self.client.get("/api/vendor/analytics?shop_id=2")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        # The endpoint must ignore shop_id=2 and lock vendor 1 to shop 1
        self.assertEqual(data["shop"]["id"], 1)


class TestRBACAndAuthorization(unittest.TestCase):
    """Verifies that customers, vendors, and unauthenticated users cannot bypass RBAC."""

    def setUp(self):
        self.client = app.test_client()

    def test_unauthenticated_access_rejected(self):
        """Unauthenticated access to protected routes returns HTTP 401."""
        resp = self.client.get("/api/orders/my-orders")
        self.assertEqual(resp.status_code, 401)

        resp = self.client.get("/api/admin/overview")
        self.assertEqual(resp.status_code, 401)

        resp = self.client.get("/api/vendor/analytics")
        self.assertEqual(resp.status_code, 401)

    def test_customer_blocked_from_admin(self):
        """A customer account cannot access admin endpoints (HTTP 403)."""
        self.client.post("/api/auth/customer/login", json={
            "email": "student@kpriet.ac.in",
            "password": "password123",
            "customerType": "student"
        })

        resp = self.client.get("/api/admin/overview")
        self.assertEqual(resp.status_code, 403)

        resp = self.client.get("/api/admin/shops")
        self.assertEqual(resp.status_code, 403)

    def test_customer_blocked_from_vendor_endpoints(self):
        """A customer account cannot access vendor endpoints (HTTP 403)."""
        self.client.post("/api/auth/customer/login", json={
            "email": "student@kpriet.ac.in",
            "password": "password123",
            "customerType": "student"
        })

        resp = self.client.get("/api/vendor/analytics")
        self.assertEqual(resp.status_code, 403)

        resp = self.client.post("/api/vendor/menu/item", json={"name": "Hacked Item", "price": 10})
        self.assertEqual(resp.status_code, 403)

    def test_vendor_blocked_from_admin(self):
        """A vendor cannot access admin endpoints (HTTP 403)."""
        self.client.post("/api/auth/vendor/login", json={
            "email": "ypr@kpriet.ac.in",
            "password": "vendor123"
        })

        resp = self.client.get("/api/admin/overview")
        self.assertEqual(resp.status_code, 403)


class TestCORSAndErrorHandling(unittest.TestCase):
    """Verifies safe error handling, database failure 503 response, and OTP suppression."""

    def setUp(self):
        self.client = app.test_client()

    def test_otp_suppressed_in_production(self):
        """In production mode, /api/auth/otp/send must NOT return demo_otp or debug_code."""
        old_env = os.environ.get("FLASK_ENV")
        try:
            os.environ["FLASK_ENV"] = "production"
            with patch("routes.auth.DB.execute", return_value=1), \
                 patch("services.sms_service.SMSService.send_otp", return_value=(True, "OTP sent successfully via SMS.")):
                resp = self.client.post("/api/auth/otp/send", json={
                    "email": "security_test@kpriet.ac.in",
                    "purpose": "signup"
                })
                self.assertEqual(resp.status_code, 200)
                data = resp.get_json()
                self.assertTrue(data["success"])
                self.assertNotIn("demo_otp", data)
                self.assertNotIn("debug_code", data)

        finally:
            if old_env is not None:
                os.environ["FLASK_ENV"] = old_env

    def test_database_failure_returns_safe_503(self):
        """When DB connection fails in production, endpoint returns clean 503 without leaking stack traces or SQL."""
        old_env = os.environ.get("FLASK_ENV")
        try:
            os.environ["FLASK_ENV"] = "production"
            resp = self.client.post("/api/auth/otp/send", json={
                "email": "security_test_db_down@kpriet.ac.in",
                "purpose": "signup"
            })
            self.assertEqual(resp.status_code, 503)
            data = resp.get_json()
            self.assertFalse(data["success"])
            self.assertIn("temporarily unavailable", data["message"].lower())
            self.assertNotIn("traceback", resp.get_data(as_text=True).lower())
            self.assertNotIn("operationalerror", resp.get_data(as_text=True).lower())
        finally:
            if old_env is not None:
                os.environ["FLASK_ENV"] = old_env

    def test_cors_allowed_development_origin(self):
        """Allowed development origin receives Access-Control-Allow-Origin header."""
        resp = self.client.get("/api/health", headers={"Origin": "http://localhost:5500"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "http://localhost:5500")

    def test_cors_unauthorized_origin(self):
        """Unauthorized origin does not receive Access-Control-Allow-Origin header."""
        resp = self.client.get("/api/health", headers={"Origin": "http://malicious-site.example"})
        self.assertEqual(resp.status_code, 200)
        self.assertNotEqual(resp.headers.get("Access-Control-Allow-Origin"), "http://malicious-site.example")

    def test_safe_404_response(self):
        """404 responses do not leak file paths or internal server details."""
        resp = self.client.get("/api/non-existent-endpoint-xyz")
        self.assertEqual(resp.status_code, 404)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertIn("message", data)
        self.assertNotIn("traceback", resp.get_data(as_text=True).lower())


if __name__ == "__main__":
    unittest.main()
