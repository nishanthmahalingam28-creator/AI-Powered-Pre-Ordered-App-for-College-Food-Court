"""
Automated Test Suite for Phase 12 — Production Security & Deployment Remediation.

Verifies:
1. Requirements.txt contains razorpay and cryptography dependencies.
2. Production payment fail-fast: No silent fallback to sandbox/mock orders when official Razorpay SDK is unavailable.
3. Production configuration validation: Fails fast on missing or placeholder SECRET_KEY, DB_PASSWORD, RAZORPAY_KEY_ID (rejects rzp_test_), RAZORPAY_KEY_SECRET, RAZORPAY_WEBHOOK_SECRET.
4. Production database policy: Direct and indirect SQLite usage is strictly rejected when FLASK_ENV=production.
5. Docker networking security: docker-compose.yml does not bind MySQL 3306 or Gunicorn 5000 directly to host ports; isolates services on internal_net and exposes only Nginx on public_net.
6. Docker compose mandatory environment variables: Insecure default passwords and secret fallbacks removed.
7. Deployment artifact hygiene: .gitignore and .dockerignore strictly exclude .pytest_cache/, *.pyc, food_court_local.db, and test artifacts.
8. Frontend key resolution: Client-side JavaScript (config.js, orders.js, preorder.js) contains no hardcoded test keys.
9. Production cookie and CORS security: SameSite=Lax, HttpOnly=True, Secure=True (in prod), wildcard '*' rejected with credentials.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from config import ProductionConfig, DevelopmentConfig, TestingConfig, BaseConfig
from db import is_production, get_sqlite_connection, get_db_connection, DatabaseConnectionError
from services.payment_provider import RazorpayProvider


class TestPhase12Remediation(unittest.TestCase):

    # =========================================================================
    # 1. DEPENDENCY INTEGRITY (STEP 2 & STEP 7)
    # =========================================================================

    def test_01_requirements_contains_razorpay_and_cryptography(self):
        """requirements.txt must explicitly declare razorpay and cryptography."""
        req_path = os.path.join(ROOT_DIR, "requirements.txt")
        self.assertTrue(os.path.exists(req_path), "requirements.txt must exist.")
        with open(req_path, "r", encoding="utf-8") as f:
            content = f.read().lower()
        self.assertIn("razorpay", content, "Official razorpay package must be in requirements.txt")
        self.assertIn("cryptography", content, "cryptography package must be in requirements.txt")
        self.assertIn("pymysql", content, "pymysql package must be in requirements.txt")
        self.assertIn("flask", content, "flask package must be in requirements.txt")
        self.assertIn("gunicorn", content, "gunicorn package must be in requirements.txt")

    # =========================================================================
    # 2. PAYMENT PROVIDER PRODUCTION FAIL-FAST (STEP 2 & STEP 12)
    # =========================================================================

    def test_02_payment_provider_fails_fast_if_razorpay_missing_in_production(self):
        """In production, RazorpayProvider refuses to initialize if razorpay SDK is missing."""
        with patch("services.payment_provider.RAZORPAY_INSTALLED", False):
            with self.assertRaises(RuntimeError) as ctx:
                RazorpayProvider(is_prod=True)
            self.assertIn("official 'razorpay' package is required", str(ctx.exception).lower())

    def test_03_payment_provider_order_creation_fails_fast_in_production_without_client(self):
        """In production, create_order cannot silently fallback to sandbox order generation."""
        provider = RazorpayProvider(is_prod=False)
        provider.is_prod = True
        provider.client = None
        with self.assertRaises(RuntimeError) as ctx:
            provider.create_order(amount_paise=10000, receipt="TEST-RECEIPT-01")
        self.assertIn("Official Razorpay client is unavailable", str(ctx.exception))

    # =========================================================================
    # 3. PRODUCTION CONFIGURATION VALIDATION (STEP 3 & STEP 8)
    # =========================================================================

    def test_04_production_config_rejects_missing_or_short_secret_key(self):
        """ProductionConfig strictly fails fast if SECRET_KEY is missing or insecure."""
        with patch.dict(os.environ, {"SECRET_KEY": "", "FLASK_ENV": "production"}):
            with self.assertRaises(RuntimeError) as ctx:
                ProductionConfig()
            self.assertIn("SECRET_KEY", str(ctx.exception))

        with patch.dict(os.environ, {"SECRET_KEY": "short", "FLASK_ENV": "production"}):
            with self.assertRaises(RuntimeError) as ctx:
                ProductionConfig()
            self.assertIn("SECRET_KEY", str(ctx.exception))

    def test_05_production_config_rejects_missing_database_credentials(self):
        """ProductionConfig strictly fails fast if DB_PASSWORD and DATABASE_URL are absent."""
        clean_env = {
            "SECRET_KEY": "valid-production-secret-key-32-bytes-long",
            "FLASK_ENV": "production",
            "DB_PASSWORD": "",
            "DATABASE_URL": "",
        }
        with patch.dict(os.environ, clean_env):
            with self.assertRaises(RuntimeError) as ctx:
                ProductionConfig()
            self.assertIn("DB_PASSWORD", str(ctx.exception))

    def test_06_production_config_rejects_placeholder_or_test_razorpay_keys(self):
        """ProductionConfig strictly refuses sandbox rzp_test_ keys or placeholder keys in production."""
        base_env = {
            "SECRET_KEY": "valid-production-secret-key-32-bytes-long",
            "FLASK_ENV": "production",
            "DB_PASSWORD": "ValidProdDbPassword2026!",
            "RAZORPAY_KEY_ID": "rzp_test_collegefoodcourt2026",
            "RAZORPAY_KEY_SECRET": "valid_secret",
            "RAZORPAY_WEBHOOK_SECRET": "valid_webhook_secret",
        }
        with patch.dict(os.environ, base_env):
            with self.assertRaises(RuntimeError) as ctx:
                ProductionConfig()
            self.assertIn("RAZORPAY_KEY_ID", str(ctx.exception))

        # Missing key secret
        base_env["RAZORPAY_KEY_ID"] = "rzp_live_realcollegekey123"
        base_env["RAZORPAY_KEY_SECRET"] = ""
        with patch.dict(os.environ, base_env):
            with self.assertRaises(RuntimeError) as ctx:
                ProductionConfig()
            self.assertIn("RAZORPAY_KEY_SECRET", str(ctx.exception))

        # Missing webhook secret
        base_env["RAZORPAY_KEY_SECRET"] = "LiveSecretKey987654321"
        base_env["RAZORPAY_WEBHOOK_SECRET"] = ""
        with patch.dict(os.environ, base_env):
            with self.assertRaises(RuntimeError) as ctx:
                ProductionConfig()
            self.assertIn("RAZORPAY_WEBHOOK_SECRET", str(ctx.exception))

    def test_07_production_config_succeeds_with_valid_production_secrets(self):
        """ProductionConfig successfully loads when all production parameters are compliant."""
        valid_env = {
            "SECRET_KEY": "valid-production-secret-key-32-bytes-long",
            "FLASK_ENV": "production",
            "DB_PASSWORD": "ValidProdDbPassword2026!",
            "RAZORPAY_KEY_ID": "rzp_live_collegefoodcourt2026",
            "RAZORPAY_KEY_SECRET": "LiveSecretKey987654321",
            "RAZORPAY_WEBHOOK_SECRET": "LiveWebhookSecret12345678",
            "COOKIE_SECURE": "1",
        }
        with patch.dict(os.environ, valid_env):
            cfg = ProductionConfig()
            self.assertEqual(cfg.ENV, "production")
            self.assertFalse(cfg.DEBUG)
            self.assertFalse(cfg.TESTING)
            self.assertTrue(cfg.SESSION_COOKIE_SECURE)

    # =========================================================================
    # 4. PRODUCTION DATABASE POLICY (STEP 5)
    # =========================================================================

    def test_08_production_mode_prohibits_direct_sqlite_connection(self):
        """Calling get_sqlite_connection() in production raises DatabaseConnectionError."""
        with patch.dict(os.environ, {"FLASK_ENV": "production"}):
            self.assertTrue(is_production())
            with self.assertRaises(DatabaseConnectionError) as ctx:
                get_sqlite_connection()
            self.assertIn("SQLite connection attempted in production mode", str(ctx.exception))

    def test_09_production_mode_prohibits_use_sqlite_flag(self):
        """In production mode, get_db_connection() never falls back to SQLite even if USE_SQLITE=1."""
        with patch.dict(os.environ, {"FLASK_ENV": "production", "USE_SQLITE": "1", "DB_HOST": "127.0.0.1", "DB_NAME": "food_court_db"}):
            self.assertTrue(is_production())
            with patch("pymysql.connect", side_effect=Exception("MySQL unreachable")):
                with self.assertRaises(DatabaseConnectionError) as ctx:
                    get_db_connection()
                self.assertIn("unavailable", str(ctx.exception).lower())

    # =========================================================================
    # 5. DOCKER NETWORKING & SECURITY (STEP 4)
    # =========================================================================

    def test_10_docker_compose_does_not_expose_mysql_or_gunicorn_to_host(self):
        """docker-compose.yml must not bind 3306:3306 or 5000:5000 to public host ports."""
        compose_path = os.path.join(ROOT_DIR, "docker-compose.yml")
        self.assertTrue(os.path.exists(compose_path))
        with open(compose_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Ensure no host port mapping for MySQL or Gunicorn
        self.assertNotIn('"3306:3306"', content)
        self.assertNotIn("- 3306:3306", content)
        self.assertNotIn('"5000:5000"', content)
        self.assertNotIn("- 5000:5000", content)

        # Ensure nginx reverse proxy is configured with ports 80/443
        self.assertIn("nginx:", content)
        self.assertIn('"80:80"', content)
        self.assertIn('"443:443"', content)

        # Ensure internal network isolation
        self.assertIn("internal_net", content)
        self.assertIn("public_net", content)

    def test_11_docker_compose_requires_mandatory_environment_variables(self):
        """docker-compose.yml must enforce required syntax (:?...) for critical secrets."""
        compose_path = os.path.join(ROOT_DIR, "docker-compose.yml")
        with open(compose_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("${DB_PASSWORD:?DB_PASSWORD is required}", content)
        self.assertIn("${SECRET_KEY:?SECRET_KEY is required}", content)
        self.assertIn("${RAZORPAY_KEY_ID:?RAZORPAY_KEY_ID is required}", content)
        self.assertIn("${RAZORPAY_KEY_SECRET:?RAZORPAY_KEY_SECRET is required}", content)
        self.assertIn("${RAZORPAY_WEBHOOK_SECRET:?RAZORPAY_WEBHOOK_SECRET is required}", content)

    # =========================================================================
    # 6. ARTIFACT EXCLUSION & CLEAN RELEASE (STEP 6)
    # =========================================================================

    def test_12_release_artifacts_excluded_in_gitignore_and_dockerignore(self):
        """.gitignore and .dockerignore must exclude .pytest_cache and local sqlite databases."""
        gitignore_path = os.path.join(ROOT_DIR, ".gitignore")
        dockerignore_path = os.path.join(ROOT_DIR, ".dockerignore")

        with open(gitignore_path, "r", encoding="utf-8") as f:
            gi_content = f.read()
        with open(dockerignore_path, "r", encoding="utf-8") as f:
            di_content = f.read()

        for term in [".pytest_cache", "food_court_local.db", "*.db"]:
            self.assertIn(term, gi_content, f"{term} must be in .gitignore")
            self.assertIn(term, di_content, f"{term} must be in .dockerignore")

    # =========================================================================
    # 7. CLIENT-SIDE SECRET AUDIT (STEP 1 & STEP 3)
    # =========================================================================

    def test_13_frontend_contains_no_hardcoded_test_keys(self):
        """Client JS files must not contain hardcoded Razorpay test credentials."""
        js_files = [
            os.path.join(ROOT_DIR, "frontend", "js", "config.js"),
            os.path.join(ROOT_DIR, "frontend", "js", "customer", "orders.js"),
            os.path.join(ROOT_DIR, "frontend", "js", "customer", "preorder.js"),
        ]
        for path in js_files:
            self.assertTrue(os.path.exists(path), f"File {path} must exist.")
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertNotIn("rzp_test_collegefoodcourt2026", content,
                             f"{os.path.basename(path)} must not contain hardcoded test key")

    # =========================================================================
    # 8. CORS & COOKIE SECURITY (STEP 9 & STEP 10)
    # =========================================================================

    def test_14_production_cors_strips_wildcard(self):
        """ProductionConfig.get_cors_origins strips '*' to prevent credential leakage."""
        with patch.dict(os.environ, {"CORS_ORIGINS": "https://foodcourt.kpriet.ac.in, *"}):
            origins = ProductionConfig.get_cors_origins()
            self.assertNotIn("*", origins)
            self.assertIn("https://foodcourt.kpriet.ac.in", origins)

    def test_15_cookie_flags_security_defaults(self):
        """BaseConfig and ProductionConfig enforce HttpOnly, SameSite Lax, and Secure."""
        self.assertTrue(BaseConfig.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(BaseConfig.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertTrue(ProductionConfig.SESSION_COOKIE_SECURE)


if __name__ == "__main__":
    unittest.main()
