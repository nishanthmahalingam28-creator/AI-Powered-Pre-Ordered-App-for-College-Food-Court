"""
Manual E2E Test Suite for Phase 7 — Notifications & Real-Time Order Communication.

Executes all 27 specified notification workflow verification steps:
[01] Customer login
[02] Vendor login
[03] Customer places YPR order
[04] Customer receives ORDER_PLACED notification
[05] Vendor receives NEW_ORDER notification
[06] Payment succeeds
[07] Customer receives PAYMENT_SUCCESS notification
[08] Vendor starts preparing
[09] Customer receives ORDER_PREPARING notification
[10] Vendor marks order READY
[11] Customer receives ORDER_READY notification
[12] Customer views pickup instructions
[13] Customer presents pickup OTP
[14] Vendor verifies OTP
[15] Order becomes COMPLETED
[16] Customer receives ORDER_COMPLETED notification
[17] Customer marks notification read
[18] Customer checks unread count
[19] Customer marks all notifications read
[20] Attempt cross-user notification access
[21] Verify IDOR protection
[22] Send duplicate event/webhook
[23] Verify no duplicate notification
[24] Simulate notification delivery failure
[25] Verify order/payment state remains correct
[26] Vendor verifies only own-shop notifications
[27] Admin verifies authorized operational information
"""

import os
import sys
import json
import unittest
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
os.environ["SECRET_KEY"] = "phase7-manual-e2e-32b-secret-key-ok"
os.environ["ADMIN_EMAIL"] = "admin@kpriet.ac.in"
os.environ["ADMIN_PASSWORD"] = "Admin@Secure2026!"

import init_db
init_db.init_sqlite()

from db import DB
from app import app
from werkzeug.security import generate_password_hash
from services.payment import PaymentService
from services.notification import NotificationService


def print_step(step_num, title, detail=""):
    print(f"\n[{step_num:02d}] {title}")
    if detail:
        print(f"     {detail}")


class ManualE2EPhase7Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app
        cls.app.config["TESTING"] = True

        # Clean slate for test isolation
        DB.execute("DELETE FROM notifications")
        DB.execute("DELETE FROM order_items")
        DB.execute("DELETE FROM payments")
        DB.execute("DELETE FROM orders")
        DB.execute("DELETE FROM menu_items")
        DB.execute("DELETE FROM shops")
        DB.execute("DELETE FROM audit_logs")
        DB.execute("DELETE FROM users WHERE email LIKE '%@test7.kpriet.ac.in'")

        cls.pwd = "Phase7Secure!123"
        hashed = generate_password_hash(cls.pwd)

        # 1. Customer 1 (YPR buyer)
        cls.cust1_email = "student1@test7.kpriet.ac.in"
        cls.cust1_id = DB.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
            (cls.cust1_email, hashed)
        )
        DB.execute(
            "INSERT INTO customer_profiles (user_id, customer_type, full_name, identifier, mobile) VALUES (%s, 'student', %s, 'KPR2026-01', '9876543210')",
            (cls.cust1_id, "Arun Kumar")
        )

        # 2. Customer 2 (Cross-user / IDOR testing)
        cls.cust2_email = "student2@test7.kpriet.ac.in"
        cls.cust2_id = DB.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
            (cls.cust2_email, hashed)
        )
        DB.execute(
            "INSERT INTO customer_profiles (user_id, customer_type, full_name, identifier, mobile) VALUES (%s, 'student', %s, 'KPR2026-02', '9876543211')",
            (cls.cust2_id, "Deepak Raja")
        )

        # 3. Vendor 1 (YPR Stalls)
        cls.v1_email = "vendor.ypr@test7.kpriet.ac.in"
        cls.v1_id = DB.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'vendor', 1)",
            (cls.v1_email, hashed)
        )
        cls.shop1_id = DB.execute(
            "INSERT INTO shops (name, slug, description, operational_status, is_active, owner_user_id) "
            "VALUES (%s, %s, %s, 'OPEN', 1, %s)",
            ("YPR Stalls", "ypr-stalls-e2e", "Main Canteen Meals", cls.v1_id)
        )
        cls.item1_id = DB.execute(
            "INSERT INTO menu_items (shop_id, name, price, quantity, is_available) VALUES (%s, %s, %s, %s, 1)",
            (cls.shop1_id, "Crispy Masala Dosa", 60.00, 100)
        )

        # 4. Vendor 2 (German Cafe - Isolation testing)
        cls.v2_email = "vendor.germancafe@test7.kpriet.ac.in"
        cls.v2_id = DB.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'vendor', 1)",
            (cls.v2_email, hashed)
        )
        cls.shop2_id = DB.execute(
            "INSERT INTO shops (name, slug, description, operational_status, is_active, owner_user_id) "
            "VALUES (%s, %s, %s, 'OPEN', 1, %s)",
            ("German Cafe", "german-cafe-e2e", "European Snacks & Coffee", cls.v2_id)
        )

        # 5. Admin user
        cls.admin_email = "admin@kpriet.ac.in"
        cls.admin_pwd = "Admin@Secure2026!"
        admin_hash = generate_password_hash(cls.admin_pwd)
        admin = DB.get_one("SELECT id FROM users WHERE email = %s", (cls.admin_email,))
        if not admin:
            cls.admin_id = DB.execute(
                "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'admin', 1)",
                (cls.admin_email, admin_hash)
            )
        else:
            cls.admin_id = admin["id"]
            DB.execute("UPDATE users SET password_hash = %s, role = 'admin', is_active = 1 WHERE id = %s",
                       (admin_hash, cls.admin_id))

    def setUp(self):
        self.client = self.app.test_client()

    def login(self, email, password, role="customer"):
        login_url = "/api/auth/customer/login" if role == "customer" else (
            "/api/auth/vendor/login" if role == "vendor" else "/api/auth/admin/login"
        )
        res = self.client.post(login_url, json={"email": email, "password": password})
        self.assertEqual(res.status_code, 200, f"Login failed for {email}")
        return res

    def test_complete_27_step_notification_lifecycle(self):
        print("\n" + "=" * 80)
        print("STARTING PHASE 7 MANUAL 27-STEP END-TO-END NOTIFICATION & REAL-TIME TEST")
        print("=" * 80)

        # --------------------------------------------------------------------
        # [01] Customer login
        # --------------------------------------------------------------------
        print_step(1, "Customer Login", f"Authenticating student: {self.cust1_email}")
        res = self.login(self.cust1_email, self.pwd, role="customer")
        self.assertTrue(res.get_json()["success"])
        print("  -> Customer session established.")

        # --------------------------------------------------------------------
        # [02] Vendor login
        # --------------------------------------------------------------------
        print_step(2, "Vendor Login", f"Authenticating YPR stall owner: {self.v1_email}")
        vendor_client = self.app.test_client()
        res = vendor_client.post("/api/auth/vendor/login", json={"email": self.v1_email, "password": self.pwd})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["success"])
        print("  -> Vendor session established with shop isolation.")

        # --------------------------------------------------------------------
        # [03] Customer places YPR order
        # --------------------------------------------------------------------
        print_step(3, "Customer Places YPR Order", "Submitting multi-item order to YPR Stalls")
        res = self.client.post("/api/orders", json={
            "shop_id": self.shop1_id,
            "items": [{"menu_item_id": self.item1_id, "quantity": 2}],
            "payment_method": "upi"
        })
        self.assertEqual(res.status_code, 201)
        order_data = res.get_json()["order"]
        order_id = order_data["id"]
        order_ref = order_data["order_reference"]
        total_amount = float(order_data["total_amount"])
        print(f"  -> Order placed successfully: ID={order_id}, Ref={order_ref}, Amount=₹{total_amount}")

        # --------------------------------------------------------------------
        # [04] Customer receives ORDER_PLACED notification
        # --------------------------------------------------------------------
        print_step(4, "Customer Receives ORDER_PLACED Notification", "Verifying customer notification feed")
        res = self.client.get("/api/notifications")
        self.assertEqual(res.status_code, 200)
        notifs = res.get_json()["notifications"]
        placed_notif = next((n for n in notifs if n["type"] == "ORDER_PLACED" and n["order_id"] == order_id), None)
        self.assertIsNotNone(placed_notif, "ORDER_PLACED notification not found for customer")
        print(f"  -> Customer Notification verified: '{placed_notif['title']}' - '{placed_notif['message']}'")

        # --------------------------------------------------------------------
        # [05] Vendor receives NEW_ORDER notification
        # --------------------------------------------------------------------
        print_step(5, "Vendor Receives NEW_ORDER Notification", "Checking YPR kitchen notification queue")
        res = vendor_client.get("/api/notifications")
        self.assertEqual(res.status_code, 200)
        v_notifs = res.get_json()["notifications"]
        v_placed = next((n for n in v_notifs if (n["type"] in ["NEW_ORDER", "ORDER_PLACED"] or "New Order" in n["title"]) and n["order_id"] == order_id), None)
        self.assertIsNotNone(v_placed, "NEW_ORDER notification not found for vendor")
        print(f"  -> Vendor Notification verified: '{v_placed['title']}' - '{v_placed['message']}'")

        # --------------------------------------------------------------------
        # [06] Payment succeeds
        # --------------------------------------------------------------------
        print_step(6, "Payment Confirmation", f"Authoritative verification of ₹{total_amount} via PaymentService")
        gateway_order_id = order_data.get("gateway_order_id") or order_data.get("razorpay_order_id")
        from services.payment_provider import get_payment_provider
        provider = get_payment_provider()
        payment_id = f"pay_test_phase7_{order_id}"
        sig = provider.generate_test_signature(gateway_order_id, payment_id)

        res = self.client.post("/api/payments/verify", json={
            "order_id": order_id,
            "razorpay_order_id": gateway_order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": sig
        })
        self.assertEqual(res.status_code, 200)
        print("  -> Payment authoritatively marked 'paid' in database.")

        # --------------------------------------------------------------------
        # [07] Customer receives PAYMENT_SUCCESS notification
        # --------------------------------------------------------------------
        print_step(7, "Customer Receives PAYMENT_SUCCESS Notification", "Checking customer notifications for payment receipt")
        res = self.client.get("/api/notifications")
        notifs = res.get_json()["notifications"]
        pay_notif = next((n for n in notifs if n["type"] == "PAYMENT_SUCCESS" and n["order_id"] == order_id), None)
        self.assertIsNotNone(pay_notif, "PAYMENT_SUCCESS notification not found for customer")
        print(f"  -> Payment Notification verified: '{pay_notif['title']}' - '{pay_notif['message']}'")

        # --------------------------------------------------------------------
        # [08] Vendor starts preparing
        # --------------------------------------------------------------------
        print_step(8, "Vendor Starts Preparing", "Updating order status to 'preparing'")
        res = vendor_client.put(f"/api/orders/{order_id}/status", json={"status": "preparing"})
        self.assertEqual(res.status_code, 200)
        print("  -> Vendor status updated to 'preparing'.")

        # --------------------------------------------------------------------
        # [09] Customer receives ORDER_PREPARING notification
        # --------------------------------------------------------------------
        print_step(9, "Customer Receives ORDER_PREPARING Notification", "Verifying kitchen prep alert")
        res = self.client.get("/api/notifications")
        notifs = res.get_json()["notifications"]
        prep_notif = next((n for n in notifs if n["type"] == "ORDER_PREPARING" and n["order_id"] == order_id), None)
        self.assertIsNotNone(prep_notif, "ORDER_PREPARING notification not found")
        print(f"  -> Preparation Notification verified: '{prep_notif['title']}' - '{prep_notif['message']}'")

        # --------------------------------------------------------------------
        # [10] Vendor marks order READY
        # --------------------------------------------------------------------
        print_step(10, "Vendor Marks Order READY", "Updating order status to 'ready'")
        res = vendor_client.put(f"/api/orders/{order_id}/status", json={"status": "ready"})
        self.assertEqual(res.status_code, 200)
        print("  -> Vendor status updated to 'ready'.")

        # --------------------------------------------------------------------
        # [11] Customer receives ORDER_READY notification
        # --------------------------------------------------------------------
        print_step(11, "Customer Receives ORDER_READY Notification", "Verifying pickup notification")
        res = self.client.get("/api/notifications")
        notifs = res.get_json()["notifications"]
        ready_notif = next((n for n in notifs if n["type"] == "ORDER_READY" and n["order_id"] == order_id), None)
        self.assertIsNotNone(ready_notif, "ORDER_READY notification not found")
        print(f"  -> Ready Notification verified: '{ready_notif['title']}' - '{ready_notif['message']}'")

        # --------------------------------------------------------------------
        # [12] Customer views pickup instructions
        # --------------------------------------------------------------------
        print_step(12, "Customer Views Pickup Instructions", "Checking instructions for OTP presentation")
        self.assertIn("OTP", ready_notif["message"].upper())
        self.assertIn("counter", ready_notif["message"].lower())
        print(f"  -> Pickup instructions safely contained in message: '{ready_notif['message']}'")

        # --------------------------------------------------------------------
        # [13] Customer presents pickup OTP
        # --------------------------------------------------------------------
        print_step(13, "Customer Presents Pickup OTP", "Retrieving secure OTP from authoritative order details")
        res = self.client.get(f"/api/orders/{order_id}")
        self.assertEqual(res.status_code, 200)
        pickup_otp = res.get_json()["order"]["pickup_otp"]
        self.assertTrue(len(str(pickup_otp)) in [4, 6])
        print(f"  -> Student displays pickup OTP: {pickup_otp}")

        # --------------------------------------------------------------------
        # [14] Vendor verifies OTP
        # --------------------------------------------------------------------
        print_step(14, "Vendor Verifies OTP", f"Vendor enters OTP {pickup_otp} at stall counter")
        res = vendor_client.post("/api/orders/verify-otp", json={"otp": pickup_otp})
        self.assertEqual(res.status_code, 200)
        print("  -> OTP validated by vendor counter endpoint.")

        # --------------------------------------------------------------------
        # [15] Order becomes COMPLETED
        # --------------------------------------------------------------------
        print_step(15, "Order Becomes COMPLETED", "Confirming backend state transition")
        order_row = DB.get_one("SELECT order_status FROM orders WHERE id = %s", (order_id,))
        self.assertEqual(order_row["order_status"], "completed")
        print("  -> Authoritative order status confirmed as 'completed'.")

        # --------------------------------------------------------------------
        # [16] Customer receives ORDER_COMPLETED notification
        # --------------------------------------------------------------------
        print_step(16, "Customer Receives ORDER_COMPLETED Notification", "Verifying completion receipt")
        res = self.client.get("/api/notifications")
        notifs = res.get_json()["notifications"]
        done_notif = next((n for n in notifs if n["type"] == "ORDER_COMPLETED" and n["order_id"] == order_id), None)
        self.assertIsNotNone(done_notif, "ORDER_COMPLETED notification not found")
        print(f"  -> Completion Notification verified: '{done_notif['title']}' - '{done_notif['message']}'")

        # --------------------------------------------------------------------
        # [17] Customer marks notification read
        # --------------------------------------------------------------------
        print_step(17, "Customer Marks Notification Read", f"Marking notification {done_notif['id']} as read")
        res = self.client.put(f"/api/notifications/{done_notif['id']}/read")
        self.assertEqual(res.status_code, 200)
        check = DB.get_one("SELECT is_read, read_at FROM notifications WHERE id = %s", (done_notif["id"],))
        self.assertEqual(check["is_read"], 1)
        self.assertIsNotNone(check["read_at"])
        print(f"  -> Notification {done_notif['id']} marked as read at {check['read_at']}")

        # --------------------------------------------------------------------
        # [18] Customer checks unread count
        # --------------------------------------------------------------------
        print_step(18, "Customer Checks Unread Count", "Verifying GET /api/notifications/unread-count")
        res = self.client.get("/api/notifications/unread-count")
        self.assertEqual(res.status_code, 200)
        cnt = res.get_json()["unread_count"]
        self.assertEqual(cnt, 4)
        print(f"  -> Authoritative unread count: {cnt}")

        # --------------------------------------------------------------------
        # [19] Customer marks all notifications read
        # --------------------------------------------------------------------
        print_step(19, "Customer Marks All Notifications Read", "Calling PUT /api/notifications/read-all")
        res = self.client.put("/api/notifications/read-all")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["marked_count"], 4)
        res = self.client.get("/api/notifications/unread-count")
        self.assertEqual(res.get_json()["unread_count"], 0)
        print("  -> All notifications successfully marked read. Unread count = 0.")

        # --------------------------------------------------------------------
        # [20] Attempt cross-user notification access
        # --------------------------------------------------------------------
        print_step(20, "Attempt Cross-User Notification Access", f"Customer 2 attempting to read Customer 1's notification ({done_notif['id']})")
        c2_client = self.app.test_client()
        res = c2_client.post("/api/auth/customer/login", json={"email": self.cust2_email, "password": self.pwd})
        self.assertEqual(res.status_code, 200)
        res = c2_client.put(f"/api/notifications/{done_notif['id']}/read")
        print(f"  -> Cross-user update returned HTTP {res.status_code}: {res.get_json()['message']}")

        # --------------------------------------------------------------------
        # [21] Verify IDOR protection
        # --------------------------------------------------------------------
        print_step(21, "Verify IDOR Protection", "Confirming Customer 2 was strictly blocked (403/404)")
        self.assertIn(res.status_code, [403, 404])
        res = c2_client.get("/api/notifications")
        self.assertEqual(len(res.get_json()["notifications"]), 0)
        print("  -> Strict IDOR isolation confirmed: Customer 2 has 0 access to Customer 1 notifications.")

        # --------------------------------------------------------------------
        # [22] Send duplicate event/webhook
        # --------------------------------------------------------------------
        print_step(22, "Send Duplicate Event / Webhook", "Re-triggering payment success notification for order")
        NotificationService.notify_customer(
            customer_id=self.cust1_id,
            notif_type="PAYMENT_SUCCESS",
            title=f"Payment Successful #{order_ref}",
            message=f"Duplicate payment event for #{order_ref}",
            order_id=order_id
        )

        # --------------------------------------------------------------------
        # [23] Verify no duplicate notification
        # --------------------------------------------------------------------
        print_step(23, "Verify No Duplicate Notification", "Checking that idempotency suppressed duplicate insertion")
        pay_rows = DB.query(
            "SELECT id FROM notifications WHERE user_id = %s AND order_id = %s AND type = 'PAYMENT_SUCCESS'",
            (self.cust1_id, order_id)
        )
        self.assertEqual(len(pay_rows), 1, f"Expected exactly 1 PAYMENT_SUCCESS notification, found {len(pay_rows)}")
        print("  -> Idempotency confirmed: Duplicate payment notification safely suppressed.")

        # --------------------------------------------------------------------
        # [24] Simulate notification delivery failure
        # --------------------------------------------------------------------
        print_step(24, "Simulate Notification Delivery Failure", "Injecting DB error during notification creation")
        with patch.object(NotificationService, "notify_customer", side_effect=RuntimeError("Simulated Notification Network Outage")):
            with patch.object(NotificationService, "notify_vendor", side_effect=RuntimeError("Simulated Notification Network Outage")):
                res = self.client.post("/api/orders", json={
                    "shop_id": self.shop1_id,
                    "items": [{"menu_item_id": self.item1_id, "quantity": 1}],
                    "payment_method": "campus_wallet"
                })

        # --------------------------------------------------------------------
        # [25] Verify order/payment state remains correct
        # --------------------------------------------------------------------
        print_step(25, "Verify Order / Transaction Remains Correct", "Checking order was successfully committed despite notification failure")
        self.assertEqual(res.status_code, 201)
        res_order = res.get_json()["order"]
        order2_id = res_order["id"]
        check_db = DB.get_one("SELECT order_status, payment_status FROM orders WHERE id = %s", (order2_id,))
        self.assertIsNotNone(check_db)
        print(f"  -> Principle verified: ORDER TRANSACTION != NOTIFICATION DELIVERY.")
        print(f"     Order #{order2_id} created successfully with status='{check_db['order_status']}', payment='{check_db['payment_status']}'.")

        # --------------------------------------------------------------------
        # [26] Vendor verifies only own-shop notifications
        # --------------------------------------------------------------------
        print_step(26, "Vendor Shop Isolation Verification", "Checking German Cafe vendor receives 0 YPR notifications")
        v2_client = self.app.test_client()
        res = v2_client.post("/api/auth/vendor/login", json={"email": self.v2_email, "password": self.pwd})
        self.assertEqual(res.status_code, 200)
        res = v2_client.get("/api/notifications")
        self.assertEqual(res.status_code, 200)
        v2_notifs = res.get_json()["notifications"]
        self.assertEqual(len(v2_notifs), 0, "German Cafe vendor unexpectedly received notifications from YPR orders")
        print("  -> Vendor isolation verified: German Cafe has 0 notifications from YPR orders.")

        # --------------------------------------------------------------------
        # [27] Admin verifies authorized operational information
        # --------------------------------------------------------------------
        print_step(27, "Admin Authorized Operational Inspection", "Admin authenticates and inspects operational governance feed")
        admin_client = self.app.test_client()
        res = admin_client.post("/api/auth/admin/login", json={"email": self.admin_email, "password": self.admin_pwd})
        self.assertEqual(res.status_code, 200)

        admin_nids = NotificationService.notify_admin(
            notif_type="SYSTEM",
            title="Gateway Maintenance Notice",
            message="Nightly payment settlement run completed without discrepancy."
        )
        self.assertGreater(len(admin_nids), 0)

        res = admin_client.get("/api/notifications")
        self.assertEqual(res.status_code, 200)
        admin_feed = res.get_json()["notifications"]
        sys_notif = next((n for n in admin_feed if n["type"] == "SYSTEM"), None)
        self.assertIsNotNone(sys_notif, "Admin SYSTEM notification not found")
        print(f"  -> Admin Operational Feed verified: '{sys_notif['title']}' - '{sys_notif['message']}'")

        print("\n" + "=" * 80)
        print("ALL 27 PHASE 7 MANUAL END-TO-END NOTIFICATION STEPS PASSED SUCCESSFULLY!")
        print("=" * 80 + "\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
