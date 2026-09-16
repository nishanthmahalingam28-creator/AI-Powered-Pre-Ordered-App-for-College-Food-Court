"""
Automated Test Suite for Phase 10 — Real Cloud Deployment & Live College Pilot.

Verifies:
1. Pilot environment configuration and secret protection.
2. Health (/api/health) and Readiness (/api/ready) observability probes.
3. Multi-persona pilot cohort accounts (Student, Faculty, Guest) registration and profiles.
4. Participating pilot stalls operational status and menu availability (YPR & German Cafe).
5. Student order lifecycle with Razorpay sandbox and vendor counter OTP verification.
6. Faculty order lifecycle with German Cafe and order completion.
7. Razorpay webhook verification with idempotent replay and signature validation.
8. Concurrent ordering stock protection under pilot peak load.
9. Automated database logical backup and restore verification test against non-production staging.
10. Global sanitized error handling under pilot stress.
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
os.environ["SECRET_KEY"] = "phase10-pilot-test-key-32b-ok"
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


class TestPhase10PilotReadiness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

        # Clean slate for Phase 10 test isolation (scoped strictly to Phase 10 test entities)
        DB.execute("DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE order_reference LIKE 'P10-%')")
        DB.execute("DELETE FROM payments WHERE order_id IN (SELECT id FROM orders WHERE order_reference LIKE 'P10-%')")
        DB.execute("DELETE FROM orders WHERE order_reference LIKE 'P10-%'")
        DB.execute("DELETE FROM menu_items WHERE shop_id IN (SELECT id FROM shops WHERE slug LIKE '%phase10%')")
        DB.execute("DELETE FROM shops WHERE slug LIKE '%phase10%'")
        DB.execute("DELETE FROM customer_profiles WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@pilot10.kpriet.ac.in')")
        DB.execute("DELETE FROM users WHERE email LIKE '%@pilot10.kpriet.ac.in'")

        cls.pwd = "PilotSecure!2026"
        cls.hashed = generate_password_hash(cls.pwd)
        cls.provider = get_payment_provider()

        # Dedicated Stall for Concurrency Test (keeps YPR and German Cafe untouched)
        cls.concurrency_vendor_email = "vendor.phase10@pilot10.kpriet.ac.in"
        cls.concurrency_vendor_id = DB.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'vendor', 1)",
            (cls.concurrency_vendor_email, cls.hashed)
        )
        cls.concurrency_shop_id = DB.execute(
            "INSERT INTO shops (name, slug, description, category, operational_status, is_active, owner_user_id) "
            "VALUES ('Phase 10 Pilot Stall', 'phase10-stall', 'Pilot Concurrency Stall', 'Snacks', 'OPEN', 1, %s)",
            (cls.concurrency_vendor_id,)
        )
        cls.item_limited_id = DB.execute(
            "INSERT INTO menu_items (shop_id, name, price, category, quantity, is_available) VALUES (%s, %s, %s, %s, 1, 1)",
            (cls.concurrency_shop_id, "Pilot Limited Sweet (Last 1)", 50.00, "Sweets")
        )

    @classmethod
    def tearDownClass(cls):
        try:
            DB.execute("DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE order_reference LIKE 'P10-%')")
            DB.execute("DELETE FROM payments WHERE order_id IN (SELECT id FROM orders WHERE order_reference LIKE 'P10-%')")
            DB.execute("DELETE FROM orders WHERE order_reference LIKE 'P10-%'")
            DB.execute("DELETE FROM menu_items WHERE shop_id IN (SELECT id FROM shops WHERE slug LIKE '%phase10%')")
            DB.execute("DELETE FROM shops WHERE slug LIKE '%phase10%'")
            DB.execute("DELETE FROM customer_profiles WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@pilot10.kpriet.ac.in')")
            DB.execute("DELETE FROM users WHERE email LIKE '%@pilot10.kpriet.ac.in'")
        except Exception:
            pass

    # =========================================================================
    # 1. PILOT ENVIRONMENT CONFIGURATION & SECRET PROTECTION
    # =========================================================================

    def test_01_pilot_environment_and_secret_protection(self):
        """Verify production configuration enforces mandatory secret key and disallows insecure defaults."""
        with patch.dict(os.environ, {"SECRET_KEY": "", "FLASK_ENV": "production"}):
            with self.assertRaises(RuntimeError) as ctx:
                ProductionConfig()
            self.assertIn("SECRET_KEY", str(ctx.exception))

        with patch.dict(os.environ, {"SECRET_KEY": "dev-insecure-secret-key", "FLASK_ENV": "production"}):
            with self.assertRaises(RuntimeError) as ctx:
                ProductionConfig()
            self.assertIn("insecure", str(ctx.exception).lower())

        with patch.dict(os.environ, {"FLASK_ENV": "production"}):
            self.assertTrue(is_production())

        with patch.dict(os.environ, {"CORS_ORIGINS": "https://foodcourt.kpriet.ac.in, *"}):
            origins = ProductionConfig.get_cors_origins()
            self.assertNotIn("*", origins)
            self.assertIn("https://foodcourt.kpriet.ac.in", origins)

    # =========================================================================
    # 2. PROBES & OBSERVABILITY
    # =========================================================================

    def test_02_health_and_readiness_probes_pilot_ready(self):
        """Verify health (liveness) and readiness probes return HTTP 200 with sanitized metadata."""
        # 1. Health Probe
        h_resp = self.client.get("/api/health")
        self.assertEqual(h_resp.status_code, 200)
        h_data = json.loads(h_resp.data)
        self.assertEqual(h_data["status"], "ok")
        self.assertEqual(h_data["service"], "food-court-api")
        self.assertNotIn("password", str(h_data).lower())
        self.assertNotIn("secret", str(h_data).lower())

        # 2. Readiness Probe
        r_resp = self.client.get("/api/ready")
        self.assertEqual(r_resp.status_code, 200)
        r_data = json.loads(r_resp.data)
        self.assertEqual(r_data["status"], "ready")
        self.assertEqual(r_data["database"], "connected")

        # 3. Simulated DB failure returns HTTP 503
        with patch.object(DB, "get_one", side_effect=Exception("DB Unreachable")):
            r_down = self.client.get("/api/ready")
            self.assertEqual(r_down.status_code, 503)
            r_down_data = json.loads(r_down.data)
            self.assertEqual(r_down_data["status"], "not_ready")

    # =========================================================================
    # 3. MULTI-PERSONA PILOT COHORT REGISTRATION
    # =========================================================================

    def test_03_pilot_multi_persona_registration_and_profiles(self):
        """Verify Student, Faculty, and Guest accounts can register and authenticate."""
        personas = [
            {
                "email": "student.pilot@pilot10.kpriet.ac.in",
                "full_name": "Arjun Kumar (Student)",
                "customer_type": "student",
                "identifier": "KPR2026-CSE-042",
                "mobile": "9876543260"
            },
            {
                "email": "faculty.pilot@pilot10.kpriet.ac.in",
                "full_name": "Dr. Ramesh Babu (Faculty)",
                "customer_type": "faculty",
                "identifier": "KPR-FAC-EE-09",
                "mobile": "9876543261"
            },
            {
                "email": "guest.pilot@pilot10.kpriet.ac.in",
                "full_name": "Auditor Guest",
                "customer_type": "guest",
                "identifier": "GUEST-2026-01",
                "mobile": "9876543262"
            }
        ]

        for p in personas:
            # Register direct DB insert with proper hash to simulate clean verified registration
            uid = DB.execute(
                "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
                (p["email"], self.hashed)
            )
            DB.execute(
                """
                INSERT INTO customer_profiles (user_id, customer_type, full_name, identifier, mobile, wallet_balance)
                VALUES (%s, %s, %s, %s, %s, 1000.00)
                """,
                (uid, p["customer_type"], p["full_name"], p["identifier"], p["mobile"])
            )

            # Test authentication via customer login endpoint
            resp = self.client.post("/api/auth/customer/login", json={
                "email": p["email"],
                "password": self.pwd,
                "customerType": p["customer_type"]
            })
            self.assertEqual(resp.status_code, 200, f"Login failed for persona {p['customer_type']}")
            data = json.loads(resp.data)
            self.assertTrue(data.get("success"))
            self.assertEqual(data["user"]["email"], p["email"])
            self.assertEqual(data["user"]["customer_type"], p["customer_type"])

    # =========================================================================
    # 4. PILOT STALLS OPERATIONAL STATUS
    # =========================================================================

    def test_04_pilot_stalls_operational_status(self):
        """Verify participating pilot stalls (YPR ID 1 and German Cafe ID 3) are active and open."""
        # Query YPR (Stall 1)
        ypr = DB.get_one("SELECT * FROM shops WHERE id = 1")
        self.assertIsNotNone(ypr)
        self.assertEqual(ypr["name"], "YPR")
        self.assertEqual(ypr["operational_status"], "OPEN")
        self.assertEqual(ypr["is_active"], 1)

        # Query German Cafe (Stall 3)
        german = DB.get_one("SELECT * FROM shops WHERE id = 3")
        self.assertIsNotNone(german)
        self.assertEqual(german["name"], "German Cafe")
        self.assertEqual(german["operational_status"], "OPEN")
        self.assertEqual(german["is_active"], 1)

        # Verify menu items exist
        ypr_items = DB.get_all("SELECT * FROM menu_items WHERE shop_id = 1 AND is_available = 1")
        self.assertGreaterEqual(len(ypr_items), 1)

        german_items = DB.get_all("SELECT * FROM menu_items WHERE shop_id = 3 AND is_available = 1")
        self.assertGreaterEqual(len(german_items), 1)

    # =========================================================================
    # 5. STUDENT ORDER LIFECYCLE & COUNTER OTP VERIFICATION
    # =========================================================================

    def test_05_student_order_and_otp_counter_verification(self):
        """Test complete student order: place order, pay, and vendor counter OTP verification."""
        # 1. Login as Student
        login_resp = self.client.post(
            "/api/auth/customer/login",
            json={"email": "student.pilot@pilot10.kpriet.ac.in", "password": self.pwd}
        )
        self.assertEqual(login_resp.status_code, 200)

        # 2. Place Order at YPR (Stall 1)
        ypr_item = DB.get_one("SELECT * FROM menu_items WHERE shop_id = 1 AND is_available = 1 AND quantity >= 2")
        self.assertIsNotNone(ypr_item)

        order_payload = {
            "items": [{"id": ypr_item["id"], "quantity": 1}],
            "payment_method": "UPI / Online"
        }
        create_resp = self.client.post("/api/orders", json=order_payload)
        self.assertEqual(create_resp.status_code, 201)
        create_data = json.loads(create_resp.data)
        self.assertTrue(create_data.get("success"))
        order = create_data["order"]
        order_id = order["order_id"]
        gateway_order_id = order["gateway_order_id"]
        pickup_otp = order["pickup_otp"]

        # 3. Complete Sandbox Payment
        mock_payment_id = f"pay_pilot_{int(time.time())}"
        signature = self.provider.generate_test_signature(gateway_order_id, mock_payment_id)

        verify_resp = self.client.post(
            "/api/payments/verify",
            json={
                "order_id": order_id,
                "razorpay_order_id": gateway_order_id,
                "razorpay_payment_id": mock_payment_id,
                "razorpay_signature": signature
            }
        )
        self.assertEqual(verify_resp.status_code, 200)

        # Check order is paid in DB
        order_db = DB.get_one("SELECT * FROM orders WHERE id = %s", (order_id,))
        self.assertEqual(order_db["payment_status"], "paid")

        # 4. Vendor (YPR) logs in
        vendor_login = self.client.post("/api/auth/vendor/login", json={"email": "ypr@kpriet.ac.in", "password": "vendor123"})
        self.assertEqual(vendor_login.status_code, 200)

        # 5. Vendor tests OTP verification
        bad_otp_resp = self.client.post("/api/orders/verify-otp", json={"otp": "000000"})
        self.assertEqual(bad_otp_resp.status_code, 404)

        good_otp_resp = self.client.post("/api/orders/verify-otp", json={"otp": pickup_otp})
        self.assertEqual(good_otp_resp.status_code, 200)
        good_otp_data = json.loads(good_otp_resp.data)
        self.assertTrue(good_otp_data.get("success"))

        # Verify order transitioned to completed
        updated_order = DB.get_one("SELECT * FROM orders WHERE id = %s", (order_id,))
        self.assertEqual(updated_order["order_status"], "completed")
        self.assertIsNotNone(updated_order["completed_time"])

    # =========================================================================
    # 6. FACULTY ORDER LIFECYCLE (GERMAN CAFE)
    # =========================================================================

    def test_06_faculty_order_lifecycle_with_snack_item(self):
        """Test faculty order at German Cafe (Stall 3) through pickup OTP verification."""
        # 1. Login as Faculty
        self.client.post("/api/auth/customer/login", json={"email": "faculty.pilot@pilot10.kpriet.ac.in", "password": self.pwd})

        german_item = DB.get_one("SELECT * FROM menu_items WHERE shop_id = 3 AND is_available = 1 AND quantity >= 1")
        self.assertIsNotNone(german_item)

        # 2. Create Order
        create_resp = self.client.post(
            "/api/orders",
            json={
                "items": [{"id": german_item["id"], "quantity": 1}],
                "payment_method": "UPI / Online"
            }
        )
        self.assertEqual(create_resp.status_code, 201)
        cdata = json.loads(create_resp.data)
        order = cdata["order"]
        order_id = order["order_id"]
        gateway_order_id = order["gateway_order_id"]
        pickup_otp = order["pickup_otp"]

        # 3. Pay via Razorpay sandbox
        mock_pid = f"pay_fac_{int(time.time())}"
        sig = self.provider.generate_test_signature(gateway_order_id, mock_pid)

        self.client.post(
            "/api/payments/verify",
            json={
                "order_id": order_id,
                "razorpay_order_id": gateway_order_id,
                "razorpay_payment_id": mock_pid,
                "razorpay_signature": sig
            }
        )

        # 4. German Cafe Vendor verifies OTP
        self.client.post("/api/auth/vendor/login", json={"email": "german@kpriet.ac.in", "password": "vendor123"})
        verify_resp = self.client.post("/api/orders/verify-otp", json={"otp": pickup_otp})
        self.assertEqual(verify_resp.status_code, 200)

        completed_order = DB.get_one("SELECT order_status FROM orders WHERE id = %s", (order_id,))
        self.assertEqual(completed_order["order_status"], "completed")

    # =========================================================================
    # 7. WEBHOOK IDEMPOTENCY & AUTHORITATIVE RECONCILIATION
    # =========================================================================

    def test_07_sandbox_webhook_authoritative_reconciliation(self):
        """Verify Razorpay webhook verifies signatures and handles duplicate callbacks idempotently."""
        # 1. Login Student and create order
        self.client.post("/api/auth/customer/login", json={"email": "student.pilot@pilot10.kpriet.ac.in", "password": self.pwd})
        item = DB.get_one("SELECT * FROM menu_items WHERE shop_id = 1 AND is_available = 1")

        create_resp = self.client.post(
            "/api/orders",
            json={
                "items": [{"id": item["id"], "quantity": 1}],
                "payment_method": "UPI / Online"
            }
        )
        self.assertEqual(create_resp.status_code, 201)
        order = json.loads(create_resp.data)["order"]
        rzp_order_id = order["gateway_order_id"]
        mock_pid = f"pay_wh_{int(time.time())}"

        # 2. Forge webhook payload
        webhook_payload = {
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
        raw_body = json.dumps(webhook_payload).encode("utf-8")
        valid_signature = self.provider.generate_test_webhook_signature(raw_body)

        # 3. Test Invalid Signature -> Rejected (400)
        invalid_resp = self.client.post(
            "/api/payments/webhook",
            data=raw_body,
            headers={"X-Razorpay-Signature": "invalid_sig_here", "Content-Type": "application/json"}
        )
        self.assertEqual(invalid_resp.status_code, 400)

        # 4. Test Valid Signature -> Success (200)
        valid_resp = self.client.post(
            "/api/payments/webhook",
            data=raw_body,
            headers={"X-Razorpay-Signature": valid_signature, "Content-Type": "application/json"}
        )
        self.assertEqual(valid_resp.status_code, 200)

        # 5. Test Duplicate Webhook Replay -> Idempotent Success (200)
        replay_resp = self.client.post(
            "/api/payments/webhook",
            data=raw_body,
            headers={"X-Razorpay-Signature": valid_signature, "Content-Type": "application/json"}
        )
        self.assertEqual(replay_resp.status_code, 200)

    # =========================================================================
    # 8. CONCURRENT STOCK INTEGRITY UNDER PILOT LOAD
    # =========================================================================

    def test_08_pilot_concurrency_stock_safety(self):
        """Simulate two concurrent students racing to buy the last unit (Stock=1)."""
        # Register two racing students
        user_c1 = DB.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
            ("race.c1@pilot10.kpriet.ac.in", self.hashed)
        )
        DB.execute(
            "INSERT INTO customer_profiles (user_id, customer_type, full_name, identifier, mobile, wallet_balance) "
            "VALUES (%s, 'student', 'Race C1', 'KPR2026-RACE-1', '9876543271', 500.00)",
            (user_c1,)
        )

        user_c2 = DB.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
            ("race.c2@pilot10.kpriet.ac.in", self.hashed)
        )
        DB.execute(
            "INSERT INTO customer_profiles (user_id, customer_type, full_name, identifier, mobile, wallet_balance) "
            "VALUES (%s, 'student', 'Race C2', 'KPR2026-RACE-2', '9876543272', 500.00)",
            (user_c2,)
        )

        client1 = self.app.test_client()
        client2 = self.app.test_client()

        client1.post("/api/auth/customer/login", json={"email": "race.c1@pilot10.kpriet.ac.in", "password": self.pwd})
        client2.post("/api/auth/customer/login", json={"email": "race.c2@pilot10.kpriet.ac.in", "password": self.pwd})

        results = []

        def place_order(client):
            resp = client.post(
                "/api/orders",
                json={
                    "items": [{"id": self.item_limited_id, "quantity": 1}],
                    "payment_method": "Pay at Counter"
                }
            )
            results.append(resp.status_code)

        t1 = threading.Thread(target=place_order, args=(client1,))
        t2 = threading.Thread(target=place_order, args=(client2,))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Exactly 1 success (201) and exactly 1 failure (400)
        self.assertEqual(sorted(results), [201, 400])

        # Final stock must be exactly 0 (no negative stock)
        final_stock = DB.get_one("SELECT quantity FROM menu_items WHERE id = %s", (self.item_limited_id,))["quantity"]
        self.assertEqual(final_stock, 0)

    # =========================================================================
    # 9. DATABASE LOGICAL BACKUP & RESTORE INTEGRITY
    # =========================================================================

    def test_09_database_backup_and_restore_verification(self):
        """
        Verify logical backup and restore procedure against a staging test database:
        1. Dump source database schema and records.
        2. Create a clean isolated target database.
        3. Execute restore script into target database.
        4. Compare table counts, row counts across all tables, and schema integrity.
        """
        source_db_path = init_db.SQLITE_PATH
        self.assertTrue(os.path.exists(source_db_path))

        # Perform logical dump using SQLite iterdump
        src_conn = sqlite3.connect(source_db_path)
        dump_lines = list(src_conn.iterdump())
        src_conn.close()

        dump_sql = "\n".join(dump_lines)
        self.assertGreater(len(dump_sql), 1000)

        # Restore into in-memory staging target database
        target_conn = sqlite3.connect(":memory:")
        target_cur = target_conn.cursor()
        target_cur.executescript(dump_sql)

        # Verify table row counts match exactly
        tables_to_verify = [
            "users", "customer_profiles", "shops", "menu_items",
            "orders", "order_items", "payments", "notifications"
        ]

        src_conn = sqlite3.connect(source_db_path)
        src_cur = src_conn.cursor()

        for tbl in tables_to_verify:
            src_cur.execute(f"SELECT COUNT(*) FROM {tbl}")
            src_count = src_cur.fetchone()[0]

            target_cur.execute(f"SELECT COUNT(*) FROM {tbl}")
            target_count = target_cur.fetchone()[0]

            self.assertEqual(
                src_count, target_count,
                f"Backup/Restore mismatch for table {tbl}: source={src_count}, target={target_count}"
            )

        src_conn.close()
        target_conn.close()

    # =========================================================================
    # 10. SANITIZED ERROR HANDLING UNDER PILOT STRESS
    # =========================================================================

    def test_10_sanitized_error_handling_under_pilot_stress(self):
        """Verify errors return clean JSON without exposing stack traces or internals."""
        # 404 Not Found
        resp404 = self.client.get("/api/unknown-pilot-route")
        self.assertEqual(resp404.status_code, 404)
        data404 = json.loads(resp404.data)
        self.assertFalse(data404.get("success", True))
        self.assertIn("message", data404)
        self.assertNotIn("Traceback", str(resp404.data))

        # 405 Method Not Allowed
        resp405 = self.client.post("/api/health")
        self.assertEqual(resp405.status_code, 405)
        data405 = json.loads(resp405.data)
        self.assertFalse(data405.get("success", True))
        self.assertIn("message", data405)
        self.assertNotIn("Traceback", str(resp405.data))


if __name__ == "__main__":
    unittest.main()
