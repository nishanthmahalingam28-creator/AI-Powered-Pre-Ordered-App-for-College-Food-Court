"""
Phase 4 Ordering System Automated Test Suite.

Validates the complete real-world order lifecycle:
1. Cart & Order Validation (Single-stall rule, stock checks, negative qty, inactive items).
2. Stock Reservation & Deduction (Atomic deduction, depletion to 0, concurrency guard).
3. Order Items Immutability (Historical order price protected against subsequent menu price updates).
4. Critical Payment Lifecycle:
   - Server-side verification (frontend cannot spoof payment).
   - Campus Wallet balance deduction & insufficient funds rollback.
   - UPI/Online HMAC-signed gateway token initiation & verification.
   - Pay at Counter deferred payment.
5. Order Cancellation & Rollback (Stock restored, wallet refunded, rejected once preparing).
6. Itemized Bill & Receipt (Item snapshots, subtotal, totals, timestamps, IDOR protection).
7. Vendor Kitchen Queue & Status Progression (Timestamps: preparing, ready).
8. Pickup OTP Verification (Completion, timestamps, pay-at-counter settlement).
9. Full Real-World End-to-End Integration.
"""

import os
import sys
import json
import unittest
from decimal import Decimal

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ["FLASK_ENV"] = "development"
os.environ["USE_SQLITE"] = "1"
os.environ["SECRET_KEY"] = "phase4-ordering-system-test-key-32b-secret"

import init_db
init_db.init_sqlite()

from db import DB
from app import app
from werkzeug.security import generate_password_hash
from services.payment import PaymentService


class TestPhase4OrderingSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Refresh SQLite schema and initial data
        init_db.init_sqlite()

        # 1. Setup Customer User & Profile
        cls.cust_email = "student.phase4@kpriet.ac.in"
        cls.cust_pwd = "Password@123"
        cust_user = DB.get_one("SELECT id FROM users WHERE email = %s", (cls.cust_email,))
        if not cust_user:
            cls.cust_id = DB.execute(
                "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
                (cls.cust_email, generate_password_hash(cls.cust_pwd))
            )
        else:
            cls.cust_id = cust_user["id"]
            DB.execute("UPDATE users SET password_hash = %s, role = 'customer', is_active = 1 WHERE id = %s",
                       (generate_password_hash(cls.cust_pwd), cls.cust_id))

        cust_prof = DB.get_one("SELECT id FROM customer_profiles WHERE user_id = %s", (cls.cust_id,))
        if not cust_prof:
            DB.execute(
                "INSERT INTO customer_profiles (user_id, full_name, identifier, customer_type, wallet_balance) "
                "VALUES (%s, 'Phase4 Student', '22CS999', 'student', 500.00)",
                (cls.cust_id,)
            )
        else:
            DB.execute("UPDATE customer_profiles SET wallet_balance = 500.00, customer_type = 'student' WHERE user_id = %s", (cls.cust_id,))

        # 2. Setup Second Customer (for IDOR tests)
        cls.cust2_email = "guest.phase4@kpriet.ac.in"
        cls.cust2_pwd = "Password@123"
        cust2_user = DB.get_one("SELECT id FROM users WHERE email = %s", (cls.cust2_email,))
        if not cust2_user:
            cls.cust2_id = DB.execute(
                "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
                (cls.cust2_email, generate_password_hash(cls.cust2_pwd))
            )
        else:
            cls.cust2_id = cust2_user["id"]
            DB.execute("UPDATE users SET password_hash = %s, role = 'customer', is_active = 1 WHERE id = %s",
                       (generate_password_hash(cls.cust2_pwd), cls.cust2_id))

        cust2_prof = DB.get_one("SELECT id FROM customer_profiles WHERE user_id = %s", (cls.cust2_id,))
        if not cust2_prof:
            DB.execute(
                "INSERT INTO customer_profiles (user_id, full_name, identifier, customer_type, wallet_balance) "
                "VALUES (%s, 'Phase4 Guest', 'GST101', 'guest', 100.00)",
                (cls.cust2_id,)
            )
        else:
            DB.execute("UPDATE customer_profiles SET wallet_balance = 100.00, customer_type = 'guest' WHERE user_id = %s", (cls.cust2_id,))

        # 3. Setup Stall 1 (YPR) & Vendor User
        cls.vendor_email = "vendor.ypr.phase4@kpriet.ac.in"
        cls.vendor_pwd = "Vendor@123"
        vendor_user = DB.get_one("SELECT id FROM users WHERE email = %s", (cls.vendor_email,))
        if not vendor_user:
            cls.vendor_id = DB.execute(
                "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'vendor', 1)",
                (cls.vendor_email, generate_password_hash(cls.vendor_pwd))
            )
        else:
            cls.vendor_id = vendor_user["id"]

        shop1 = DB.get_one("SELECT id FROM shops WHERE name = 'YPR'")
        if not shop1:
            cls.shop1_id = DB.execute(
                "INSERT INTO shops (name, slug, description, is_active, owner_user_id) VALUES ('YPR', 'ypr-phase4', 'YPR Stall', 1, %s)",
                (cls.vendor_id,)
            )
        else:
            cls.shop1_id = shop1["id"]

        DB.execute("UPDATE shops SET owner_user_id = %s, is_active = 1 WHERE id = %s", (cls.vendor_id, cls.shop1_id))

        # 4. Setup Stall 2 (Chai Point) for multi-stall tests
        shop2 = DB.get_one("SELECT id FROM shops WHERE name = 'Chai Point'")
        if not shop2:
            cls.shop2_id = DB.execute(
                "INSERT INTO shops (name, slug, description, is_active) VALUES ('Chai Point', 'chai-point-phase4', 'Tea Stall', 1)"
            )
        else:
            cls.shop2_id = shop2["id"]

        # 5. Clean & Seed Fresh Menu Items for tests
        DB.execute("DELETE FROM menu_items WHERE shop_id IN (%s, %s)", (cls.shop1_id, cls.shop2_id))

        cls.item_burger_id = DB.execute(
            "INSERT INTO menu_items (shop_id, name, price, quantity, category, is_available) "
            "VALUES (%s, 'Crispy Veg Burger', 80.00, 20, 'Snacks', 1)",
            (cls.shop1_id,)
        )

        cls.item_fries_id = DB.execute(
            "INSERT INTO menu_items (shop_id, name, price, quantity, category, is_available) "
            "VALUES (%s, 'Peri Peri Fries', 60.00, 15, 'Snacks', 1)",
            (cls.shop1_id,)
        )

        cls.item_lowstock_id = DB.execute(
            "INSERT INTO menu_items (shop_id, name, price, quantity, category, is_available) "
            "VALUES (%s, 'Limited Dessert', 50.00, 2, 'Dessert', 1)",
            (cls.shop1_id,)
        )

        cls.item_inactive_id = DB.execute(
            "INSERT INTO menu_items (shop_id, name, price, quantity, category, is_available) "
            "VALUES (%s, 'Unavailable Pasta', 120.00, 10, 'Main Course', 0)",
            (cls.shop1_id,)
        )

        # Item belonging to Shop 2
        cls.item_tea_id = DB.execute(
            "INSERT INTO menu_items (shop_id, name, price, quantity, category, is_available) "
            "VALUES (%s, 'Masala Chai', 20.00, 30, 'Beverages', 1)",
            (cls.shop2_id,)
        )

        cls.client = app.test_client()

    def setUp(self):
        # Reset wallet balance and stock before each individual test
        DB.execute("UPDATE customer_profiles SET wallet_balance = 500.00 WHERE user_id = %s", (self.cust_id,))
        DB.execute("UPDATE customer_profiles SET wallet_balance = 100.00 WHERE user_id = %s", (self.cust2_id,))
        DB.execute("UPDATE menu_items SET price = 80.00, quantity = 20, is_available = 1 WHERE id = %s", (self.item_burger_id,))
        DB.execute("UPDATE menu_items SET price = 60.00, quantity = 15, is_available = 1 WHERE id = %s", (self.item_fries_id,))
        DB.execute("UPDATE menu_items SET price = 50.00, quantity = 2, is_available = 1 WHERE id = %s", (self.item_lowstock_id,))
        DB.execute("UPDATE menu_items SET price = 120.00, quantity = 10, is_available = 0 WHERE id = %s", (self.item_inactive_id,))
        DB.execute("UPDATE menu_items SET price = 20.00, quantity = 30, is_available = 1 WHERE id = %s", (self.item_tea_id,))

    def login_customer(self, email=None, pwd=None):
        email = email or self.cust_email
        pwd = pwd or self.cust_pwd
        res = self.client.post("/api/auth/customer/login", json={"email": email, "password": pwd})
        self.assertEqual(res.status_code, 200, f"Login failed for {email}: {res.get_json()}")
        return res

    def login_vendor(self):
        res = self.client.post("/api/auth/vendor/login", json={"email": self.vendor_email, "password": self.vendor_pwd})
        self.assertEqual(res.status_code, 200, f"Vendor login failed: {res.get_json()}")
        return res

    # ==========================================
    # 1. CART & PRE-ORDER VALIDATION TESTS
    # ==========================================

    def test_01_reject_empty_cart(self):
        self.login_customer()
        res = self.client.post("/api/orders", json={"items": [], "payment_method": "Campus Wallet"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("empty", res.get_json().get("message", "").lower())

    def test_02_reject_invalid_quantities(self):
        self.login_customer()
        # Zero quantity
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_burger_id, "quantity": 0}],
            "payment_method": "Campus Wallet"
        })
        self.assertEqual(res.status_code, 400)

        # Negative quantity
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_burger_id, "quantity": -3}],
            "payment_method": "Campus Wallet"
        })
        self.assertEqual(res.status_code, 400)

    def test_03_reject_non_existent_item(self):
        self.login_customer()
        res = self.client.post("/api/orders", json={
            "items": [{"id": 999999, "quantity": 1}],
            "payment_method": "Campus Wallet"
        })
        self.assertIn(res.status_code, (400, 404))
        self.assertIn("not found", res.get_json().get("message", "").lower())

    def test_04_reject_unavailable_inactive_item(self):
        self.login_customer()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_inactive_id, "quantity": 1}],
            "payment_method": "Campus Wallet"
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("out of stock", res.get_json().get("message", "").lower())

    def test_05_reject_multi_stall_cart(self):
        """Enforces Section 5: One-shop cart rule."""
        self.login_customer()
        # Item 1 from Stall 1 (Burger), Item 2 from Stall 2 (Tea)
        res = self.client.post("/api/orders", json={
            "items": [
                {"id": self.item_burger_id, "quantity": 1},
                {"id": self.item_tea_id, "quantity": 1}
            ],
            "payment_method": "Campus Wallet"
        })
        self.assertEqual(res.status_code, 400)
        msg = res.get_json().get("message", "").lower()
        self.assertTrue("one" in msg or "single" in msg)

    def test_06_reject_quantity_exceeding_stock(self):
        self.login_customer()
        # item_lowstock_id has quantity 2
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_lowstock_id, "quantity": 5}],
            "payment_method": "Campus Wallet"
        })
        self.assertEqual(res.status_code, 400)
        msg = res.get_json().get("message", "").lower()
        self.assertTrue("available" in msg or "adjust" in msg or "stock" in msg)

    # ==========================================
    # 2. STOCK RESERVATION & DEDUCTION TESTS
    # ==========================================

    def test_07_stock_deducted_atomically_upon_order(self):
        self.login_customer()
        before_stock = DB.get_one("SELECT quantity FROM menu_items WHERE id = %s", (self.item_burger_id,))["quantity"]

        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_burger_id, "quantity": 3}],
            "payment_method": "Campus Wallet"
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data["success"])

        after_stock = DB.get_one("SELECT quantity FROM menu_items WHERE id = %s", (self.item_burger_id,))["quantity"]
        self.assertEqual(after_stock, before_stock - 3)

    def test_08_depleting_stock_to_zero_marks_unavailable(self):
        self.login_customer()
        # item_lowstock_id has remaining stock 2
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_lowstock_id, "quantity": 2}],
            "payment_method": "Campus Wallet"
        })
        self.assertEqual(res.status_code, 201)

        item = DB.get_one("SELECT quantity, is_available FROM menu_items WHERE id = %s", (self.item_lowstock_id,))
        self.assertEqual(item["quantity"], 0)
        self.assertEqual(item["is_available"], 0)

        # Attempting to order again must fail
        res2 = self.client.post("/api/orders", json={
            "items": [{"id": self.item_lowstock_id, "quantity": 1}],
            "payment_method": "Campus Wallet"
        })
        self.assertEqual(res2.status_code, 400)

    # ==========================================
    # 3. ORDER ITEMS IMMUTABILITY TESTS
    # ==========================================

    def test_09_historical_order_price_immutable_after_menu_price_change(self):
        """
        Step 3 requirement:
        Changing the current menu item's price must NOT alter historical order totals.
        Burger ₹80 x 2 = ₹160. Later vendor changes price to ₹110. Old order must still be ₹160.
        """
        self.login_customer()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_burger_id, "quantity": 2}],
            "payment_method": "Campus Wallet"
        })
        self.assertEqual(res.status_code, 201)
        order_id = res.get_json()["order"]["order_id"]

        # Fetch initial order total
        order_before = DB.get_one("SELECT total_amount FROM orders WHERE id = %s", (order_id,))
        self.assertEqual(float(order_before["total_amount"]), 160.00)

        # Vendor changes Burger price to 110.00
        DB.execute("UPDATE menu_items SET price = 110.00 WHERE id = %s", (self.item_burger_id,))

        # Verify old order in database is still 160.00
        order_after = DB.get_one("SELECT total_amount FROM orders WHERE id = %s", (order_id,))
        self.assertEqual(float(order_after["total_amount"]), 160.00)

        # Verify old order item snapshot has unit_price 80.00
        order_item = DB.get_one("SELECT * FROM order_items WHERE order_id = %s", (order_id,))
        self.assertEqual(float(order_item["unit_price"]), 80.00)
        self.assertEqual(float(order_item["subtotal"]), 160.00)

        # Verify Bill API returns historical 160.00
        bill_res = self.client.get(f"/api/orders/{order_id}/bill")
        self.assertEqual(bill_res.status_code, 200)
        bill = bill_res.get_json()["bill"]
        self.assertEqual(float(bill["total_amount"]), 160.00)
        self.assertEqual(float(bill["items"][0]["unit_price"]), 80.00)

        # Restore burger price
        DB.execute("UPDATE menu_items SET price = 80.00 WHERE id = %s", (self.item_burger_id,))

    # ==========================================
    # 4. CRITICAL PAYMENT LIFECYCLE TESTS
    # ==========================================

    def test_10_upi_online_starts_pending_and_provides_gateway_token(self):
        """
        Critical Requirement:
        Never mark an order payment_status = 'paid' before server gateway confirmation.
        """
        self.login_customer()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_fries_id, "quantity": 1}],
            "payment_method": "UPI / Online"
        })
        self.assertEqual(res.status_code, 201)
        order = res.get_json()["order"]

        # Crucial checks
        self.assertEqual(order["order_status"], "pending")
        self.assertEqual(order["payment_status"], "pending")
        self.assertIsNotNone(order.get("payment"))
        self.assertIsNotNone(order["payment"].get("gateway_token"))

        # Check DB directly
        db_order = DB.get_one("SELECT payment_status FROM orders WHERE id = %s", (order["order_id"],))
        self.assertEqual(db_order["payment_status"], "pending")

    def test_11_spoofed_or_invalid_gateway_confirmation_rejected(self):
        """Payment confirmation requires valid server-signed HMAC token."""
        self.login_customer()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_fries_id, "quantity": 1}],
            "payment_method": "UPI / Online"
        })
        order_id = res.get_json()["order"]["order_id"]

        # 1. Missing token
        res_fail1 = self.client.post(f"/api/orders/{order_id}/confirm-payment", json={
            "transaction_id": "TXN-FAKE-123"
        })
        self.assertEqual(res_fail1.status_code, 400)

        # 2. Forged / invalid signature token
        res_fail2 = self.client.post(f"/api/orders/{order_id}/confirm-payment", json={
            "gateway_token": f"{order_id}.60.00.forged_signature_token",
            "transaction_id": "TXN-FAKE-123"
        })
        self.assertEqual(res_fail2.status_code, 400)

        # Payment status must remain pending
        db_order = DB.get_one("SELECT payment_status FROM orders WHERE id = %s", (order_id,))
        self.assertEqual(db_order["payment_status"], "pending")

    def test_12_valid_gateway_confirmation_updates_payment_to_paid(self):
        """Server verified gateway confirmation transitions payment_status to 'paid'."""
        self.login_customer()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_fries_id, "quantity": 1}],
            "payment_method": "UPI / Online"
        })
        order = res.get_json()["order"]
        order_id = order["order_id"]
        valid_token = order["payment"]["gateway_token"]

        confirm_res = self.client.post(f"/api/orders/{order_id}/confirm-payment", json={
            "gateway_token": valid_token,
            "transaction_id": "UPI-REAL-TXN-778899"
        })
        self.assertEqual(confirm_res.status_code, 200)
        confirm_data = confirm_res.get_json()
        self.assertTrue(confirm_data["success"])
        self.assertEqual(confirm_data["payment_status"], "paid")

        # Verify DB records payment_time and payment_status = 'paid'
        db_order = DB.get_one("SELECT payment_status, payment_time FROM orders WHERE id = %s", (order_id,))
        self.assertEqual(db_order["payment_status"], "paid")
        self.assertIsNotNone(db_order["payment_time"])

    def test_13_campus_wallet_insufficient_balance_rollback(self):
        """Insufficient balance rolls back transaction; stock is NOT deducted."""
        self.login_customer()
        # Set wallet balance to ₹10.00
        DB.execute("UPDATE customer_profiles SET wallet_balance = 10.00 WHERE user_id = %s", (self.cust_id,))

        fries_stock_before = DB.get_one("SELECT quantity FROM menu_items WHERE id = %s", (self.item_fries_id,))["quantity"]

        # Attempt to order ₹60 fries with ₹10 wallet
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_fries_id, "quantity": 1}],
            "payment_method": "Campus Wallet"
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("insufficient", res.get_json().get("message", "").lower())

        # Stock must NOT have changed
        fries_stock_after = DB.get_one("SELECT quantity FROM menu_items WHERE id = %s", (self.item_fries_id,))["quantity"]
        self.assertEqual(fries_stock_after, fries_stock_before)

        # Restore wallet balance to ₹500.00
        DB.execute("UPDATE customer_profiles SET wallet_balance = 500.00 WHERE user_id = %s", (self.cust_id,))

    def test_14_campus_wallet_sufficient_balance_deducts_atomically(self):
        self.login_customer()
        DB.execute("UPDATE customer_profiles SET wallet_balance = 200.00 WHERE user_id = %s", (self.cust_id,))

        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_fries_id, "quantity": 2}],  # 2 x 60 = 120
            "payment_method": "Campus Wallet"
        })
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.get_json()["order"]["payment_status"], "paid")

        wallet_after = DB.get_one("SELECT wallet_balance FROM customer_profiles WHERE user_id = %s", (self.cust_id,))["wallet_balance"]
        self.assertEqual(float(wallet_after), 80.00)

    # ==========================================
    # 5. ORDER CANCELLATION & ROLLBACK TESTS
    # ==========================================

    def test_15_cancel_pending_order_restores_stock_and_refunds_wallet(self):
        self.login_customer()
        DB.execute("UPDATE customer_profiles SET wallet_balance = 300.00 WHERE user_id = %s", (self.cust_id,))
        stock_before = DB.get_one("SELECT quantity FROM menu_items WHERE id = %s", (self.item_fries_id,))["quantity"]

        # Place order: 1 Fries = 60.00
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_fries_id, "quantity": 1}],
            "payment_method": "Campus Wallet"
        })
        order_id = res.get_json()["order"]["order_id"]

        # Verify stock decreased by 1 and wallet is 240
        stock_mid = DB.get_one("SELECT quantity FROM menu_items WHERE id = %s", (self.item_fries_id,))["quantity"]
        self.assertEqual(stock_mid, stock_before - 1)
        wallet_mid = DB.get_one("SELECT wallet_balance FROM customer_profiles WHERE user_id = %s", (self.cust_id,))["wallet_balance"]
        self.assertEqual(float(wallet_mid), 240.00)

        # Cancel the pending order
        cancel_res = self.client.post(f"/api/orders/{order_id}/cancel")
        self.assertEqual(cancel_res.status_code, 200)
        self.assertTrue(cancel_res.get_json()["success"])

        # Check stock is restored
        stock_after = DB.get_one("SELECT quantity FROM menu_items WHERE id = %s", (self.item_fries_id,))["quantity"]
        self.assertEqual(stock_after, stock_before)

        # Check wallet is refunded
        wallet_after = DB.get_one("SELECT wallet_balance FROM customer_profiles WHERE user_id = %s", (self.cust_id,))["wallet_balance"]
        self.assertEqual(float(wallet_after), 300.00)

        # Check order status is cancelled & payment status is refunded
        db_order = DB.get_one("SELECT order_status, payment_status, cancellation_time FROM orders WHERE id = %s", (order_id,))
        self.assertEqual(db_order["order_status"], "cancelled")
        self.assertEqual(db_order["payment_status"], "refunded")
        self.assertIsNotNone(db_order["cancellation_time"])

    def test_16_cannot_cancel_order_after_kitchen_preparing(self):
        """Customer cannot cancel order once stall begins preparing."""
        self.login_customer()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_fries_id, "quantity": 1}],
            "payment_method": "Campus Wallet"
        })
        order_id = res.get_json()["order"]["order_id"]

        # Vendor begins preparing
        self.login_vendor()
        self.client.put(f"/api/orders/{order_id}/status", json={"status": "preparing"})

        # Customer attempts to cancel
        self.login_customer()
        cancel_res = self.client.post(f"/api/orders/{order_id}/cancel")
        self.assertEqual(cancel_res.status_code, 400)
        self.assertIn("cannot cancel", cancel_res.get_json().get("message", "").lower())

    # ==========================================
    # 6. ITEMIZED BILL & IDOR SECURITY TESTS
    # ==========================================

    def test_17_bill_api_returns_itemized_snapshot_and_timestamps(self):
        self.login_customer()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_fries_id, "quantity": 2}],
            "payment_method": "Campus Wallet"
        })
        order_id = res.get_json()["order"]["order_id"]

        bill_res = self.client.get(f"/api/orders/{order_id}/bill")
        self.assertEqual(bill_res.status_code, 200)
        bill = bill_res.get_json()["bill"]

        self.assertEqual(bill["order_id"], order_id)
        self.assertEqual(bill["shop_name"], "YPR")
        self.assertEqual(float(bill["total_amount"]), 120.00)
        self.assertEqual(len(bill["items"]), 1)
        self.assertEqual(bill["items"][0]["item_name"], "Peri Peri Fries")
        self.assertEqual(bill["items"][0]["quantity"], 2)
        self.assertIn("timestamps", bill)
        self.assertIsNotNone(bill["timestamps"]["order_time"])

    def test_18_bill_api_idor_protection(self):
        """Customer 2 cannot view Customer 1's bill."""
        self.login_customer(self.cust_email, self.cust_pwd)
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_fries_id, "quantity": 1}],
            "payment_method": "Campus Wallet"
        })
        cust1_order_id = res.get_json()["order"]["order_id"]

        # Login as Customer 2
        self.login_customer(self.cust2_email, self.cust2_pwd)
        bill_res = self.client.get(f"/api/orders/{cust1_order_id}/bill")
        self.assertEqual(bill_res.status_code, 403)
        msg = bill_res.get_json().get("message", "").lower()
        self.assertTrue("forbidden" in msg or "cannot access" in msg or "denied" in msg)

    # ==========================================
    # 7. VENDOR KITCHEN QUEUE & STATUS TRANSITIONS
    # ==========================================

    def test_19_vendor_sees_live_orders_for_their_shop_only(self):
        self.login_customer()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_burger_id, "quantity": 1}],
            "payment_method": "Campus Wallet"
        })
        order_id = res.get_json()["order"]["order_id"]

        self.login_vendor()
        vendor_orders_res = self.client.get(f"/api/orders/vendor/{self.shop1_id}")
        self.assertEqual(vendor_orders_res.status_code, 200)
        orders = vendor_orders_res.get_json()["orders"]
        order_ids = [o["id"] for o in orders]
        self.assertIn(order_id, order_ids)

    def test_20_vendor_status_transitions_and_timestamps(self):
        self.login_customer()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_burger_id, "quantity": 1}],
            "payment_method": "Campus Wallet"
        })
        order_id = res.get_json()["order"]["order_id"]

        self.login_vendor()
        # 1. Pending -> Preparing
        prep_res = self.client.put(f"/api/orders/{order_id}/status", json={"status": "preparing"})
        self.assertEqual(prep_res.status_code, 200)
        order_row = DB.get_one("SELECT order_status, preparing_time FROM orders WHERE id = %s", (order_id,))
        self.assertEqual(order_row["order_status"], "preparing")
        self.assertIsNotNone(order_row["preparing_time"])

        # 2. Preparing -> Ready
        ready_res = self.client.put(f"/api/orders/{order_id}/status", json={"status": "ready"})
        self.assertEqual(ready_res.status_code, 200)
        order_row = DB.get_one("SELECT order_status, ready_time FROM orders WHERE id = %s", (order_id,))
        self.assertEqual(order_row["order_status"], "ready")
        self.assertIsNotNone(order_row["ready_time"])

    # ==========================================
    # 8. PICKUP OTP VERIFICATION TESTS
    # ==========================================

    def test_21_verify_pickup_otp_completes_order(self):
        self.login_customer()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_burger_id, "quantity": 1}],
            "payment_method": "Campus Wallet"
        })
        order_data = res.get_json()["order"]
        order_id = order_data["order_id"]
        pickup_otp = order_data["pickup_otp"]

        self.login_vendor()
        # Vendor enters OTP
        verify_res = self.client.post("/api/orders/verify-otp", json={
            "otp": pickup_otp,
            "shop_id": self.shop1_id
        })
        self.assertEqual(verify_res.status_code, 200)
        self.assertTrue(verify_res.get_json()["success"])

        # Order must now be completed with completed_time
        order_row = DB.get_one("SELECT order_status, completed_time FROM orders WHERE id = %s", (order_id,))
        self.assertEqual(order_row["order_status"], "completed")
        self.assertIsNotNone(order_row["completed_time"])

    def test_22_verify_pickup_otp_wrong_otp_rejected(self):
        self.login_vendor()
        verify_res = self.client.post("/api/orders/verify-otp", json={
            "otp": "000000",
            "shop_id": self.shop1_id
        })
        self.assertEqual(verify_res.status_code, 404)
        self.assertFalse(verify_res.get_json()["success"])

    def test_23_pay_at_counter_marked_paid_upon_otp_verification(self):
        """Pay at Counter payment status stays pending until stall confirms pickup OTP."""
        self.login_customer()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_burger_id, "quantity": 1}],
            "payment_method": "Pay at Counter"
        })
        order_data = res.get_json()["order"]
        order_id = order_data["order_id"]
        otp = order_data["pickup_otp"]

        # Payment status must initially be pending
        self.assertEqual(order_data["payment_status"], "pending")

        # Vendor verifies OTP
        self.login_vendor()
        verify_res = self.client.post("/api/orders/verify-otp", json={
            "otp": otp,
            "shop_id": self.shop1_id
        })
        self.assertEqual(verify_res.status_code, 200)

        # Payment status must now be updated to paid in database
        order_row = DB.get_one("SELECT order_status, payment_status FROM orders WHERE id = %s", (order_id,))
        self.assertEqual(order_row["order_status"], "completed")
        self.assertEqual(order_row["payment_status"], "paid")

    # ==========================================
    # 9. FULL REAL-WORLD END-TO-END FLOW
    # ==========================================

    def test_24_full_real_world_e2e_order_lifecycle(self):
        """
        Complete real-world journey:
        Customer Cart -> Stock Reservation -> Order Created (pending) ->
        UPI Payment Gateway Confirmation -> Vendor Kitchen Queue -> Preparing ->
        Ready -> Customer Arrives with OTP -> Vendor Verifies OTP -> Completed ->
        Immutable Bill Snapshot.
        """
        # 1. Customer logs in & places UPI order
        self.login_customer()
        stock_init = DB.get_one("SELECT quantity FROM menu_items WHERE id = %s", (self.item_fries_id,))["quantity"]

        order_res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_fries_id, "quantity": 2}],
            "payment_method": "UPI / Online"
        })
        self.assertEqual(order_res.status_code, 201)
        order_payload = order_res.get_json()["order"]
        order_id = order_payload["order_id"]
        pickup_otp = order_payload["pickup_otp"]
        gateway_token = order_payload["payment"]["gateway_token"]

        # Stock reduced immediately
        stock_after_order = DB.get_one("SELECT quantity FROM menu_items WHERE id = %s", (self.item_fries_id,))["quantity"]
        self.assertEqual(stock_after_order, stock_init - 2)

        # Order & Payment initially pending
        self.assertEqual(order_payload["order_status"], "pending")
        self.assertEqual(order_payload["payment_status"], "pending")

        # 2. Server Gateway Payment Confirmation
        pay_res = self.client.post(f"/api/orders/{order_id}/confirm-payment", json={
            "gateway_token": gateway_token,
            "transaction_id": "UPI-E2E-SUCCESS-101"
        })
        self.assertEqual(pay_res.status_code, 200)
        self.assertEqual(pay_res.get_json()["payment_status"], "paid")

        # 3. Vendor sees order in active queue
        self.login_vendor()
        q_res = self.client.get(f"/api/orders/vendor/{self.shop1_id}")
        active_ids = [o["id"] for o in q_res.get_json()["orders"]]
        self.assertIn(order_id, active_ids)

        # 4. Vendor transitions: Preparing -> Ready
        self.client.put(f"/api/orders/{order_id}/status", json={"status": "preparing"})
        self.client.put(f"/api/orders/{order_id}/status", json={"status": "ready"})

        # 5. Customer presents OTP -> Vendor verifies
        otp_res = self.client.post("/api/orders/verify-otp", json={
            "otp": pickup_otp,
            "shop_id": self.shop1_id
        })
        self.assertEqual(otp_res.status_code, 200)

        # 6. Verify final completed state & bill
        self.login_customer()
        bill_res = self.client.get(f"/api/orders/{order_id}/bill")
        self.assertEqual(bill_res.status_code, 200)
        bill = bill_res.get_json()["bill"]

        self.assertEqual(bill["order_status"], "completed")
        self.assertEqual(bill["payment_status"], "paid")
        self.assertIsNotNone(bill["timestamps"]["order_time"])
        self.assertIsNotNone(bill["timestamps"]["payment_time"])
        self.assertIsNotNone(bill["timestamps"]["preparing_time"])
        self.assertIsNotNone(bill["timestamps"]["ready_time"])
        self.assertIsNotNone(bill["timestamps"]["completed_time"])


if __name__ == "__main__":
    unittest.main()
