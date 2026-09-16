"""
Automated Test Suite for Phase 11 — Institutional Production Deployment & Live College Pilot.

Validates all 18 production verification criteria specified in Step 41:
1. Production Configuration & Secret Key Validation
2. Database Connectivity & ACID Transaction Isolation
3. Health Liveness Probe (/api/health)
4. Readiness Probe Outage Handling (/api/ready)
5. Customer & Vendor Authentication
6. Role-Based Access Control (RBAC) & Boundary Checks
7. Shop Access & Stall Status Isolation
8. Menu Catalog & Authoritative Pricing Integrity
9. AI Recommendation Meal-Slot Integration
10. Notification Delivery & Unread Counter Tracking
11. Order Lifecycle & Counter OTP Verification
12. Payment Gateway Integration & Paise Calculation
13. Webhook Idempotency & Tampering Rejection
14. Stock Safety & Multi-Threaded Concurrency
15. Global Sanitized Error Handling
16. Production Security Headers & HSTS
17. CORS Origin Whitelisting & Wildcard Stripping
18. Secret Protection & Credential Non-Exposure
"""

import os
import sys
import json
import time
import sqlite3
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
os.environ["SECRET_KEY"] = "phase11-institutional-test-key-32b-ok"
os.environ["PAYMENT_PROVIDER"] = "razorpay"
os.environ["PAYMENT_ENVIRONMENT"] = "test"
os.environ["RAZORPAY_KEY_ID"] = "rzp_test_collegefoodcourt2026"
os.environ["RAZORPAY_KEY_SECRET"] = "rzp_sec_kpriet_dev_secret_key_32b"
os.environ["RAZORPAY_WEBHOOK_SECRET"] = "rzp_wh_sec_kpriet_webhook_32b_key"

import init_db
init_db.init_sqlite()

from app import app
from db import DB, is_production, DatabaseConnectionError
from config import get_config, ProductionConfig, TestingConfig
from werkzeug.security import generate_password_hash
from services.payment_provider import get_payment_provider


class TestPhase11Production(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

        # Clean slate strictly scoped to Phase 11 test entities
        DB.execute("DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE order_reference LIKE 'P11-%')")
        DB.execute("DELETE FROM payments WHERE order_id IN (SELECT id FROM orders WHERE order_reference LIKE 'P11-%')")
        DB.execute("DELETE FROM orders WHERE order_reference LIKE 'P11-%'")
        DB.execute("DELETE FROM menu_items WHERE shop_id IN (SELECT id FROM shops WHERE slug LIKE '%phase11%')")
        DB.execute("DELETE FROM shops WHERE slug LIKE '%phase11%'")
        DB.execute("DELETE FROM customer_profiles WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@pilot11.kpriet.ac.in')")
        DB.execute("DELETE FROM users WHERE email LIKE '%@pilot11.kpriet.ac.in'")

        cls.pwd = "InstitutionalSecure!2026"
        cls.hashed = generate_password_hash(cls.pwd)
        cls.provider = get_payment_provider()

        # Dedicated Stall for Concurrency Test (keeps seeded YPR and German Cafe untouched)
        cls.concurrency_vendor_email = "vendor.phase11@pilot11.kpriet.ac.in"
        cls.concurrency_vendor_id = DB.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'vendor', 1)",
            (cls.concurrency_vendor_email, cls.hashed)
        )
        cls.concurrency_shop_id = DB.execute(
            "INSERT INTO shops (name, slug, description, category, operational_status, is_active, owner_user_id) "
            "VALUES ('Phase 11 Pilot Stall', 'phase11-stall', 'Phase 11 Concurrency Stall', 'Snacks', 'OPEN', 1, %s)",
            (cls.concurrency_vendor_id,)
        )
        cls.item_limited_id = DB.execute(
            "INSERT INTO menu_items (shop_id, name, price, category, quantity, is_available) VALUES (%s, %s, %s, %s, 1, 1)",
            (cls.concurrency_shop_id, "Phase 11 Limited Sweet (Last 1)", 45.00, "Sweets")
        )

        # Register Pilot Personas for Phase 11
        cls.student_email = "student.p11@pilot11.kpriet.ac.in"
        cls.student_id = DB.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
            (cls.student_email, cls.hashed)
        )
        DB.execute(
            """
            INSERT INTO customer_profiles (user_id, customer_type, full_name, identifier, mobile, wallet_balance)
            VALUES (%s, 'student', 'Arjun Kumar', '22CS042', '9876543281', 500.00)
            """,
            (cls.student_id,)
        )

        cls.faculty_email = "faculty.p11@pilot11.kpriet.ac.in"
        cls.faculty_id = DB.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
            (cls.faculty_email, cls.hashed)
        )
        DB.execute(
            """
            INSERT INTO customer_profiles (user_id, customer_type, full_name, identifier, mobile, wallet_balance)
            VALUES (%s, 'faculty', 'Dr. Ramesh Babu', 'KPR-FAC-014', '9876543282', 1000.00)
            """,
            (cls.faculty_id,)
        )

    @classmethod
    def tearDownClass(cls):
        try:
            DB.execute("DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE order_reference LIKE 'P11-%')")
            DB.execute("DELETE FROM payments WHERE order_id IN (SELECT id FROM orders WHERE order_reference LIKE 'P11-%')")
            DB.execute("DELETE FROM orders WHERE order_reference LIKE 'P11-%'")
            DB.execute("DELETE FROM menu_items WHERE shop_id IN (SELECT id FROM shops WHERE slug LIKE '%phase11%')")
            DB.execute("DELETE FROM shops WHERE slug LIKE '%phase11%'")
            DB.execute("DELETE FROM customer_profiles WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@pilot11.kpriet.ac.in')")
            DB.execute("DELETE FROM users WHERE email LIKE '%@pilot11.kpriet.ac.in'")
        except Exception:
            pass

    # =========================================================================
    # 1. PRODUCTION CONFIGURATION & SECRET KEY VALIDATION
    # =========================================================================

    def test_01_production_config_requires_secret_key(self):
        """Verify production configuration strictly refuses to boot if SECRET_KEY is missing or weak."""
        with patch.dict(os.environ, {"SECRET_KEY": "", "FLASK_ENV": "production"}):
            with self.assertRaises(RuntimeError) as ctx:
                ProductionConfig()
            self.assertIn("SECRET_KEY", str(ctx.exception))

        with patch.dict(os.environ, {"SECRET_KEY": "dev-insecure-secret-key", "FLASK_ENV": "production"}):
            with self.assertRaises(RuntimeError) as ctx:
                ProductionConfig()
            self.assertIn("insecure", str(ctx.exception).lower())

    # =========================================================================
    # 2. DATABASE CONNECTIVITY & ACID TRANSACTIONS
    # =========================================================================

    def test_02_database_connectivity_and_acid_rollback(self):
        """Verify ACID transactions rollback completely on exceptions."""
        initial_user_count = DB.get_one("SELECT COUNT(*) as cnt FROM users")["cnt"]

        try:
            with DB.transaction() as tx:
                tx.execute(
                    "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
                    ("rollback.test@pilot11.kpriet.ac.in", self.hashed)
                )
                # Intentional error to trigger rollback
                raise RuntimeError("Simulated transaction failure")
        except RuntimeError:
            pass

        after_count = DB.get_one("SELECT COUNT(*) as cnt FROM users")["cnt"]
        self.assertEqual(initial_user_count, after_count, "Rollback failed: orphaned record persisted.")

    # =========================================================================
    # 3. HEALTH LIVENESS PROBE
    # =========================================================================

    def test_03_health_liveness_probe_operational(self):
        """Verify GET /api/health returns HTTP 200 with service metadata and zero exposed secrets."""
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "food-court-api")
        self.assertIn("version", data)
        self.assertNotIn("password", str(data).lower())
        self.assertNotIn("secret", str(data).lower())

    # =========================================================================
    # 4. READINESS PROBE OUTAGE HANDLING
    # =========================================================================

    def test_04_readiness_probe_database_dependency(self):
        """Verify GET /api/ready returns HTTP 200 when database is healthy, HTTP 503 during outage."""
        res = self.client.get("/api/ready")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "ready")
        self.assertEqual(data["database"], "connected")

        # Simulate database failure
        with patch.object(DB, "get_one", side_effect=Exception("DB Down")):
            down_res = self.client.get("/api/ready")
            self.assertEqual(down_res.status_code, 503)
            down_data = down_res.get_json()
            self.assertEqual(down_data["status"], "not_ready")

    # =========================================================================
    # 5. CUSTOMER & VENDOR AUTHENTICATION
    # =========================================================================

    def test_05_customer_and_vendor_authentication(self):
        """Verify customer and vendor login workflows."""
        # Customer login
        c_res = self.client.post("/api/auth/customer/login", json={
            "email": self.student_email,
            "password": self.pwd,
            "customerType": "student"
        })
        self.assertEqual(c_res.status_code, 200)
        c_data = c_res.get_json()
        self.assertTrue(c_data["success"])
        self.assertEqual(c_data["user"]["email"], self.student_email)

        # Vendor login (YPR)
        v_res = self.client.post("/api/auth/vendor/login", json={
            "email": "ypr@kpriet.ac.in",
            "password": "vendor123"
        })
        self.assertEqual(v_res.status_code, 200)
        v_data = v_res.get_json()
        self.assertTrue(v_data["success"])
        self.assertEqual(v_data["user"]["role"], "vendor")

    # =========================================================================
    # 6. ROLE-BASED ACCESS CONTROL (RBAC)
    # =========================================================================

    def test_06_role_based_access_control_isolation(self):
        """Verify customer cannot access vendor or admin endpoints."""
        # Authenticate as student
        self.client.post("/api/auth/customer/login", json={
            "email": self.student_email,
            "password": self.pwd,
            "customerType": "student"
        })

        # Customer attempting vendor kitchen queue -> HTTP 403
        v_queue = self.client.get("/api/vendor/orders")
        self.assertEqual(v_queue.status_code, 403)

        # Customer attempting admin analytics -> HTTP 403
        adm_res = self.client.get("/api/admin/overview")
        self.assertEqual(adm_res.status_code, 403)

    # =========================================================================
    # 7. SHOP ACCESS & STALL STATUS ISOLATION
    # =========================================================================

    def test_07_shop_access_and_stall_status(self):
        """Verify active shops directory and operational status filtering."""
        res = self.client.get("/api/shops")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("shops", data)
        self.assertGreaterEqual(len(data["shops"]), 2)

        # Verify YPR stall is present and OPEN
        ypr = next((s for s in data["shops"] if s["id"] == 1), None)
        self.assertIsNotNone(ypr)
        self.assertEqual(ypr["operational_status"], "OPEN")

    # =========================================================================
    # 8. MENU CATALOG & AUTHORITATIVE PRICING INTEGRITY
    # =========================================================================

    def test_08_menu_catalog_and_price_tampering_defense(self):
        """Verify client-submitted prices in order payloads are completely ignored; DB is authoritative."""
        self.client.post("/api/auth/customer/login", json={
            "email": self.student_email,
            "password": self.pwd,
            "customerType": "student"
        })

        item = DB.get_one("SELECT * FROM menu_items WHERE shop_id = 1 AND is_available = 1 AND quantity >= 2")
        self.assertIsNotNone(item)
        expected_total = float(item["price"]) * 1

        # Attempt to tamper price to ₹1.00
        tampered_order = {
            "items": [{"id": item["id"], "quantity": 1, "price": 1.00}],
            "payment_method": "Pay at Counter"
        }
        res = self.client.post("/api/orders", json=tampered_order)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertEqual(float(data["order"]["total_amount"]), expected_total)

    # =========================================================================
    # 9. AI RECOMMENDATION MEAL-SLOT INTEGRATION
    # =========================================================================

    def test_09_ai_recommendations_context_integration(self):
        """Verify AI recommendation endpoint returns meal slot and availability-filtered items."""
        res = self.client.get("/api/recommendations")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success", True))
        self.assertIn("recommendations", data)
        self.assertIn("slot", data)

    # =========================================================================
    # 10. NOTIFICATION DELIVERY & UNREAD TRACKING
    # =========================================================================

    def test_10_notification_delivery_and_unread_tracking(self):
        """Verify customer receives notifications and can check unread counts."""
        self.client.post("/api/auth/customer/login", json={
            "email": self.student_email,
            "password": self.pwd,
            "customerType": "student"
        })

        res = self.client.get("/api/notifications")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("notifications", data)

        count_res = self.client.get("/api/notifications/unread-count")
        self.assertEqual(count_res.status_code, 200)
        self.assertIn("unread_count", count_res.get_json())

    # =========================================================================
    # 11. ORDER LIFECYCLE & COUNTER OTP VERIFICATION
    # =========================================================================

    def test_11_order_lifecycle_and_counter_otp(self):
        """Test complete order progression: PLACED -> PREPARING -> READY -> OTP VERIFIED -> COMPLETED."""
        # 1. Customer places order
        self.client.post("/api/auth/customer/login", json={
            "email": self.student_email,
            "password": self.pwd,
            "customerType": "student"
        })
        item = DB.get_one("SELECT * FROM menu_items WHERE shop_id = 1 AND is_available = 1 AND quantity >= 2")

        order_res = self.client.post("/api/orders", json={
            "items": [{"id": item["id"], "quantity": 1}],
            "payment_method": "Pay at Counter"
        })
        self.assertEqual(order_res.status_code, 201)
        order_obj = order_res.get_json()["order"]
        order_id = order_obj["order_id"]
        pickup_otp = order_obj["pickup_otp"]

        # 2. Vendor logs in and advances status
        self.client.post("/api/auth/vendor/login", json={"email": "ypr@kpriet.ac.in", "password": "vendor123"})
        self.client.put(f"/api/orders/{order_id}/status", json={"status": "preparing"})
        self.client.put(f"/api/orders/{order_id}/status", json={"status": "ready"})

        # 3. Vendor verifies counter OTP
        otp_res = self.client.post("/api/orders/verify-otp", json={"otp": pickup_otp})
        self.assertEqual(otp_res.status_code, 200)
        self.assertTrue(otp_res.get_json()["success"])

        # 4. Assert order completed
        order_db = DB.get_one("SELECT order_status, completed_time FROM orders WHERE id = %s", (order_id,))
        self.assertEqual(order_db["order_status"], "completed")
        self.assertIsNotNone(order_db["completed_time"])

    # =========================================================================
    # 12. PAYMENT GATEWAY INTEGRATION & PAISE CALCULATION
    # =========================================================================

    def test_12_payment_gateway_paise_calculation(self):
        """Verify Razorpay payment order generates authoritative amount_paise (₹1 = 100 paise)."""
        self.client.post("/api/auth/customer/login", json={
            "email": self.student_email,
            "password": self.pwd,
            "customerType": "student"
        })
        item = DB.get_one("SELECT * FROM menu_items WHERE shop_id = 1 AND is_available = 1")

        order_res = self.client.post("/api/orders", json={
            "items": [{"id": item["id"], "quantity": 2}],
            "payment_method": "UPI / Online"
        })
        self.assertEqual(order_res.status_code, 201)
        order_obj = order_res.get_json()["order"]
        expected_paise = int(round(float(item["price"]) * 2 * 100))
        self.assertEqual(order_obj["amount_paise"], expected_paise)
        self.assertTrue(order_obj["gateway_order_id"].startswith("order_"))

    # =========================================================================
    # 13. WEBHOOK IDEMPOTENCY & TAMPERING REJECTION
    # =========================================================================

    def test_13_webhook_idempotency_and_tampering_rejection(self):
        """Verify webhook accepts valid HMAC signatures, rejects invalid ones, and handles duplicate replays."""
        self.client.post("/api/auth/customer/login", json={
            "email": self.student_email,
            "password": self.pwd,
            "customerType": "student"
        })
        item = DB.get_one("SELECT * FROM menu_items WHERE shop_id = 1 AND is_available = 1")

        order_res = self.client.post("/api/orders", json={
            "items": [{"id": item["id"], "quantity": 1}],
            "payment_method": "UPI / Online"
        })
        order_obj = order_res.get_json()["order"]
        rzp_order_id = order_obj["gateway_order_id"]
        mock_pid = f"pay_p11_wh_{int(time.time())}"

        wh_payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": mock_pid,
                        "order_id": rzp_order_id,
                        "amount": int(round(float(item["price"]) * 100)),
                        "status": "captured"
                    }
                }
            }
        }
        raw_body = json.dumps(wh_payload).encode("utf-8")
        valid_sig = self.provider.generate_test_webhook_signature(raw_body)

        # 1. Invalid signature -> 400
        bad_res = self.client.post(
            "/api/payments/webhook",
            data=raw_body,
            headers={"X-Razorpay-Signature": "tampered_signature", "Content-Type": "application/json"}
        )
        self.assertEqual(bad_res.status_code, 400)

        # 2. Valid signature -> 200
        good_res = self.client.post(
            "/api/payments/webhook",
            data=raw_body,
            headers={"X-Razorpay-Signature": valid_sig, "Content-Type": "application/json"}
        )
        self.assertEqual(good_res.status_code, 200)

        # 3. Duplicate replay -> 200 (idempotent)
        replay_res = self.client.post(
            "/api/payments/webhook",
            data=raw_body,
            headers={"X-Razorpay-Signature": valid_sig, "Content-Type": "application/json"}
        )
        self.assertEqual(replay_res.status_code, 200)

    # =========================================================================
    # 14. STOCK SAFETY & MULTI-THREADED CONCURRENCY
    # =========================================================================

    def test_14_stock_concurrency_race_condition(self):
        """Two concurrent customers race to purchase the last unit (Stock=1). Exactly 1 succeeds."""
        u1 = DB.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
            ("p11.race1@pilot11.kpriet.ac.in", self.hashed)
        )
        DB.execute(
            "INSERT INTO customer_profiles (user_id, customer_type, full_name, identifier, mobile, wallet_balance) "
            "VALUES (%s, 'student', 'Race 1', 'KPR-R1', '9876543291', 500.00)",
            (u1,)
        )
        u2 = DB.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
            ("p11.race2@pilot11.kpriet.ac.in", self.hashed)
        )
        DB.execute(
            "INSERT INTO customer_profiles (user_id, customer_type, full_name, identifier, mobile, wallet_balance) "
            "VALUES (%s, 'student', 'Race 2', 'KPR-R2', '9876543292', 500.00)",
            (u2,)
        )

        c1 = self.app.test_client()
        c2 = self.app.test_client()
        c1.post("/api/auth/customer/login", json={"email": "p11.race1@pilot11.kpriet.ac.in", "password": self.pwd})
        c2.post("/api/auth/customer/login", json={"email": "p11.race2@pilot11.kpriet.ac.in", "password": self.pwd})

        statuses = []

        def place_order(cl):
            resp = cl.post(
                "/api/orders",
                json={
                    "items": [{"id": self.item_limited_id, "quantity": 1}],
                    "payment_method": "Pay at Counter"
                }
            )
            statuses.append(resp.status_code)

        t1 = threading.Thread(target=place_order, args=(c1,))
        t2 = threading.Thread(target=place_order, args=(c2,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(sorted(statuses), [201, 400])
        final_stock = DB.get_one("SELECT quantity FROM menu_items WHERE id = %s", (self.item_limited_id,))["quantity"]
        self.assertEqual(final_stock, 0)

    # =========================================================================
    # 15. GLOBAL SANITIZED ERROR HANDLING
    # =========================================================================

    def test_15_global_sanitized_error_handling(self):
        """Verify 400, 404, and 405 error handlers return sanitized JSON without exposing stack traces."""
        res404 = self.client.get("/api/non-existent-p11-endpoint")
        self.assertEqual(res404.status_code, 404)
        data404 = res404.get_json()
        self.assertFalse(data404.get("success", True))
        self.assertIn("message", data404)
        self.assertNotIn("Traceback", str(res404.data))

        res405 = self.client.post("/api/health")
        self.assertEqual(res405.status_code, 405)
        data405 = res405.get_json()
        self.assertFalse(data405.get("success", True))
        self.assertNotIn("Traceback", str(res405.data))

    # =========================================================================
    # 16. PRODUCTION SECURITY HEADERS & HSTS
    # =========================================================================

    def test_16_production_security_headers_present(self):
        """Verify production security headers on HTTP and HSTS over HTTPS."""
        res = self.client.get("/api/health")
        self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res.headers.get("X-Frame-Options"), "SAMEORIGIN")
        self.assertEqual(res.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")

        # HSTS is attached over secure/HTTPS connections or in production mode
        https_res = self.client.get("/api/health", base_url="https://localhost")
        self.assertIn("max-age=", https_res.headers.get("Strict-Transport-Security", ""))

    # =========================================================================
    # 17. CORS ORIGIN WHITELISTS
    # =========================================================================

    def test_17_cors_origin_whitelisting(self):
        """Verify production configuration strips wildcard '*' when credentials are used."""
        with patch.dict(os.environ, {"CORS_ORIGINS": "https://foodcourt.kpriet.ac.in, *"}):
            origins = ProductionConfig.get_cors_origins()
            self.assertNotIn("*", origins)
            self.assertIn("https://foodcourt.kpriet.ac.in", origins)

    # =========================================================================
    # 18. SECRET PROTECTION & NON-EXPOSURE
    # =========================================================================

    def test_18_secret_protection_in_responses(self):
        """Verify private keys, passwords, and webhook secrets are never exposed in responses."""
        res = self.client.get("/")
        self.assertNotIn("rzp_sec", str(res.data))
        self.assertNotIn("rzp_wh_sec", str(res.data))
        self.assertNotIn("password_hash", str(res.data))


if __name__ == "__main__":
    unittest.main()
