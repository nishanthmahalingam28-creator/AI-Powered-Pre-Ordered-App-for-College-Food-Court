"""
Automated Test Suite for Phase 7 — Notifications & Real-Time Order Communication.

Verifies:
1. Authenticated user can retrieve notifications
2. Unauthenticated user is rejected (401)
3. Customer only sees own notifications
4. IDOR protection: Customer A cannot view or mark Customer B's notification
5. Mark notification read (is_read=1, read_at populated)
6. Mark all notifications read
7. Unread count returns accurate counts
8. Order placed notification dispatched to customer
9. Order placed notification dispatched to vendor (NEW_ORDER)
10. Payment success notification on gateway verification
11. Payment failure notification on gateway failure
12. Preparing notification dispatched to customer
13. Ready notification dispatched with pickup OTP instructions
14. Order completed notification upon OTP verification
15. Order cancellation notification to customer and vendor
16. Duplicate event / webhook does not create duplicate notifications (Idempotency)
17. Vendor only receives own-shop notifications (Shop Isolation)
18. XSS payload in notification content is safely escaped
19. Notification service failure does not break order placement (Non-blocking principle)
20. Notification service failure does not break payment verification
21. Pagination and query filters (unread, type) work correctly
"""

import os
import sys
import unittest
from datetime import datetime
from unittest.mock import patch

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ["FLASK_ENV"] = "development"
os.environ["USE_SQLITE"] = "1"
os.environ["SECRET_KEY"] = "phase7-test-32b-secret-key-verified-ok"
os.environ["PAYMENT_PROVIDER"] = "razorpay"
os.environ["PAYMENT_ENVIRONMENT"] = "test"
os.environ["RAZORPAY_KEY_ID"] = "rzp_test_collegefoodcourt2026"
os.environ["RAZORPAY_KEY_SECRET"] = "rzp_sec_kpriet_dev_secret_key_32b"
os.environ["RAZORPAY_WEBHOOK_SECRET"] = "rzp_wh_sec_kpriet_webhook_32b_key"

import init_db
init_db.init_sqlite()

from app import app
from db import DB
from werkzeug.security import generate_password_hash
from services.notification import NotificationService, NotificationType
from services.payment_provider import get_payment_provider


class TestPhase7Notifications(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

        # 1. Provision Admin Account
        cls.admin_email = "admin.phase7@kpriet.ac.in"
        cls.admin_pwd = "Admin@Phase7Password123"
        admin_u = DB.get_one("SELECT id FROM users WHERE email = %s", (cls.admin_email,))
        if not admin_u:
            cls.admin_id = DB.execute(
                "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'admin', 1)",
                (cls.admin_email, generate_password_hash(cls.admin_pwd))
            )
        else:
            cls.admin_id = admin_u["id"]
            DB.execute("UPDATE users SET password_hash = %s, role = 'admin', is_active = 1 WHERE id = %s",
                       (generate_password_hash(cls.admin_pwd), cls.admin_id))

        # 2. Provision Stall A (Phase7 Tandoor) & Vendor A
        cls.vendor_a_email = "vendor.tandoor@kpriet.ac.in"
        cls.vendor_a_pwd = "VendorA@Password123"
        v_user_a = DB.get_one("SELECT id FROM users WHERE email = %s", (cls.vendor_a_email,))
        if not v_user_a:
            cls.vendor_a_id = DB.execute(
                "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'vendor', 1)",
                (cls.vendor_a_email, generate_password_hash(cls.vendor_a_pwd))
            )
        else:
            cls.vendor_a_id = v_user_a["id"]
            DB.execute("UPDATE users SET password_hash = %s, role = 'vendor', is_active = 1 WHERE id = %s",
                       (generate_password_hash(cls.vendor_a_pwd), cls.vendor_a_id))

        shop_a = DB.get_one("SELECT id FROM shops WHERE slug = 'phase7-tandoor'")
        if not shop_a:
            cls.shop_a_id = DB.execute(
                "INSERT INTO shops (name, slug, category, is_active, operational_status, owner_user_id) "
                "VALUES ('Phase7 Tandoor', 'phase7-tandoor', 'North Indian', 1, 'OPEN', %s)",
                (cls.vendor_a_id,)
            )
        else:
            cls.shop_a_id = shop_a["id"]
            DB.execute("UPDATE shops SET owner_user_id = %s, is_active = 1, operational_status = 'OPEN' WHERE id = %s",
                       (cls.vendor_a_id, cls.shop_a_id))

        # 3. Provision Stall B (Phase7 Juice Bar) & Vendor B
        cls.vendor_b_email = "vendor.juice@kpriet.ac.in"
        cls.vendor_b_pwd = "VendorB@Password123"
        v_user_b = DB.get_one("SELECT id FROM users WHERE email = %s", (cls.vendor_b_email,))
        if not v_user_b:
            cls.vendor_b_id = DB.execute(
                "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'vendor', 1)",
                (cls.vendor_b_email, generate_password_hash(cls.vendor_b_pwd))
            )
        else:
            cls.vendor_b_id = v_user_b["id"]
            DB.execute("UPDATE users SET password_hash = %s, role = 'vendor', is_active = 1 WHERE id = %s",
                       (generate_password_hash(cls.vendor_b_pwd), cls.vendor_b_id))

        shop_b = DB.get_one("SELECT id FROM shops WHERE slug = 'phase7-juice'")
        if not shop_b:
            cls.shop_b_id = DB.execute(
                "INSERT INTO shops (name, slug, category, is_active, operational_status, owner_user_id) "
                "VALUES ('Phase7 Juice Bar', 'phase7-juice', 'Beverages', 1, 'OPEN', %s)",
                (cls.vendor_b_id,)
            )
        else:
            cls.shop_b_id = shop_b["id"]
            DB.execute("UPDATE shops SET owner_user_id = %s, is_active = 1, operational_status = 'OPEN' WHERE id = %s",
                       (cls.vendor_b_id, cls.shop_b_id))

        # 4. Provision Customer 1 (Student)
        cls.cust1_email = "student1.phase7@kpriet.ac.in"
        cls.cust1_pwd = "Password@Student123"
        c_user1 = DB.get_one("SELECT id FROM users WHERE email = %s", (cls.cust1_email,))
        if not c_user1:
            cls.cust1_id = DB.execute(
                "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
                (cls.cust1_email, generate_password_hash(cls.cust1_pwd))
            )
            DB.execute(
                "INSERT INTO customer_profiles (user_id, full_name, identifier, customer_type, wallet_balance, mobile) "
                "VALUES (%s, 'Phase7 Student One', '23CS101', 'student', 2500.00, '9888112233')",
                (cls.cust1_id,)
            )
        else:
            cls.cust1_id = c_user1["id"]
            DB.execute("UPDATE users SET password_hash = %s, role = 'customer', is_active = 1 WHERE id = %s",
                       (generate_password_hash(cls.cust1_pwd), cls.cust1_id))
            DB.execute("UPDATE customer_profiles SET wallet_balance = 2500.00 WHERE user_id = %s", (cls.cust1_id,))

        # 5. Provision Customer 2 (Faculty - for IDOR tests)
        cls.cust2_email = "faculty2.phase7@kpriet.ac.in"
        cls.cust2_pwd = "Password@Faculty123"
        c_user2 = DB.get_one("SELECT id FROM users WHERE email = %s", (cls.cust2_email,))
        if not c_user2:
            cls.cust2_id = DB.execute(
                "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
                (cls.cust2_email, generate_password_hash(cls.cust2_pwd))
            )
            DB.execute(
                "INSERT INTO customer_profiles (user_id, full_name, identifier, customer_type, wallet_balance, mobile) "
                "VALUES (%s, 'Phase7 Faculty Two', 'FAC702', 'faculty', 1000.00, '9777223344')",
                (cls.cust2_id,)
            )
        else:
            cls.cust2_id = c_user2["id"]
            DB.execute("UPDATE users SET password_hash = %s, role = 'customer', is_active = 1 WHERE id = %s",
                       (generate_password_hash(cls.cust2_pwd), cls.cust2_id))

        # 6. Seed Test Menu Items
        DB.execute("DELETE FROM menu_items WHERE shop_id IN (%s, %s)", (cls.shop_a_id, cls.shop_b_id))
        cls.item_paneer_id = DB.execute(
            "INSERT INTO menu_items (shop_id, name, description, price, category, quantity, is_available) "
            "VALUES (%s, 'Paneer Tikka Roll', 'Spiced paneer roll in mint chutney', 120.00, 'Snacks', 30, 1)",
            (cls.shop_a_id,)
        )
        cls.item_shake_id = DB.execute(
            "INSERT INTO menu_items (shop_id, name, description, price, category, quantity, is_available) "
            "VALUES (%s, 'Mango Shake', 'Fresh mango shake with ice cream', 60.00, 'Beverages', 25, 1)",
            (cls.shop_b_id,)
        )

    def setUp(self):
        # Clear test notifications between test runs
        DB.execute("DELETE FROM notifications WHERE user_id IN (%s, %s, %s, %s, %s)",
                   (self.admin_id, self.vendor_a_id, self.vendor_b_id, self.cust1_id, self.cust2_id))

    def login_admin(self):
        self.client.post("/api/auth/logout")
        res = self.client.post("/api/auth/admin/login", json={"username": self.admin_email, "password": self.admin_pwd})
        self.assertEqual(res.status_code, 200)

    def login_vendor_a(self):
        self.client.post("/api/auth/logout")
        res = self.client.post("/api/auth/vendor/login", json={"email": self.vendor_a_email, "password": self.vendor_a_pwd})
        self.assertEqual(res.status_code, 200)

    def login_vendor_b(self):
        self.client.post("/api/auth/logout")
        res = self.client.post("/api/auth/vendor/login", json={"email": self.vendor_b_email, "password": self.vendor_b_pwd})
        self.assertEqual(res.status_code, 200)

    def login_customer1(self):
        self.client.post("/api/auth/logout")
        res = self.client.post("/api/auth/customer/login", json={"email": self.cust1_email, "password": self.cust1_pwd})
        self.assertEqual(res.status_code, 200)

    def login_customer2(self):
        self.client.post("/api/auth/logout")
        res = self.client.post("/api/auth/customer/login", json={"email": self.cust2_email, "password": self.cust2_pwd})
        self.assertEqual(res.status_code, 200)

    # ========================================================================
    # 1. NOTIFICATION RETRIEVAL & AUTHENTICATION
    # ========================================================================

    def test_01_authenticated_user_can_retrieve_notifications(self):
        """Authenticated users can query their notification feed."""
        # Seed 2 notifications for customer 1
        NotificationService.create_notification(self.cust1_id, NotificationType.ORDER_PLACED, "Order Placed", "Your order #100 was placed.")
        NotificationService.create_notification(self.cust1_id, NotificationType.PAYMENT_SUCCESS, "Payment Confirmed", "Payment for #100 succeeded.")

        self.login_customer1()
        res = self.client.get("/api/notifications")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["notifications"]), 2)
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["unread_count"], 2)

    def test_02_unauthenticated_user_is_rejected(self):
        """Unauthenticated requests to notification endpoints are strictly rejected (401)."""
        self.client.post("/api/auth/logout")
        res = self.client.get("/api/notifications")
        self.assertEqual(res.status_code, 401)

        res_count = self.client.get("/api/notifications/unread-count")
        self.assertEqual(res_count.status_code, 401)

        res_read = self.client.put("/api/notifications/1/read")
        self.assertEqual(res_read.status_code, 401)

        res_all = self.client.put("/api/notifications/read-all")
        self.assertEqual(res_all.status_code, 401)

    # ========================================================================
    # 2. USER ISOLATION & IDOR PROTECTION
    # ========================================================================

    def test_03_customer_only_sees_own_notifications(self):
        """Customer A never sees Customer B's notifications."""
        # Notification for Customer 1
        NotificationService.create_notification(self.cust1_id, NotificationType.SYSTEM, "Cust 1 Alert", "Message for Cust 1")
        # Notification for Customer 2
        NotificationService.create_notification(self.cust2_id, NotificationType.SYSTEM, "Cust 2 Alert", "Message for Cust 2")

        self.login_customer1()
        res1 = self.client.get("/api/notifications")
        self.assertEqual(res1.status_code, 200)
        titles1 = [n["title"] for n in res1.get_json()["notifications"]]
        self.assertIn("Cust 1 Alert", titles1)
        self.assertNotIn("Cust 2 Alert", titles1)

        self.login_customer2()
        res2 = self.client.get("/api/notifications")
        self.assertEqual(res2.status_code, 200)
        titles2 = [n["title"] for n in res2.get_json()["notifications"]]
        self.assertIn("Cust 2 Alert", titles2)
        self.assertNotIn("Cust 1 Alert", titles2)

    def test_04_customer_cannot_access_or_modify_another_customers_notification(self):
        """IDOR Protection: Customer A cannot mark Customer B's notification as read."""
        notif_id_cust2 = NotificationService.create_notification(
            self.cust2_id, NotificationType.ORDER_PLACED, "Cust 2 Secret Order", "Details for Cust 2"
        )

        # Customer 1 attempts to mark Customer 2's notification as read
        self.login_customer1()
        res = self.client.put(f"/api/notifications/{notif_id_cust2}/read")
        self.assertEqual(res.status_code, 403)
        self.assertIn("Forbidden", res.get_json()["message"])

        # Verify notification remains unread for Customer 2
        notif = DB.get_one("SELECT is_read FROM notifications WHERE id = %s", (notif_id_cust2,))
        self.assertEqual(notif["is_read"], 0)

    # ========================================================================
    # 3. READ / UNREAD MANAGEMENT & UNREAD COUNT
    # ========================================================================

    def test_05_mark_single_notification_read(self):
        """Owner can mark their notification as read; is_read becomes 1 and read_at is populated."""
        nid = NotificationService.create_notification(self.cust1_id, NotificationType.ORDER_READY, "Food Ready", "Collect your food.")
        self.login_customer1()

        res = self.client.put(f"/api/notifications/{nid}/read")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["success"])

        # Check DB state
        row = DB.get_one("SELECT is_read, read_at FROM notifications WHERE id = %s", (nid,))
        self.assertEqual(row["is_read"], 1)
        self.assertIsNotNone(row["read_at"])

    def test_06_mark_all_notifications_read(self):
        """mark-all endpoint marks all notifications for authenticated user without affecting others."""
        # 3 unread for Cust 1
        for i in range(3):
            NotificationService.create_notification(self.cust1_id, NotificationType.ORDER_PLACED, f"Order {i}", f"Msg {i}")
        # 2 unread for Cust 2
        for j in range(2):
            NotificationService.create_notification(self.cust2_id, NotificationType.ORDER_PLACED, f"Cust2 Order {j}", f"Msg {j}")

        self.login_customer1()
        res = self.client.put("/api/notifications/read-all")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["marked_count"], 3)

        # Verify Customer 1 has 0 unread
        self.assertEqual(NotificationService.get_unread_count(self.cust1_id), 0)
        # Verify Customer 2 still has 2 unread!
        self.assertEqual(NotificationService.get_unread_count(self.cust2_id), 2)

    def test_07_unread_count_accurate(self):
        """GET /api/notifications/unread-count returns accurate count reflecting read changes."""
        NotificationService.create_notification(self.cust1_id, NotificationType.ORDER_PLACED, "N1", "M1")
        NotificationService.create_notification(self.cust1_id, NotificationType.ORDER_PLACED, "N2", "M2")

        self.login_customer1()
        res = self.client.get("/api/notifications/unread-count")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["unread_count"], 2)

    # ========================================================================
    # 4. ORDER LIFECYCLE EVENT NOTIFICATIONS
    # ========================================================================

    def test_08_order_placed_generates_customer_notification(self):
        """Placing an order creates an ORDER_PLACED notification for the customer."""
        self.login_customer1()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_paneer_id, "quantity": 1}],
            "payment_method": "Campus Wallet"
        })
        self.assertEqual(res.status_code, 201)
        order_info = res.get_json()["order"]
        order_id = order_info["id"]

        notifs = NotificationService.get_notifications(self.cust1_id)["notifications"]
        cust_notif_types = [n["type"] for n in notifs]
        self.assertIn("ORDER_PLACED", cust_notif_types)

    def test_09_order_placed_generates_vendor_new_order_notification(self):
        """Placing an order dispatches a NEW_ORDER notification to the assigned stall vendor."""
        self.login_customer1()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_paneer_id, "quantity": 1}],
            "payment_method": "Campus Wallet"
        })
        self.assertEqual(res.status_code, 201)

        # Vendor A owns Phase7 Tandoor -> Vendor A should receive notification
        v_notifs = NotificationService.get_notifications(self.vendor_a_id)["notifications"]
        self.assertTrue(any(n["type"] == "ORDER_PLACED" and "New Order" in n["title"] for n in v_notifs))

    def test_10_payment_success_notification_on_gateway_verification(self):
        """Authoritative payment verification emits PAYMENT_SUCCESS notification."""
        # Create online order (pending)
        self.login_customer1()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_paneer_id, "quantity": 1}],
            "payment_method": "UPI / Online"
        })
        self.assertEqual(res.status_code, 201)
        order_data = res.get_json()["order"]
        order_id = order_data["id"]
        gateway_order_id = order_data["gateway_order_id"]

        # Verify payment with real Razorpay mock signature
        provider = get_payment_provider()
        payment_id = f"pay_test_phase7_{order_id}"
        sig = provider.generate_test_signature(gateway_order_id, payment_id)

        v_res = self.client.post(f"/api/orders/{order_id}/verify-payment", json={
            "razorpay_order_id": gateway_order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": sig
        })
        self.assertEqual(v_res.status_code, 200)

        # Verify customer received PAYMENT_SUCCESS notification
        notifs = NotificationService.get_notifications(self.cust1_id)["notifications"]
        self.assertTrue(any(n["type"] == "PAYMENT_SUCCESS" and n["order_id"] == order_id for n in notifs))

    def test_11_payment_failure_notification_on_gateway_failure(self):
        """Payment failure reports emit PAYMENT_FAILED notification."""
        self.login_customer1()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_paneer_id, "quantity": 1}],
            "payment_method": "UPI / Online"
        })
        self.assertEqual(res.status_code, 201)
        order_id = res.get_json()["order"]["id"]

        # Simulate payment failure via PaymentService
        from services.payment import PaymentService
        PaymentService.handle_payment_failure(order_id, failure_reason="Card expired")

        notifs = NotificationService.get_notifications(self.cust1_id)["notifications"]
        self.assertTrue(any(n["type"] == "PAYMENT_FAILED" and n["order_id"] == order_id for n in notifs))

    def test_12_order_preparing_notification_to_customer(self):
        """Vendor setting order to 'preparing' creates an ORDER_PREPARING notification for customer."""
        self.login_customer1()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_paneer_id, "quantity": 1}],
            "payment_method": "Campus Wallet"
        })
        order_id = res.get_json()["order"]["id"]

        self.login_vendor_a()
        prep_res = self.client.put(f"/api/orders/{order_id}/status", json={"status": "preparing"})
        self.assertEqual(prep_res.status_code, 200)

        notifs = NotificationService.get_notifications(self.cust1_id)["notifications"]
        self.assertTrue(any(n["type"] == "ORDER_PREPARING" and n["order_id"] == order_id for n in notifs))

    def test_13_order_ready_notification_with_otp_instructions(self):
        """Vendor setting order to 'ready' creates an ORDER_READY notification mentioning pickup OTP."""
        self.login_customer1()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_paneer_id, "quantity": 1}],
            "payment_method": "Campus Wallet"
        })
        order_id = res.get_json()["order"]["id"]
        pickup_otp = res.get_json()["order"]["pickup_otp"]

        self.login_vendor_a()
        self.client.put(f"/api/orders/{order_id}/status", json={"status": "preparing"})
        ready_res = self.client.put(f"/api/orders/{order_id}/status", json={"status": "ready"})
        self.assertEqual(ready_res.status_code, 200)

        notifs = NotificationService.get_notifications(self.cust1_id)["notifications"]
        ready_notif = next((n for n in notifs if n["type"] == "ORDER_READY" and n["order_id"] == order_id), None)
        self.assertIsNotNone(ready_notif)
        self.assertIn(pickup_otp, ready_notif["message"])

    def test_14_order_completed_notification_upon_otp_verification(self):
        """Valid pickup OTP verification completes order and sends ORDER_COMPLETED notification."""
        self.login_customer1()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_paneer_id, "quantity": 1}],
            "payment_method": "Campus Wallet"
        })
        order_id = res.get_json()["order"]["id"]
        pickup_otp = res.get_json()["order"]["pickup_otp"]

        self.login_vendor_a()
        self.client.put(f"/api/orders/{order_id}/status", json={"status": "preparing"})
        self.client.put(f"/api/orders/{order_id}/status", json={"status": "ready"})

        otp_res = self.client.post("/api/orders/verify-otp", json={
            "otp": pickup_otp,
            "shop_id": self.shop_a_id
        })
        self.assertEqual(otp_res.status_code, 200)

        notifs = NotificationService.get_notifications(self.cust1_id)["notifications"]
        self.assertTrue(any(n["type"] == "ORDER_COMPLETED" and n["order_id"] == order_id for n in notifs))

    def test_15_order_cancellation_notification_to_customer_and_vendor(self):
        """Cancelling an order dispatches ORDER_CANCELLED to both customer and vendor."""
        self.login_customer1()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_paneer_id, "quantity": 1}],
            "payment_method": "Campus Wallet"
        })
        order_id = res.get_json()["order"]["id"]

        cancel_res = self.client.post(f"/api/orders/{order_id}/cancel")
        self.assertEqual(cancel_res.status_code, 200)

        # Check customer received cancellation notification with refund details
        c_notifs = NotificationService.get_notifications(self.cust1_id)["notifications"]
        c_cancel = next((n for n in c_notifs if n["type"] == "ORDER_CANCELLED" and n["order_id"] == order_id), None)
        self.assertIsNotNone(c_cancel)
        self.assertIn("refunded", c_cancel["message"].lower())

        # Check vendor received cancellation notification
        v_notifs = NotificationService.get_notifications(self.vendor_a_id)["notifications"]
        v_cancel = next((n for n in v_notifs if n["type"] == "ORDER_CANCELLED" and n["order_id"] == order_id), None)
        self.assertIsNotNone(v_cancel)

    # ========================================================================
    # 5. IDEMPOTENCY & ISOLATION
    # ========================================================================

    def test_16_duplicate_webhook_or_event_does_not_create_duplicate_notification(self):
        """Idempotency guard prevents duplicate notification on replayed event."""
        self.login_customer1()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_paneer_id, "quantity": 1}],
            "payment_method": "Campus Wallet"
        })
        self.assertEqual(res.status_code, 201)
        test_order_id = res.get_json()["order"]["id"]

        # Clear notifications from initial placement
        DB.execute("DELETE FROM notifications WHERE order_id = %s", (test_order_id,))

        # First creation succeeds
        nid1 = NotificationService.create_notification(
            self.cust1_id, NotificationType.PAYMENT_SUCCESS, "Paid", "Your payment succeeded", order_id=test_order_id
        )
        self.assertIsNotNone(nid1)

        # Second creation with same order_id, user_id, and type is suppressed
        nid2 = NotificationService.create_notification(
            self.cust1_id, NotificationType.PAYMENT_SUCCESS, "Paid", "Your payment succeeded", order_id=test_order_id
        )
        self.assertIsNone(nid2)

        # Verify exactly one notification exists in DB
        rows = DB.query("SELECT id FROM notifications WHERE user_id = %s AND order_id = %s AND type = %s",
                        (self.cust1_id, test_order_id, NotificationType.PAYMENT_SUCCESS))
        self.assertEqual(len(rows), 1)

    def test_17_vendor_only_receives_assigned_shop_notifications(self):
        """Vendor of Shop A never receives notifications for Shop B orders."""
        # Customer orders from Stall A (Phase7 Tandoor)
        self.login_customer1()
        res_a = self.client.post("/api/orders", json={
            "items": [{"id": self.item_paneer_id, "quantity": 1}],
            "payment_method": "Campus Wallet"
        })
        order_a_id = res_a.get_json()["order"]["id"]

        # Vendor A receives notification
        v_a_notifs = NotificationService.get_notifications(self.vendor_a_id)["notifications"]
        self.assertTrue(any(n["order_id"] == order_a_id for n in v_a_notifs))

        # Vendor B (Juice Bar) MUST NOT receive notification for Shop A's order
        v_b_notifs = NotificationService.get_notifications(self.vendor_b_id)["notifications"]
        self.assertFalse(any(n["order_id"] == order_a_id for n in v_b_notifs))

    # ========================================================================
    # 6. SECURITY & NON-BLOCKING RESILIENCE
    # ========================================================================

    def test_18_xss_payload_in_notification_content_is_safely_escaped(self):
        """XSS injection payloads in notification title or message are safely sanitized/escaped."""
        raw_xss = "<script>alert('XSS-HACKED')</script><img src=x onerror=alert(1)>"
        nid = NotificationService.create_notification(
            self.cust1_id, NotificationType.SYSTEM, raw_xss, raw_xss
        )
        self.assertIsNotNone(nid)

        row = DB.get_one("SELECT title, message FROM notifications WHERE id = %s", (nid,))
        self.assertNotIn("<script>", row["title"])
        self.assertNotIn("<script>", row["message"])
        self.assertIn("&lt;script&gt;", row["title"])
        self.assertIn("&lt;script&gt;", row["message"])

    def test_19_notification_service_failure_does_not_break_order_placement(self):
        """
        Critical Rule: ORDER TRANSACTION != NOTIFICATION DELIVERY.
        Even if notification persistence throws an unhandled database exception,
        the order placement and stock deduction must succeed!
        """
        self.login_customer1()

        # Mock NotificationService.create_notification to simulate an internal failure
        with patch.object(NotificationService, "create_notification", side_effect=RuntimeError("Notification DB Failure")):
            res = self.client.post("/api/orders", json={
                "items": [{"id": self.item_paneer_id, "quantity": 1}],
                "payment_method": "Campus Wallet"
            })
            # Order MUST still succeed with HTTP 201!
            self.assertEqual(res.status_code, 201)
            self.assertTrue(res.get_json()["success"])
            order_id = res.get_json()["order"]["id"]
            # Verify order actually exists in database
            db_order = DB.get_one("SELECT id FROM orders WHERE id = %s", (order_id,))
            self.assertIsNotNone(db_order)

    def test_20_notification_service_failure_does_not_affect_payment_verification(self):
        """Payment confirmation succeeds even if notification dispatch encounters an error."""
        self.login_customer1()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_paneer_id, "quantity": 1}],
            "payment_method": "UPI / Online"
        })
        order_id = res.get_json()["order"]["id"]
        gateway_order_id = res.get_json()["order"]["gateway_order_id"]

        provider = get_payment_provider()
        payment_id = f"pay_resilience_test_{order_id}"
        sig = provider.generate_test_signature(gateway_order_id, payment_id)

        with patch.object(NotificationService, "create_notification", side_effect=RuntimeError("Notification Down")):
            v_res = self.client.post(f"/api/orders/{order_id}/verify-payment", json={
                "razorpay_order_id": gateway_order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": sig
            })
            self.assertEqual(v_res.status_code, 200)
            self.assertEqual(v_res.get_json()["payment_status"], "paid")

            # Verify order in DB is authoritatively marked paid
            order_row = DB.get_one("SELECT payment_status FROM orders WHERE id = %s", (order_id,))
            self.assertEqual(order_row["payment_status"], "paid")

    # ========================================================================
    # 7. PAGINATION & FILTERING
    # ========================================================================

    def test_21_pagination_and_query_filters_work_correctly(self):
        """Query parameters unread, type, and pagination function as expected."""
        # Create 5 unread notifications of various types
        NotificationService.create_notification(self.cust1_id, NotificationType.ORDER_PLACED, "O1", "M1")
        NotificationService.create_notification(self.cust1_id, NotificationType.ORDER_READY, "O2", "M2")
        NotificationService.create_notification(self.cust1_id, NotificationType.PAYMENT_SUCCESS, "P1", "M3")
        NotificationService.create_notification(self.cust1_id, NotificationType.PAYMENT_FAILED, "P2", "M4")
        nid_sys = NotificationService.create_notification(self.cust1_id, NotificationType.SYSTEM, "S1", "M5")

        # Mark system notification as read
        NotificationService.mark_as_read(nid_sys, self.cust1_id)

        self.login_customer1()

        # 1. Unread filter
        res_unread = self.client.get("/api/notifications?unread=true")
        self.assertEqual(res_unread.status_code, 200)
        self.assertEqual(res_unread.get_json()["total"], 4)

        # 2. Type filter: ORDER
        res_order = self.client.get("/api/notifications?type=ORDER")
        self.assertEqual(res_order.status_code, 200)
        self.assertEqual(res_order.get_json()["total"], 2)

        # 3. Type filter: PAYMENT
        res_pay = self.client.get("/api/notifications?type=PAYMENT")
        self.assertEqual(res_pay.status_code, 200)
        self.assertEqual(res_pay.get_json()["total"], 2)

        # 4. Pagination (limit=2, page=1)
        res_page = self.client.get("/api/notifications?limit=2&page=1")
        self.assertEqual(res_page.status_code, 200)
        p_data = res_page.get_json()
        self.assertEqual(len(p_data["notifications"]), 2)
        self.assertEqual(p_data["pages"], 3)


if __name__ == "__main__":
    unittest.main()
