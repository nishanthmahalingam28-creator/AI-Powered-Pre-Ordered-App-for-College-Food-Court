"""
Phase 5 Payment Gateway & Production Security Automated Test Suite.

Comprehensive validation of:
1. Payment Order Creation (Authoritative amount calculation in paise, gateway order ID, currency).
2. Server-Side Verification (Authentic HMAC-SHA256 signature validation, tampering rejection).
3. Security & Anti-Fraud (Client paid flag rejection, IDOR cross-customer verification block).
4. Webhook Security (X-Razorpay-Signature HMAC verification, replay protection, idempotency).
5. Stock & Payment Consistency (Preserved stock on success, exact-once restoration on failure).
6. Campus Wallet & Pay at Counter Non-Regression.
"""

import os
import sys
import json
import unittest
import hmac
import hashlib

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ["FLASK_ENV"] = "development"
os.environ["USE_SQLITE"] = "1"
os.environ["SECRET_KEY"] = "phase5-payment-security-test-key-32b-secret"
os.environ["PAYMENT_PROVIDER"] = "razorpay"
os.environ["PAYMENT_ENVIRONMENT"] = "test"
os.environ["RAZORPAY_KEY_ID"] = "rzp_test_collegefoodcourt2026"
os.environ["RAZORPAY_KEY_SECRET"] = "rzp_sec_kpriet_dev_secret_key_32b"
os.environ["RAZORPAY_WEBHOOK_SECRET"] = "rzp_wh_sec_kpriet_webhook_32b_key"

import init_db
init_db.init_sqlite()

from db import DB
from app import app
from werkzeug.security import generate_password_hash
from services.payment_provider import get_payment_provider
from services.payment import PaymentService


class TestPhase5PaymentGateway(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db.init_sqlite()
        cls.provider = get_payment_provider()

        # Customer A Setup
        cls.cust_a_email = "student.phase5a@kpriet.ac.in"
        cls.cust_a_pwd = "Password@123"
        user_a = DB.get_one("SELECT id FROM users WHERE email = %s", (cls.cust_a_email,))
        if not user_a:
            cls.cust_a_id = DB.execute(
                "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
                (cls.cust_a_email, generate_password_hash(cls.cust_a_pwd))
            )
            DB.execute(
                "INSERT INTO customer_profiles (user_id, customer_type, full_name, identifier, mobile, wallet_balance) "
                "VALUES (%s, 'student', 'Student A', '22CS001', '9876543211', 300.00)",
                (cls.cust_a_id,)
            )
        else:
            cls.cust_a_id = user_a["id"]
            DB.execute("UPDATE users SET password_hash = %s, role = 'customer', is_active = 1 WHERE id = %s",
                       (generate_password_hash(cls.cust_a_pwd), cls.cust_a_id))
            DB.execute("UPDATE customer_profiles SET wallet_balance = 300.00 WHERE user_id = %s", (cls.cust_a_id,))

        # Customer B Setup (For Cross-Tenant IDOR Tests)
        cls.cust_b_email = "student.phase5b@kpriet.ac.in"
        cls.cust_b_pwd = "Password@123"
        user_b = DB.get_one("SELECT id FROM users WHERE email = %s", (cls.cust_b_email,))
        if not user_b:
            cls.cust_b_id = DB.execute(
                "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
                (cls.cust_b_email, generate_password_hash(cls.cust_b_pwd))
            )
            DB.execute(
                "INSERT INTO customer_profiles (user_id, customer_type, full_name, identifier, mobile, wallet_balance) "
                "VALUES (%s, 'student', 'Student B', '22CS002', '9876543212', 150.00)",
                (cls.cust_b_id,)
            )
        else:
            cls.cust_b_id = user_b["id"]
            DB.execute("UPDATE users SET password_hash = %s, role = 'customer', is_active = 1 WHERE id = %s",
                       (generate_password_hash(cls.cust_b_pwd), cls.cust_b_id))

        # Ensure active stall & food items
        stall = DB.get_one("SELECT id FROM shops WHERE id = 1")
        if not stall:
            DB.execute("INSERT INTO shops (id, name, slug, owner_user_id, description, category, is_active) VALUES (1, 'YPR Canteen', 'ypr', 2, 'South Indian Food', 'Food', 1)")

        # Create or update specific test items
        item1 = DB.get_one("SELECT id FROM menu_items WHERE id = 1")
        if not item1:
            cls.item_dosa_id = DB.execute(
                "INSERT INTO menu_items (id, shop_id, name, description, price, category, quantity, is_available) VALUES (1, 1, 'Hot Ghee Dosa', 'Crispy Dosa', 65.00, 'Food', 50, 1)"
            )
        else:
            cls.item_dosa_id = 1
            DB.execute("UPDATE menu_items SET price = 65.00, quantity = 50, is_available = 1 WHERE id = 1")

        # Low stock item for stock depletion & rollback tests
        cls.item_vada_id = 99
        vada = DB.get_one("SELECT id FROM menu_items WHERE id = 99")
        if not vada:
            DB.execute(
                "INSERT INTO menu_items (id, shop_id, name, description, price, category, quantity, is_available) VALUES (99, 1, 'Medu Vada', 'Crispy Vada', 25.00, 'Food', 10, 1)"
            )
        else:
            DB.execute("UPDATE menu_items SET price = 25.00, quantity = 10, is_available = 1 WHERE id = 99")

    def setUp(self):
        self.client = app.test_client()

    def login_customer_a(self):
        res = self.client.post("/api/auth/customer/login", json={
            "email": self.cust_a_email,
            "password": self.cust_a_pwd
        })
        self.assertEqual(res.status_code, 200, "Customer A login failed")

    def login_customer_b(self):
        res = self.client.post("/api/auth/customer/login", json={
            "email": self.cust_b_email,
            "password": self.cust_b_pwd
        })
        self.assertEqual(res.status_code, 200, "Customer B login failed")

    # =========================================================================
    # 1. PAYMENT CREATION & AUTHORITATIVE AMOUNT
    # =========================================================================

    def test_01_create_online_payment_authoritative_amount_and_paise(self):
        """
        Checkout generates local order and gateway order with authoritative amount in paise.
        Order and payment start in strictly PENDING state.
        """
        self.login_customer_a()
        # Order: 2 x Dosa (65.00) = 130.00
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_dosa_id, "quantity": 2}],
            "payment_method": "UPI / Online"
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data["success"])
        order = data["order"]

        self.assertEqual(order["total_amount"], 130.00)
        self.assertEqual(order["order_status"], "pending")
        self.assertEqual(order["payment_status"], "pending")
        self.assertEqual(order["currency"], "INR")
        self.assertEqual(order["amount_paise"], 13000)

        # Verify gateway details
        self.assertIsNotNone(order.get("gateway_order_id"))
        self.assertTrue(order["gateway_order_id"].startswith("order_"))
        self.assertEqual(order.get("razorpay_order_id"), order.get("gateway_order_id"))
        self.assertEqual(order.get("key_id"), "rzp_test_collegefoodcourt2026")

        # Verify local payments table record
        pay_record = DB.get_one("SELECT * FROM payments WHERE order_id = %s", (order["order_id"],))
        self.assertIsNotNone(pay_record)
        self.assertEqual(pay_record["status"], "pending")
        self.assertEqual(pay_record["provider"], "razorpay")
        self.assertEqual(pay_record["currency"], "INR")
        self.assertEqual(pay_record["gateway_order_id"], order["gateway_order_id"])
        self.assertEqual(float(pay_record["amount"]), 130.00)

    def test_02_amount_tampering_ignored_on_checkout(self):
        """
        Security requirement: Client sending tampered amount in request payload is ignored.
        Authoritative calculation strictly from database prices.
        """
        self.login_customer_a()
        # Attacker tries to pass total_amount: 1.00 for ₹130 order
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_dosa_id, "quantity": 2}],
            "total_amount": 1.00,
            "amount": 1.00,
            "amount_paise": 100,
            "payment_method": "UPI / Online"
        })
        self.assertEqual(res.status_code, 201)
        order = res.get_json()["order"]
        self.assertEqual(order["total_amount"], 130.00)
        self.assertEqual(order["amount_paise"], 13000)

    # =========================================================================
    # 2. SERVER-SIDE SIGNATURE VERIFICATION
    # =========================================================================

    def test_03_valid_razorpay_signature_confirms_payment(self):
        """
        Valid HMAC-SHA256 signature updates payment_status to 'paid' and records payment_time.
        """
        self.login_customer_a()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_dosa_id, "quantity": 1}],
            "payment_method": "UPI / Online"
        })
        order = res.get_json()["order"]
        order_id = order["order_id"]
        gateway_order_id = order["gateway_order_id"]
        gateway_payment_id = "pay_test_txn_998877"

        # Generate authentic HMAC-SHA256 signature using provider key
        valid_signature = self.provider.generate_test_signature(gateway_order_id, gateway_payment_id)

        verify_res = self.client.post(f"/api/orders/{order_id}/verify-payment", json={
            "razorpay_order_id": gateway_order_id,
            "razorpay_payment_id": gateway_payment_id,
            "razorpay_signature": valid_signature
        })
        self.assertEqual(verify_res.status_code, 200)
        verify_data = verify_res.get_json()
        self.assertTrue(verify_data["success"])
        self.assertEqual(verify_data["payment_status"], "paid")

        # Verify database state
        db_order = DB.get_one("SELECT payment_status, payment_time FROM orders WHERE id = %s", (order_id,))
        self.assertEqual(db_order["payment_status"], "paid")
        self.assertIsNotNone(db_order["payment_time"])

        db_payment = DB.get_one("SELECT status, gateway_payment_id, paid_at FROM payments WHERE order_id = %s", (order_id,))
        self.assertEqual(db_payment["status"], "successful")
        self.assertEqual(db_payment["gateway_payment_id"], gateway_payment_id)
        self.assertIsNotNone(db_payment["paid_at"])

    def test_04_tampered_or_invalid_signature_rejected(self):
        """
        Invalid or modified signature must be rejected with HTTP 400; order remains pending.
        """
        self.login_customer_a()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_dosa_id, "quantity": 1}],
            "payment_method": "UPI / Online"
        })
        order = res.get_json()["order"]
        order_id = order["order_id"]
        gateway_order_id = order["gateway_order_id"]

        # Tampered signature
        fake_signature = "bad_forged_signature_hash_00000000000000000000000000000000"
        verify_res = self.client.post(f"/api/orders/{order_id}/verify-payment", json={
            "razorpay_order_id": gateway_order_id,
            "razorpay_payment_id": "pay_test_tampered_1",
            "razorpay_signature": fake_signature
        })
        self.assertEqual(verify_res.status_code, 400)
        self.assertIn("invalid or tampered", verify_res.get_json()["message"].lower())

        # Payment status must remain pending
        db_order = DB.get_one("SELECT payment_status FROM orders WHERE id = %s", (order_id,))
        self.assertEqual(db_order["payment_status"], "pending")

    def test_05_missing_signature_parameters_rejected(self):
        """Missing any required signature parameters rejected with HTTP 400."""
        self.login_customer_a()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_dosa_id, "quantity": 1}],
            "payment_method": "UPI / Online"
        })
        order_id = res.get_json()["order"]["order_id"]

        res_missing = self.client.post(f"/api/orders/{order_id}/verify-payment", json={
            "razorpay_payment_id": "pay_test_only"
        })
        self.assertEqual(res_missing.status_code, 400)

    def test_06_order_id_substitution_rejected(self):
        """Submitting signature for another order's gateway_order_id is rejected."""
        self.login_customer_a()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_dosa_id, "quantity": 1}],
            "payment_method": "UPI / Online"
        })
        order_id = res.get_json()["order"]["order_id"]

        wrong_gateway_order = "order_different_999999"
        sig = self.provider.generate_test_signature(wrong_gateway_order, "pay_123")

        verify_res = self.client.post(f"/api/orders/{order_id}/verify-payment", json={
            "razorpay_order_id": wrong_gateway_order,
            "razorpay_payment_id": "pay_123",
            "razorpay_signature": sig
        })
        self.assertEqual(verify_res.status_code, 400)
        self.assertIn("mismatch", verify_res.get_json()["message"].lower())

    # =========================================================================
    # 3. SECURITY & IDOR PROTECTION
    # =========================================================================

    def test_07_client_paid_flag_in_place_order_rejected(self):
        """Sending payment_status='paid' or is_paid=true from client is strictly rejected."""
        self.login_customer_a()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_dosa_id, "quantity": 1}],
            "payment_method": "UPI / Online",
            "payment_status": "paid",
            "is_paid": True,
            "status": "paid"
        })
        self.assertEqual(res.status_code, 201)
        order = res.get_json()["order"]
        self.assertEqual(order["payment_status"], "pending")
        self.assertEqual(order["order_status"], "pending")

    def test_08_customer_a_cannot_confirm_customer_b_payment(self):
        """Customer B cannot confirm or tamper with Customer A's order payment (HTTP 403 IDOR)."""
        # 1. Customer A places order
        self.login_customer_a()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_dosa_id, "quantity": 1}],
            "payment_method": "UPI / Online"
        })
        order = res.get_json()["order"]
        order_id = order["order_id"]
        gateway_order_id = order["gateway_order_id"]
        sig = self.provider.generate_test_signature(gateway_order_id, "pay_cross_tenant_1")

        # 2. Customer B attempts to confirm Customer A's order
        self.login_customer_b()
        res_cross = self.client.post(f"/api/orders/{order_id}/verify-payment", json={
            "razorpay_order_id": gateway_order_id,
            "razorpay_payment_id": "pay_cross_tenant_1",
            "razorpay_signature": sig
        })
        self.assertEqual(res_cross.status_code, 403)
        self.assertIn("forbidden", res_cross.get_json()["message"].lower())

    # =========================================================================
    # 4. WEBHOOK IMPLEMENTATION & SECURITY
    # =========================================================================

    def test_09_unsigned_or_invalid_webhook_rejected(self):
        """Webhook without X-Razorpay-Signature or with forged signature is rejected (HTTP 400)."""
        payload = json.dumps({"event": "payment.captured"}).encode("utf-8")

        # 1. No signature header
        res1 = self.client.post("/api/payments/webhook", data=payload, content_type="application/json")
        self.assertEqual(res1.status_code, 400)

        # 2. Invalid signature header
        res2 = self.client.post(
            "/api/payments/webhook",
            data=payload,
            content_type="application/json",
            headers={"X-Razorpay-Signature": "invalid_forged_webhook_signature"}
        )
        self.assertEqual(res2.status_code, 400)

    def test_10_valid_webhook_confirms_payment(self):
        """Authentic payment.captured webhook confirms order and records payment."""
        self.login_customer_a()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_dosa_id, "quantity": 1}],
            "payment_method": "UPI / Online"
        })
        order = res.get_json()["order"]
        order_id = order["order_id"]
        gateway_order_id = order["gateway_order_id"]

        webhook_payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_wh_test_1001",
                        "order_id": gateway_order_id,
                        "amount": 6500,
                        "currency": "INR",
                        "status": "captured"
                    }
                }
            }
        }
        raw_body = json.dumps(webhook_payload).encode("utf-8")
        valid_wh_sig = self.provider.generate_test_webhook_signature(raw_body)

        wh_res = self.client.post(
            "/api/payments/webhook",
            data=raw_body,
            content_type="application/json",
            headers={"X-Razorpay-Signature": valid_wh_sig}
        )
        self.assertEqual(wh_res.status_code, 200)

        # Verify DB updated to paid
        db_order = DB.get_one("SELECT payment_status FROM orders WHERE id = %s", (order_id,))
        self.assertEqual(db_order["payment_status"], "paid")

        db_payment = DB.get_one("SELECT status, gateway_payment_id FROM payments WHERE order_id = %s", (order_id,))
        self.assertEqual(db_payment["status"], "successful")
        self.assertEqual(db_payment["gateway_payment_id"], "pay_wh_test_1001")

    def test_11_webhook_amount_tampering_rejected(self):
        """Webhook reporting amount less than local order total is rejected and marks payment failed."""
        self.login_customer_a()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_dosa_id, "quantity": 2}], # ₹130 = 13000 paise
            "payment_method": "UPI / Online"
        })
        order = res.get_json()["order"]
        order_id = order["order_id"]
        gateway_order_id = order["gateway_order_id"]

        # Webhook reports only 1000 paise (₹10)
        webhook_payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_wh_tampered_amount",
                        "order_id": gateway_order_id,
                        "amount": 1000,
                        "currency": "INR"
                    }
                }
            }
        }
        raw_body = json.dumps(webhook_payload).encode("utf-8")
        wh_sig = self.provider.generate_test_webhook_signature(raw_body)

        wh_res = self.client.post(
            "/api/payments/webhook",
            data=raw_body,
            content_type="application/json",
            headers={"X-Razorpay-Signature": wh_sig}
        )
        self.assertEqual(wh_res.status_code, 400)

        # Order must NOT be marked as paid
        db_order = DB.get_one("SELECT payment_status FROM orders WHERE id = %s", (order_id,))
        self.assertNotEqual(db_order["payment_status"], "paid")

    # =========================================================================
    # 5. IDEMPOTENCY
    # =========================================================================

    def test_12_duplicate_verification_is_idempotent(self):
        """Submitting payment verification multiple times returns success without error."""
        self.login_customer_a()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_dosa_id, "quantity": 1}],
            "payment_method": "UPI / Online"
        })
        order = res.get_json()["order"]
        order_id = order["order_id"]
        gateway_order_id = order["gateway_order_id"]
        sig = self.provider.generate_test_signature(gateway_order_id, "pay_idem_1")

        # First verification
        v1 = self.client.post(f"/api/orders/{order_id}/verify-payment", json={
            "razorpay_order_id": gateway_order_id,
            "razorpay_payment_id": "pay_idem_1",
            "razorpay_signature": sig
        })
        self.assertEqual(v1.status_code, 200)

        # Duplicate verification
        v2 = self.client.post(f"/api/orders/{order_id}/verify-payment", json={
            "razorpay_order_id": gateway_order_id,
            "razorpay_payment_id": "pay_idem_1",
            "razorpay_signature": sig
        })
        self.assertEqual(v2.status_code, 200)
        self.assertTrue(v2.get_json()["success"])
        self.assertEqual(v2.get_json()["payment_status"], "paid")

    def test_13_duplicate_webhook_is_idempotent(self):
        """Duplicate webhook deliveries return 200 without double processing."""
        self.login_customer_a()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_dosa_id, "quantity": 1}],
            "payment_method": "UPI / Online"
        })
        gateway_order_id = res.get_json()["order"]["gateway_order_id"]

        webhook_payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_wh_dup_2002",
                        "order_id": gateway_order_id,
                        "amount": 6500,
                        "currency": "INR"
                    }
                }
            }
        }
        raw_body = json.dumps(webhook_payload).encode("utf-8")
        wh_sig = self.provider.generate_test_webhook_signature(raw_body)

        # Webhook delivery 1
        res1 = self.client.post("/api/payments/webhook", data=raw_body, headers={"X-Razorpay-Signature": wh_sig})
        self.assertEqual(res1.status_code, 200)

        # Duplicate webhook delivery 2
        res2 = self.client.post("/api/payments/webhook", data=raw_body, headers={"X-Razorpay-Signature": wh_sig})
        self.assertEqual(res2.status_code, 200)

    # =========================================================================
    # 6. STOCK CONSISTENCY
    # =========================================================================

    def test_14_successful_payment_preserves_stock_deduction(self):
        """Successful payment keeps stock reserved/deducted."""
        self.login_customer_a()
        stock_before = DB.get_one("SELECT quantity FROM menu_items WHERE id = %s", (self.item_vada_id,))["quantity"]

        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_vada_id, "quantity": 2}],
            "payment_method": "UPI / Online"
        })
        order = res.get_json()["order"]
        order_id = order["order_id"]
        gateway_order_id = order["gateway_order_id"]

        # Confirm payment
        sig = self.provider.generate_test_signature(gateway_order_id, "pay_stock_test_1")
        v_res = self.client.post(f"/api/orders/{order_id}/verify-payment", json={
            "razorpay_order_id": gateway_order_id,
            "razorpay_payment_id": "pay_stock_test_1",
            "razorpay_signature": sig
        })
        self.assertEqual(v_res.status_code, 200)

        # Stock must remain deducted by 2
        stock_after = DB.get_one("SELECT quantity FROM menu_items WHERE id = %s", (self.item_vada_id,))["quantity"]
        self.assertEqual(stock_after, stock_before - 2)

    def test_15_failed_payment_webhook_restores_stock_exactly_once(self):
        """Payment failure webhook restores reserved stock exactly once without double restoration."""
        self.login_customer_a()
        stock_before = DB.get_one("SELECT quantity FROM menu_items WHERE id = %s", (self.item_vada_id,))["quantity"]

        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_vada_id, "quantity": 3}],
            "payment_method": "UPI / Online"
        })
        order = res.get_json()["order"]
        order_id = order["order_id"]
        gateway_order_id = order["gateway_order_id"]

        # Verify stock decreased by 3 immediately upon order placement
        stock_reserved = DB.get_one("SELECT quantity FROM menu_items WHERE id = %s", (self.item_vada_id,))["quantity"]
        self.assertEqual(stock_reserved, stock_before - 3)

        # Deliver payment.failed webhook
        fail_payload = {
            "event": "payment.failed",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_failed_txn_001",
                        "order_id": gateway_order_id,
                        "error_description": "Card declined by bank"
                    }
                }
            }
        }
        raw_body = json.dumps(fail_payload).encode("utf-8")
        wh_sig = self.provider.generate_test_webhook_signature(raw_body)

        wh_res = self.client.post("/api/payments/webhook", data=raw_body, headers={"X-Razorpay-Signature": wh_sig})
        self.assertEqual(wh_res.status_code, 200)

        # Stock must be restored back to original stock_before
        stock_restored = DB.get_one("SELECT quantity FROM menu_items WHERE id = %s", (self.item_vada_id,))["quantity"]
        self.assertEqual(stock_restored, stock_before)

        # Duplicate failure webhook must NOT restore stock a second time
        wh_res2 = self.client.post("/api/payments/webhook", data=raw_body, headers={"X-Razorpay-Signature": wh_sig})
        self.assertEqual(wh_res2.status_code, 200)

        stock_after_dup = DB.get_one("SELECT quantity FROM menu_items WHERE id = %s", (self.item_vada_id,))["quantity"]
        self.assertEqual(stock_after_dup, stock_before)

    # =========================================================================
    # 7. CAMPUS WALLET & PAY AT COUNTER PRESERVATION
    # =========================================================================

    def test_16_campus_wallet_atomic_deduction(self):
        """Campus Wallet immediately settles payment without gateway interaction."""
        self.login_customer_a()
        bal_before = DB.get_one("SELECT wallet_balance FROM customer_profiles WHERE user_id = %s", (self.cust_a_id,))["wallet_balance"]

        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_dosa_id, "quantity": 1}], # ₹65.00
            "payment_method": "Campus Wallet"
        })
        self.assertEqual(res.status_code, 201)
        order = res.get_json()["order"]
        self.assertEqual(order["payment_status"], "paid")

        bal_after = DB.get_one("SELECT wallet_balance FROM customer_profiles WHERE user_id = %s", (self.cust_a_id,))["wallet_balance"]
        self.assertEqual(round(bal_after, 2), round(bal_before - 65.00, 2))

    def test_17_pay_at_counter_stays_pending_until_pickup(self):
        """Pay at Counter remains pending and is settled when vendor verifies pickup OTP."""
        self.login_customer_a()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_dosa_id, "quantity": 1}],
            "payment_method": "Pay at Counter"
        })
        self.assertEqual(res.status_code, 201)
        order = res.get_json()["order"]
        self.assertEqual(order["payment_status"], "pending")
        order_id = order["order_id"]
        otp = order["pickup_otp"]

        # Vendor logs in and verifies OTP
        v_res = self.client.post("/api/auth/vendor/login", json={
            "email": "ypr@kpriet.ac.in",
            "password": "vendor123"
        })
        self.assertEqual(v_res.status_code, 200, f"Vendor login failed: {v_res.get_json()}")
        otp_res = self.client.post("/api/orders/verify-otp", json={
            "order_id": order_id,
            "pickup_otp": otp
        })
        self.assertEqual(otp_res.status_code, 200)

        # Order must now be completed and payment_status = paid
        db_order = DB.get_one("SELECT order_status, payment_status FROM orders WHERE id = %s", (order_id,))
        self.assertEqual(db_order["order_status"], "completed")
        self.assertEqual(db_order["payment_status"], "paid")


if __name__ == "__main__":
    unittest.main()
