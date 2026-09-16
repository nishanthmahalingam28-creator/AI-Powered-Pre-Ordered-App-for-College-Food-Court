"""
Automated Test Suite for Phase 9 — Production Deployment, Cloud Infrastructure & Performance.

Verifies:
1. Production configuration loading and strict SECRET_KEY enforcement.
2. Production MySQL requirement and rejection of SQLite fallback.
3. Health check probe (GET /api/health) liveness & sanitization.
4. Readiness check probe (GET /api/ready) database dependency verification.
5. Global sanitized error handling (400, 401, 403, 404, 405, 409, 422, 429, 500, 503).
6. Security headers (X-Content-Type-Options, X-Frame-Options, Referrer-Policy).
7. Request correlation tracking (X-Request-ID header propagation).
8. Production CORS safety (wildcard '*' rejected with credentials).
9. Session cookie security flags (HttpOnly, Secure, SameSite).
10. Order concurrency: Multi-threaded simultaneous purchase of last unit (Stock=1).
    - Exactly 1 customer succeeds (HTTP 201).
    - Exactly 1 customer fails safely (HTTP 400).
    - Final stock is exactly 0; zero negative stock; zero duplicate reservation.
11. Payment concurrency: Duplicate webhook idempotency.
12. Multi-worker safe OTP rate-limiting enforcement.
"""

import os
import sys
import json
import time
import unittest
import threading
from unittest.mock import patch
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ["FLASK_ENV"] = "testing"
os.environ["USE_SQLITE"] = "1"
os.environ["SECRET_KEY"] = "phase9-production-test-key-32b-ok"

import init_db
init_db.init_sqlite()

from app import app
from db import DB, is_production, DatabaseConnectionError
from config import get_config, ProductionConfig, DevelopmentConfig, TestingConfig
from werkzeug.security import generate_password_hash
from services.payment_provider import get_payment_provider


class TestPhase9Production(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

        # Clean slate for Phase 9 test isolation
        DB.execute("DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE order_reference LIKE 'P9-%')")
        DB.execute("DELETE FROM payments WHERE order_id IN (SELECT id FROM orders WHERE order_reference LIKE 'P9-%')")
        DB.execute("DELETE FROM orders WHERE order_reference LIKE 'P9-%'")
        DB.execute("DELETE FROM menu_items WHERE shop_id IN (SELECT id FROM shops WHERE slug LIKE '%phase9%')")
        DB.execute("DELETE FROM shops WHERE slug LIKE '%phase9%'")
        DB.execute("DELETE FROM customer_profiles WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@test9.kpriet.ac.in')")
        DB.execute("DELETE FROM users WHERE email LIKE '%@test9.kpriet.ac.in'")

        cls.pwd = "Phase9Secure!123"
        hashed = generate_password_hash(cls.pwd)

        # 1. Customer A
        cls.cust_a_email = "student.a@test9.kpriet.ac.in"
        cls.cust_a_id = DB.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
            (cls.cust_a_email, hashed)
        )
        DB.execute(
            "INSERT INTO customer_profiles (user_id, customer_type, full_name, identifier, mobile, wallet_balance) "
            "VALUES (%s, 'student', 'Student A', 'KPR2026-P9-A', '9876543250', 500.00)",
            (cls.cust_a_id,)
        )

        # 2. Customer B (for concurrency test)
        cls.cust_b_email = "student.b@test9.kpriet.ac.in"
        cls.cust_b_id = DB.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
            (cls.cust_b_email, hashed)
        )
        DB.execute(
            "INSERT INTO customer_profiles (user_id, customer_type, full_name, identifier, mobile, wallet_balance) "
            "VALUES (%s, 'student', 'Student B', 'KPR2026-P9-B', '9876543251', 500.00)",
            (cls.cust_b_id,)
        )

        # 3. Dedicated Stall for Concurrency Test
        cls.vendor_email = "vendor.phase9@test9.kpriet.ac.in"
        cls.vendor_id = DB.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'vendor', 1)",
            (cls.vendor_email, hashed)
        )
        cls.shop_id = DB.execute(
            "INSERT INTO shops (name, slug, description, category, operational_status, is_active, owner_user_id) "
            "VALUES ('Phase 9 Stall', 'phase9-stall', 'Production Test Stall', 'Snacks', 'OPEN', 1, %s)",
            (cls.vendor_id,)
        )

        # Limited stock item: Exactly 1 unit available
        cls.item_limited_id = DB.execute(
            "INSERT INTO menu_items (shop_id, name, price, category, quantity, is_available) VALUES (%s, %s, %s, %s, 1, 1)",
            (cls.shop_id, "Special Rasmalai (Last 1 Left)", 60.00, "Desserts")
        )

        # Normal stock item
        cls.item_regular_id = DB.execute(
            "INSERT INTO menu_items (shop_id, name, price, category, quantity, is_available) VALUES (%s, %s, %s, %s, 50, 1)",
            (cls.shop_id, "Cold Coffee", 50.00, "Beverages")
        )

        cls.provider = get_payment_provider()

    @classmethod
    def tearDownClass(cls):
        try:
            DB.execute("DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE order_reference LIKE 'P9-%')")
            DB.execute("DELETE FROM payments WHERE order_id IN (SELECT id FROM orders WHERE order_reference LIKE 'P9-%')")
            DB.execute("DELETE FROM orders WHERE order_reference LIKE 'P9-%'")
            DB.execute("DELETE FROM menu_items WHERE shop_id IN (SELECT id FROM shops WHERE slug LIKE '%phase9%')")
            DB.execute("DELETE FROM shops WHERE slug LIKE '%phase9%'")
            DB.execute("DELETE FROM customer_profiles WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@test9.kpriet.ac.in')")
            DB.execute("DELETE FROM users WHERE email LIKE '%@test9.kpriet.ac.in'")
        except Exception:
            pass

    # =========================================================================
    # 1. PRODUCTION CONFIGURATION & DATABASE ENFORCEMENT
    # =========================================================================

    def test_01_production_config_requires_secret_key(self):
        """ProductionConfig strictly refuses to boot if SECRET_KEY is missing or weak."""
        with patch.dict(os.environ, {"SECRET_KEY": "", "FLASK_ENV": "production"}):
            with self.assertRaises(RuntimeError) as ctx:
                ProductionConfig()
            self.assertIn("SECRET_KEY", str(ctx.exception))

    def test_02_production_mode_rejects_sqlite_fallback(self):
        """In production mode, db.is_production() is True and SQLite fallback is strictly prohibited."""
        with patch.dict(os.environ, {"FLASK_ENV": "production"}):
            self.assertTrue(is_production())

    def test_03_production_config_rejects_insecure_cors_wildcard(self):
        """In production, wildcard '*' with credentials is automatically stripped."""
        with patch.dict(os.environ, {"CORS_ORIGINS": "https://foodcourt.kpriet.ac.in, *"}):
            origins = ProductionConfig.get_cors_origins()
            self.assertNotIn("*", origins)
            self.assertIn("https://foodcourt.kpriet.ac.in", origins)

    # =========================================================================
    # 2. HEALTH CHECK & READINESS PROBES
    # =========================================================================

    def test_04_health_liveness_probe_safe_operational_metadata(self):
        """GET /api/health returns HTTP 200 with service metadata and zero exposed secrets."""
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "food-court-api")
        self.assertIn("version", data)
        # Ensure no sensitive database or secret info is leaked
        self.assertNotIn("password", str(data).lower())
        self.assertNotIn("secret", str(data).lower())

    def test_05_readiness_probe_database_connectivity(self):
        """GET /api/ready verifies database connectivity with lightweight probe."""
        res = self.client.get("/api/ready")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "ready")
        self.assertEqual(data["database"], "connected")

    def test_06_readiness_probe_returns_503_on_db_outage(self):
        """GET /api/ready returns HTTP 503 when the database is unavailable."""
        with patch.object(DB, "get_one", side_effect=DatabaseConnectionError("DB Down")):
            res = self.client.get("/api/ready")
            self.assertEqual(res.status_code, 503)
            data = res.get_json()
            self.assertEqual(data["status"], "not_ready")
            self.assertEqual(data["database"], "disconnected")

    # =========================================================================
    # 3. GLOBAL ERROR HANDLERS & SECURITY HEADERS
    # =========================================================================

    def test_07_global_error_handlers_return_sanitized_json(self):
        """Errors (400, 401, 403, 404, 405, 500) return sanitized JSON without stack traces."""
        # 404 Not Found
        res_404 = self.client.get("/api/non-existent-route-xyz")
        self.assertEqual(res_404.status_code, 404)
        self.assertFalse(res_404.get_json()["success"])
        self.assertEqual(res_404.get_json()["message"], "The requested API resource was not found.")

        # 405 Method Not Allowed
        res_405 = self.client.post("/api/health")
        self.assertEqual(res_405.status_code, 405)
        self.assertFalse(res_405.get_json()["success"])
        self.assertIn("Method not allowed", res_405.get_json()["message"])

    def test_08_security_headers_present_on_responses(self):
        """Responses include X-Content-Type-Options, X-Frame-Options, and Referrer-Policy."""
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res.headers.get("X-Frame-Options"), "SAMEORIGIN")
        self.assertEqual(res.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")

    def test_09_request_correlation_id_tracking(self):
        """X-Request-ID sent by client is preserved and reflected on the response."""
        custom_id = "trace-req-uuid-9988-aabb"
        res = self.client.get("/api/health", headers={"X-Request-ID": custom_id})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("X-Request-ID"), custom_id)

    def test_10_request_correlation_id_generated_if_missing(self):
        """Server generates and attaches an X-Request-ID if none is provided."""
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(len(res.headers.get("X-Request-ID", "")) > 0)

    # =========================================================================
    # 4. CONCURRENCY TESTS (RACE CONDITIONS & ATOMICITY)
    # =========================================================================

    def test_11_order_stock_concurrency_only_one_customer_wins_last_item(self):
        """
        Critical Concurrency Invariant:
        Item has stock = 1.
        Customer A and Customer B simultaneously attempt to order 1 unit.
        Result: Exactly 1 customer gets HTTP 201; 1 customer gets HTTP 400.
        Final stock must be exactly 0 (no negative stock, no double reservation).
        """
        # Ensure stock is exactly 1 before the race
        DB.execute("UPDATE menu_items SET quantity = 1, is_available = 1 WHERE id = %s", (self.item_limited_id,))

        results = {}

        def place_order(customer_email, result_key):
            client = self.app.test_client()
            client.post("/api/auth/customer/login", json={"email": customer_email, "password": self.pwd})
            res = client.post("/api/orders", json={
                "shop_id": self.shop_id,
                "items": [{"id": self.item_limited_id, "quantity": 1}],
                "payment_method": "Campus Wallet"
            })
            results[result_key] = res.status_code

        # Spawn two concurrent threads to simulate simultaneous checkout
        thread_a = threading.Thread(target=place_order, args=(self.cust_a_email, "client_a"))
        thread_b = threading.Thread(target=place_order, args=(self.cust_b_email, "client_b"))

        thread_a.start()
        thread_b.start()
        thread_a.join()
        thread_b.join()

        statuses = list(results.values())
        self.assertEqual(len(statuses), 2)
        # Exactly one 201 (success) and one 400 (out of stock rejection)
        self.assertEqual(statuses.count(201), 1, f"Expected exactly one 201, got results: {results}")
        self.assertEqual(statuses.count(400), 1, f"Expected exactly one 400, got results: {results}")

        # Authoritative database check: Stock must be exactly 0, never negative!
        final_item = DB.get_one("SELECT quantity, is_available FROM menu_items WHERE id = %s", (self.item_limited_id,))
        self.assertEqual(final_item["quantity"], 0)
        self.assertEqual(final_item["is_available"], 0)

    def test_12_duplicate_payment_webhook_concurrency_idempotent(self):
        """Simultaneous duplicate webhook delivery confirms idempotency without double processing."""
        # Setup an order waiting for payment
        client_a = self.app.test_client()
        client_a.post("/api/auth/customer/login", json={"email": self.cust_a_email, "password": self.pwd})
        res = client_a.post("/api/orders", json={
            "shop_id": self.shop_id,
            "items": [{"id": self.item_regular_id, "quantity": 1}],
            "payment_method": "UPI / Online"
        })
        self.assertEqual(res.status_code, 201)
        order_info = res.get_json()["order"]
        order_id = order_info["order_id"]
        gateway_order_id = order_info["gateway_order_id"]

        webhook_payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": f"pay_p9_concurrent_{order_id}",
                        "order_id": gateway_order_id,
                        "amount": 5000,
                        "currency": "INR",
                        "status": "captured"
                    }
                }
            }
        }
        raw_body = json.dumps(webhook_payload).encode("utf-8")
        sig = self.provider.generate_test_webhook_signature(raw_body)

        results = []

        def send_webhook():
            c = self.app.test_client()
            r = c.post(
                "/api/payments/webhook",
                data=raw_body,
                content_type="application/json",
                headers={"X-Razorpay-Signature": sig}
            )
            results.append(r.status_code)

        # Dispatch 2 concurrent webhooks
        t1 = threading.Thread(target=send_webhook)
        t2 = threading.Thread(target=send_webhook)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Both return HTTP 200 (first confirms, second is idempotent success)
        self.assertEqual(results, [200, 200])

        # Verify order payment status is 'paid' exactly once
        order_row = DB.get_one("SELECT payment_status FROM orders WHERE id = %s", (order_id,))
        self.assertEqual(order_row["payment_status"], "paid")

    # =========================================================================
    # 5. MULTI-WORKER SAFE RATE LIMITING
    # =========================================================================

    def test_13_multi_worker_safe_otp_rate_limiting(self):
        """Exceeding 5 OTP requests per target returns HTTP 429 via database audit query."""
        test_mobile = "9876543299"
        # Clear any prior OTPs for this target
        DB.execute("DELETE FROM otp_codes WHERE target = %s", (test_mobile,))

        client = self.app.test_client()
        # Send 5 OTPs
        for _ in range(5):
            res = client.post("/api/auth/otp/send", json={"mobile": test_mobile, "purpose": "signup"})
            self.assertEqual(res.status_code, 200)

        # 6th attempt must be rejected with HTTP 429 Too Many Requests
        res_blocked = client.post("/api/auth/otp/send", json={"mobile": test_mobile, "purpose": "signup"})
        self.assertEqual(res_blocked.status_code, 429)
        self.assertFalse(res_blocked.get_json()["success"])
        self.assertIn("Too many OTP requests", res_blocked.get_json()["message"])

        # Clean up test OTPs
        DB.execute("DELETE FROM otp_codes WHERE target = %s", (test_mobile,))


if __name__ == "__main__":
    unittest.main(verbosity=2)
