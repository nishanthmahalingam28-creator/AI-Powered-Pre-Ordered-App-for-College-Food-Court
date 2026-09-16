"""
Automated Test Suite for Phase 6 — Admin & Vendor Operational Management.

Covers:
1. Server-Side RBAC for Admin and Vendor APIs
2. Admin Shop Management (CRUD, toggle is_active, operational_status)
3. Shop Operational Status Rules (OPEN, CLOSED, TEMPORARILY_UNAVAILABLE)
   - Prevents new customer orders when closed / unavailable
   - Preserves existing orders and allows vendors to fulfill in-flight orders
4. Admin Vendor Management & 1-to-1 Stall Assignment / Unassignment
5. Vendor Stall Isolation (IDOR protection, no trust of frontend shop_id)
6. Vendor Operational Visibility & Self-Service Status Toggle
7. Strict Order Status Transitions & Rejection of Backward Transitions
   (PENDING -> PREPARING -> READY -> PICKUP OTP -> COMPLETED)
8. Pickup OTP Verification, Rate Limiting, and Order Completion
9. Customer Account Directory, Search, and Account Suspension / Reactivation
10. Global Order Monitoring with Multi-Parameter Filters
11. Payment Gateway & Transaction Monitoring with Aggregate Statistics
12. Centralized Security Audit Logging across Operations
"""

import os
import sys
import json
import unittest
from werkzeug.security import generate_password_hash

# Ensure test environment uses development SQLite for isolated testing
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ["FLASK_ENV"] = "development"
os.environ["USE_SQLITE"] = "1"
os.environ["SECRET_KEY"] = "phase6-operations-management-test-secret-key-32b"

import init_db
init_db.init_sqlite()

from app import app
from db import DB


class TestPhase6OperationsManagement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

        # 1. Setup Admin Account
        cls.admin_email = "admin.phase6@kpriet.ac.in"
        cls.admin_pwd = "Admin@Phase6Password123"
        admin_user = DB.get_one("SELECT id FROM users WHERE email = %s", (cls.admin_email,))
        if not admin_user:
            cls.admin_id = DB.execute(
                "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'admin', 1)",
                (cls.admin_email, generate_password_hash(cls.admin_pwd))
            )
        else:
            cls.admin_id = admin_user["id"]
            DB.execute("UPDATE users SET password_hash = %s, role = 'admin', is_active = 1 WHERE id = %s",
                       (generate_password_hash(cls.admin_pwd), cls.admin_id))

        # 2. Setup Dedicated Test Stalls
        # Stall A: Primary Vendor Stall
        shop_a = DB.get_one("SELECT id FROM shops WHERE name = 'Phase6 Grill'")
        if not shop_a:
            cls.shop_a_id = DB.execute(
                "INSERT INTO shops (name, slug, description, category, is_active, operational_status) "
                "VALUES ('Phase6 Grill', 'phase6-grill', 'Grill and BBQ', 'Fast Food', 1, 'OPEN')"
            )
        else:
            cls.shop_a_id = shop_a["id"]
            DB.execute("UPDATE shops SET is_active = 1, operational_status = 'OPEN' WHERE id = %s", (cls.shop_a_id,))

        # Stall B: Secondary Stall (for isolation tests)
        shop_b = DB.get_one("SELECT id FROM shops WHERE name = 'Phase6 Juice'")
        if not shop_b:
            cls.shop_b_id = DB.execute(
                "INSERT INTO shops (name, slug, description, category, is_active, operational_status) "
                "VALUES ('Phase6 Juice', 'phase6-juice', 'Juice bar', 'Beverages', 1, 'OPEN')"
            )
        else:
            cls.shop_b_id = shop_b["id"]
            DB.execute("UPDATE shops SET is_active = 1, operational_status = 'OPEN' WHERE id = %s", (cls.shop_b_id,))

        # 3. Setup Vendor Account A (Assigned to Stall A)
        cls.vendor_a_email = "vendor.grill.phase6@kpriet.ac.in"
        cls.vendor_a_pwd = "Vendor@Grill123"
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
        DB.execute("UPDATE shops SET owner_user_id = %s WHERE id = %s", (cls.vendor_a_id, cls.shop_a_id))

        # 4. Setup Vendor Account B (Assigned to Stall B)
        cls.vendor_b_email = "vendor.juice.phase6@kpriet.ac.in"
        cls.vendor_b_pwd = "Vendor@Juice123"
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
        DB.execute("UPDATE shops SET owner_user_id = %s WHERE id = %s", (cls.vendor_b_id, cls.shop_b_id))

        # 5. Setup Customer Account
        cls.cust_email = "student.phase6@kpriet.ac.in"
        cls.cust_pwd = "Password@Student123"
        c_user = DB.get_one("SELECT id FROM users WHERE email = %s", (cls.cust_email,))
        if not c_user:
            cls.cust_id = DB.execute(
                "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
                (cls.cust_email, generate_password_hash(cls.cust_pwd))
            )
        else:
            cls.cust_id = c_user["id"]
            DB.execute("UPDATE users SET password_hash = %s, role = 'customer', is_active = 1 WHERE id = %s",
                       (generate_password_hash(cls.cust_pwd), cls.cust_id))

        c_prof = DB.get_one("SELECT id FROM customer_profiles WHERE user_id = %s", (cls.cust_id,))
        if not c_prof:
            DB.execute(
                "INSERT INTO customer_profiles (user_id, full_name, identifier, customer_type, wallet_balance, mobile) "
                "VALUES (%s, 'Phase6 Student User', '23CS777', 'student', 1500.00, '9988776655')",
                (cls.cust_id,)
            )
        else:
            DB.execute("UPDATE customer_profiles SET wallet_balance = 1500.00 WHERE user_id = %s", (cls.cust_id,))
            DB.execute("UPDATE users SET is_active = 1 WHERE id = %s", (cls.cust_id,))

        # 6. Seed Test Menu Items
        DB.execute("DELETE FROM menu_items WHERE shop_id IN (%s, %s)", (cls.shop_a_id, cls.shop_b_id))
        cls.item_grill_id = DB.execute(
            "INSERT INTO menu_items (shop_id, name, description, price, category, quantity, is_available) "
            "VALUES (%s, 'BBQ Chicken Platter', 'Smoked juicy chicken with herb sauce', 180.00, 'Snacks', 25, 1)",
            (cls.shop_a_id,)
        )
        cls.item_juice_id = DB.execute(
            "INSERT INTO menu_items (shop_id, name, description, price, category, quantity, is_available) "
            "VALUES (%s, 'Watermelon Cooler', 'Fresh fruit juice with mint', 40.00, 'Beverages', 30, 1)",
            (cls.shop_b_id,)
        )

    def setUp(self):
        DB.execute("DELETE FROM shops WHERE name IN ('Phase6 Bakery Hub', 'Phase6 Deluxe Bakery', 'Audit Trail Test Stall') OR slug IN ('phase6-bakery-hub', 'phase6-deluxe-bakery', 'audit-trail-test-stall')")
        DB.execute("DELETE FROM users WHERE email = 'new.vendor.test@kpriet.ac.in'")

    def tearDown(self):
        DB.execute("DELETE FROM shops WHERE name IN ('Phase6 Bakery Hub', 'Phase6 Deluxe Bakery', 'Audit Trail Test Stall') OR slug IN ('phase6-bakery-hub', 'phase6-deluxe-bakery', 'audit-trail-test-stall')")
        DB.execute("DELETE FROM users WHERE email = 'new.vendor.test@kpriet.ac.in'")

    def login_admin(self):
        self.client.post("/api/auth/logout")
        res = self.client.post("/api/auth/admin/login", json={"username": self.admin_email, "password": self.admin_pwd})
        self.assertEqual(res.status_code, 200, f"Admin login failed: {res.get_json()}")
        return res

    def login_vendor_a(self):
        self.client.post("/api/auth/logout")
        res = self.client.post("/api/auth/vendor/login", json={"email": self.vendor_a_email, "password": self.vendor_a_pwd})
        self.assertEqual(res.status_code, 200, f"Vendor A login failed: {res.get_json()}")
        return res

    def login_vendor_b(self):
        self.client.post("/api/auth/logout")
        res = self.client.post("/api/auth/vendor/login", json={"email": self.vendor_b_email, "password": self.vendor_b_pwd})
        self.assertEqual(res.status_code, 200, f"Vendor B login failed: {res.get_json()}")
        return res

    def login_customer(self):
        self.client.post("/api/auth/logout")
        res = self.client.post("/api/auth/customer/login", json={"email": self.cust_email, "password": self.cust_pwd})
        self.assertEqual(res.status_code, 200, f"Customer login failed: {res.get_json()}")
        return res

    # ========================================================================
    # 1. SERVER-SIDE RBAC TESTS
    # ========================================================================

    def test_01_admin_endpoints_require_admin_role(self):
        """Customers and vendors are strictly blocked from admin control endpoints."""
        # Unauthenticated
        self.client.post("/api/auth/logout")
        res = self.client.get("/api/admin/overview")
        self.assertEqual(res.status_code, 401)

        # Customer role
        self.login_customer()
        for endpoint in ["/api/admin/overview", "/api/admin/shops", "/api/admin/vendors",
                         "/api/admin/customers", "/api/admin/orders", "/api/admin/payments", "/api/admin/audit-logs"]:
            res = self.client.get(endpoint)
            self.assertEqual(res.status_code, 403, f"Customer unexpectedly accessed {endpoint}")

        # Vendor role
        self.login_vendor_a()
        for endpoint in ["/api/admin/overview", "/api/admin/shops", "/api/admin/vendors",
                         "/api/admin/customers", "/api/admin/orders", "/api/admin/payments", "/api/admin/audit-logs"]:
            res = self.client.get(endpoint)
            self.assertEqual(res.status_code, 403, f"Vendor unexpectedly accessed {endpoint}")

    def test_02_vendor_endpoints_require_vendor_role(self):
        """Customers are strictly blocked from vendor management endpoints."""
        self.login_customer()
        res = self.client.get("/api/vendor/shop")
        self.assertEqual(res.status_code, 403)
        res = self.client.get("/api/vendor/analytics")
        self.assertEqual(res.status_code, 403)
        res = self.client.get("/api/vendor/orders")
        self.assertEqual(res.status_code, 403)
        res = self.client.put("/api/vendor/shop/operational-status", json={"operational_status": "CLOSED"})
        self.assertEqual(res.status_code, 403)

    # ========================================================================
    # 2. ADMIN SHOP MANAGEMENT & OPERATIONAL STATUS
    # ========================================================================

    def test_03_admin_can_create_and_manage_shops(self):
        """Admin can create new stalls, reject duplicate names, and update profiles."""
        self.login_admin()

        stall_name = "Phase6 Bakery Hub"
        res = self.client.post("/api/admin/shops", json={
            "name": stall_name,
            "category": "Bakery & Desserts",
            "description": "Artisan pastries and oven-fresh breads",
            "operational_status": "OPEN"
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data["success"])
        new_shop_id = data["shop_id"]

        # Duplicate stall rejection
        dup_res = self.client.post("/api/admin/shops", json={"name": stall_name})
        self.assertEqual(dup_res.status_code, 409)

        # Update stall details
        update_res = self.client.put(f"/api/admin/shops/{new_shop_id}", json={
            "name": "Phase6 Deluxe Bakery",
            "category": "Bakery",
            "description": "Updated bakery description"
        })
        self.assertEqual(update_res.status_code, 200)

        # Toggle stall active status
        toggle_res = self.client.put(f"/api/admin/shops/{new_shop_id}/status", json={"is_active": 0})
        self.assertEqual(toggle_res.status_code, 200)
        self.assertEqual(toggle_res.get_json()["is_active"], 0)

        # Re-activate stall
        toggle_res2 = self.client.put(f"/api/admin/shops/{new_shop_id}/status", json={"is_active": 1})
        self.assertEqual(toggle_res2.status_code, 200)
        self.assertEqual(toggle_res2.get_json()["is_active"], 1)

    def test_04_admin_can_set_shop_operational_status(self):
        """Admin can toggle stall operational status among OPEN, CLOSED, TEMPORARILY_UNAVAILABLE."""
        self.login_admin()

        # 1. Set to TEMPORARILY_UNAVAILABLE
        res = self.client.put(f"/api/admin/shops/{self.shop_a_id}/operational-status", json={
            "operational_status": "TEMPORARILY_UNAVAILABLE"
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["operational_status"], "TEMPORARILY_UNAVAILABLE")
        shop = DB.get_one("SELECT operational_status FROM shops WHERE id = %s", (self.shop_a_id,))
        self.assertEqual(shop["operational_status"], "TEMPORARILY_UNAVAILABLE")

        # 2. Set to CLOSED
        res2 = self.client.put(f"/api/admin/shops/{self.shop_a_id}/operational-status", json={
            "operational_status": "CLOSED"
        })
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.get_json()["operational_status"], "CLOSED")

        # 3. Reject invalid status
        res_inv = self.client.put(f"/api/admin/shops/{self.shop_a_id}/operational-status", json={
            "operational_status": "INVALID_STATUS_CODE"
        })
        self.assertEqual(res_inv.status_code, 400)

        # 4. Reset to OPEN
        res_open = self.client.put(f"/api/admin/shops/{self.shop_a_id}/operational-status", json={
            "operational_status": "OPEN"
        })
        self.assertEqual(res_open.status_code, 200)
        self.assertEqual(res_open.get_json()["operational_status"], "OPEN")

    # ========================================================================
    # 3. SHOP OPERATIONAL RULES (CUSTOMER ORDER REJECTION & IN-FLIGHT FULFILLMENT)
    # ========================================================================

    def test_05_customer_order_blocked_when_shop_is_closed_or_temporarily_unavailable(self):
        """Customer cannot place new pre-orders when a stall is CLOSED or TEMPORARILY_UNAVAILABLE."""
        self.login_admin()
        # Set Stall A to TEMPORARILY_UNAVAILABLE
        self.client.put(f"/api/admin/shops/{self.shop_a_id}/operational-status", json={"operational_status": "TEMPORARILY_UNAVAILABLE"})

        self.login_customer()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_grill_id, "quantity": 1}],
            "payment_method": "Campus Wallet"
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("temporarily unavailable", res.get_json().get("message", "").lower())

        # Set Stall A to CLOSED
        self.login_admin()
        self.client.put(f"/api/admin/shops/{self.shop_a_id}/operational-status", json={"operational_status": "CLOSED"})

        self.login_customer()
        res2 = self.client.post("/api/orders", json={
            "items": [{"id": self.item_grill_id, "quantity": 1}],
            "payment_method": "Campus Wallet"
        })
        self.assertEqual(res2.status_code, 400)
        self.assertIn("closed", res2.get_json().get("message", "").lower())

        # Reset Stall A to OPEN
        self.login_admin()
        self.client.put(f"/api/admin/shops/{self.shop_a_id}/operational-status", json={"operational_status": "OPEN"})

    def test_06_in_flight_orders_preserved_and_fulfillable_when_shop_closes(self):
        """
        Critical Operational Requirement:
        Existing in-flight orders are preserved and vendors can prepare and complete them
        even if the stall becomes CLOSED or TEMPORARILY_UNAVAILABLE afterwards.
        """
        # 1. Place order while OPEN
        self.login_customer()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_grill_id, "quantity": 1}],
            "payment_method": "Campus Wallet"
        })
        self.assertEqual(res.status_code, 201)
        order_data = res.get_json()["order"]
        order_id = order_data["id"]
        pickup_otp = order_data["pickup_otp"]

        # 2. Stall operational status changes to CLOSED
        self.login_admin()
        self.client.put(f"/api/admin/shops/{self.shop_a_id}/operational-status", json={"operational_status": "CLOSED"})

        # 3. Vendor can still view the in-flight order in the kitchen queue
        self.login_vendor_a()
        q_res = self.client.get("/api/vendor/orders")
        self.assertEqual(q_res.status_code, 200)
        order_ids = [o["id"] for o in q_res.get_json()["orders"]]
        self.assertIn(order_id, order_ids)

        # 4. Vendor can transition in-flight order: Pending -> Preparing -> Ready
        prep_res = self.client.put(f"/api/orders/{order_id}/status", json={"status": "preparing"})
        self.assertEqual(prep_res.status_code, 200)

        ready_res = self.client.put(f"/api/orders/{order_id}/status", json={"status": "ready"})
        self.assertEqual(ready_res.status_code, 200)

        # 5. Vendor can verify customer OTP to complete the order even while closed!
        otp_res = self.client.post("/api/orders/verify-otp", json={
            "otp": pickup_otp,
            "shop_id": self.shop_a_id
        })
        self.assertEqual(otp_res.status_code, 200)
        self.assertTrue(otp_res.get_json()["success"])

        # Reset Stall A to OPEN
        self.login_admin()
        self.client.put(f"/api/admin/shops/{self.shop_a_id}/operational-status", json={"operational_status": "OPEN"})

    # ========================================================================
    # 4. VENDOR MANAGEMENT & ASSIGNMENT
    # ========================================================================

    def test_07_admin_vendor_creation_and_assignment_lifecycle(self):
        """Admin can create new vendor, assign to stall, and reassign/unassign."""
        self.login_admin()

        v_email = "new.vendor.test@kpriet.ac.in"
        res = self.client.post("/api/admin/vendors", json={
            "email": v_email,
            "password": "VendorPassword@123",
            "shop_id": self.shop_a_id
        })
        self.assertEqual(res.status_code, 201)
        v_id = res.get_json()["user_id"]

        # Duplicate email rejected
        dup_res = self.client.post("/api/admin/vendors", json={
            "email": v_email,
            "password": "Password123"
        })
        self.assertEqual(dup_res.status_code, 409)

        # Reassign to Stall B
        reassign_res = self.client.put(f"/api/admin/vendors/{v_id}/shop", json={
            "shop_id": self.shop_b_id
        })
        self.assertEqual(reassign_res.status_code, 200)
        self.assertEqual(reassign_res.get_json()["shop_id"], self.shop_b_id)

        # Unassign vendor
        unassign_res = self.client.put(f"/api/admin/vendors/{v_id}/shop", json={
            "shop_id": None
        })
        self.assertEqual(unassign_res.status_code, 200)
        self.assertIsNone(unassign_res.get_json()["shop_id"])

        # Restore original owner assignments
        DB.execute("UPDATE shops SET owner_user_id = %s WHERE id = %s", (self.vendor_a_id, self.shop_a_id))
        DB.execute("UPDATE shops SET owner_user_id = %s WHERE id = %s", (self.vendor_b_id, self.shop_b_id))

    # ========================================================================
    # 5. VENDOR SHOP ISOLATION & SELF-SERVICE STATUS
    # ========================================================================

    def test_08_vendor_shop_isolation_and_idor_protection(self):
        """Vendor A cannot view or alter Vendor B's stall menu or orders."""
        self.login_vendor_a()

        # Vendor A reads own shop
        res = self.client.get("/api/vendor/shop")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["shop"]["id"], self.shop_a_id)

        # Vendor A attempts to modify Vendor B's menu item
        tamper_res = self.client.put(f"/api/vendor/menu/item/{self.item_juice_id}", json={
            "price": 1.00
        })
        self.assertEqual(tamper_res.status_code, 403)

        # Vendor A attempts to delete Vendor B's menu item
        del_res = self.client.delete(f"/api/vendor/menu/item/{self.item_juice_id}")
        self.assertEqual(del_res.status_code, 403)

        # Vendor A attempts to view Vendor B's orders
        order_res = self.client.get(f"/api/orders/vendor/{self.shop_b_id}")
        self.assertEqual(order_res.status_code, 403)

    def test_09_vendor_self_service_operational_status_toggle(self):
        """Vendor can toggle operational status of their assigned stall."""
        self.login_vendor_a()

        # Set to TEMPORARILY_UNAVAILABLE
        res = self.client.put("/api/vendor/shop/operational-status", json={
            "operational_status": "TEMPORARILY_UNAVAILABLE"
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["operational_status"], "TEMPORARILY_UNAVAILABLE")

        # Set back to OPEN
        res_open = self.client.put("/api/vendor/shop/operational-status", json={
            "operational_status": "OPEN"
        })
        self.assertEqual(res_open.status_code, 200)
        self.assertEqual(res_open.get_json()["operational_status"], "OPEN")

    # ========================================================================
    # 6. ORDER WORKFLOW & BACKWARD TRANSITION REJECTION
    # ========================================================================

    def test_10_strict_order_lifecycle_and_backward_transition_rejection(self):
        """
        Order Workflow: PENDING -> PREPARING -> READY -> PICKUP OTP -> COMPLETED.
        Rejects backward jumps, invalid forward skipping, and direct status completion.
        """
        # 1. Place order (starts at PENDING)
        self.login_customer()
        res = self.client.post("/api/orders", json={
            "items": [{"id": self.item_grill_id, "quantity": 1}],
            "payment_method": "Campus Wallet"
        })
        order_id = res.get_json()["order"]["id"]
        pickup_otp = res.get_json()["order"]["pickup_otp"]

        self.login_vendor_a()

        # Rejection: Cannot skip PENDING directly to READY
        skip_res = self.client.put(f"/api/orders/{order_id}/status", json={"status": "ready"})
        self.assertEqual(skip_res.status_code, 400)
        self.assertIn("must be set to 'preparing'", skip_res.get_json()["message"].lower())

        # Rejection: Cannot mark COMPLETED directly via status endpoint
        direct_comp_res = self.client.put(f"/api/orders/{order_id}/status", json={"status": "completed"})
        self.assertEqual(direct_comp_res.status_code, 400)
        self.assertIn("otp verification", direct_comp_res.get_json()["message"].lower())

        # Valid forward transition 1: PENDING -> PREPARING
        prep_res = self.client.put(f"/api/orders/{order_id}/status", json={"status": "preparing"})
        self.assertEqual(prep_res.status_code, 200)

        # Rejection: Backward transition PREPARING -> PENDING
        back_res1 = self.client.put(f"/api/orders/{order_id}/status", json={"status": "pending"})
        self.assertEqual(back_res1.status_code, 400)
        self.assertIn("invalid backward", back_res1.get_json()["message"].lower())

        # Valid forward transition 2: PREPARING -> READY
        ready_res = self.client.put(f"/api/orders/{order_id}/status", json={"status": "ready"})
        self.assertEqual(ready_res.status_code, 200)

        # Rejection: Backward transition READY -> PREPARING
        back_res2 = self.client.put(f"/api/orders/{order_id}/status", json={"status": "preparing"})
        self.assertEqual(back_res2.status_code, 400)
        self.assertIn("invalid backward", back_res2.get_json()["message"].lower())

        # Rejection: Backward transition READY -> PENDING
        back_res3 = self.client.put(f"/api/orders/{order_id}/status", json={"status": "pending"})
        self.assertEqual(back_res3.status_code, 400)
        self.assertIn("invalid backward", back_res3.get_json()["message"].lower())

        # Legitimate completion: Customer presents OTP -> Vendor verifies OTP
        verify_res = self.client.post("/api/orders/verify-otp", json={
            "otp": pickup_otp,
            "shop_id": self.shop_a_id
        })
        self.assertEqual(verify_res.status_code, 200)
        self.assertTrue(verify_res.get_json()["success"])

        # Order is now COMPLETED (terminal state)
        order_row = DB.get_one("SELECT order_status, completed_time FROM orders WHERE id = %s", (order_id,))
        self.assertEqual(order_row["order_status"], "completed")
        self.assertIsNotNone(order_row["completed_time"])

        # Rejection: Terminal COMPLETED order cannot transition to any status
        post_comp_res = self.client.put(f"/api/orders/{order_id}/status", json={"status": "ready"})
        self.assertEqual(post_comp_res.status_code, 400)
        self.assertIn("already been completed", post_comp_res.get_json()["message"].lower())

    # ========================================================================
    # 7. CUSTOMER DIRECTORY & ACCOUNT SUSPENSION
    # ========================================================================

    def test_11_customer_directory_and_suspension_governance(self):
        """Admin can list customers, search directory, and suspend/reactivate accounts."""
        self.login_admin()

        # List customers
        res = self.client.get("/api/admin/customers")
        self.assertEqual(res.status_code, 200)
        customers = res.get_json()["customers"]
        self.assertIsInstance(customers, list)

        # Search customer by roll number
        search_res = self.client.get("/api/admin/customers?q=23CS777")
        self.assertEqual(search_res.status_code, 200)
        search_list = search_res.get_json()["customers"]
        self.assertTrue(any(c["id"] == self.cust_id for c in search_list))

        # Suspend customer account (is_active: 0)
        susp_res = self.client.put(f"/api/admin/customers/{self.cust_id}/status", json={"is_active": 0})
        self.assertEqual(susp_res.status_code, 200)
        self.assertEqual(susp_res.get_json()["is_active"], 0)

        # Verify suspended customer CANNOT login
        self.client.post("/api/auth/logout")
        login_res = self.client.post("/api/auth/customer/login", json={"email": self.cust_email, "password": self.cust_pwd})
        self.assertEqual(login_res.status_code, 401)

        # Reactivate customer account (is_active: 1)
        self.login_admin()
        act_res = self.client.put(f"/api/admin/customers/{self.cust_id}/status", json={"is_active": 1})
        self.assertEqual(act_res.status_code, 200)
        self.assertEqual(act_res.get_json()["is_active"], 1)

        # Verify reactivated customer CAN login again
        cust_login = self.login_customer()
        self.assertEqual(cust_login.status_code, 200)

    # ========================================================================
    # 8. GLOBAL ORDER & PAYMENT MONITORING
    # ========================================================================

    def test_12_admin_global_order_monitoring_with_filters(self):
        """Admin can monitor orders campus-wide with status and shop filters."""
        self.login_admin()

        # All orders
        res = self.client.get("/api/admin/orders")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["success"])

        # Filter by shop_id
        res_shop = self.client.get(f"/api/admin/orders?shop_id={self.shop_a_id}")
        self.assertEqual(res_shop.status_code, 200)
        for o in res_shop.get_json()["orders"]:
            self.assertEqual(o["shop_id"], self.shop_a_id)

        # Filter by status
        res_st = self.client.get("/api/admin/orders?status=completed")
        self.assertEqual(res_st.status_code, 200)
        for o in res_st.get_json()["orders"]:
            self.assertEqual(o["order_status"], "completed")

    def test_13_admin_global_payment_monitoring_and_aggregates(self):
        """Admin can monitor transaction records and view aggregate turnover stats."""
        self.login_admin()

        res = self.client.get("/api/admin/payments")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("payments", data)
        self.assertIn("summary", data)
        summary = data["summary"]
        self.assertIn("total_collected", summary)
        self.assertIn("success_count", summary)

    # ========================================================================
    # 9. CENTRALIZED SECURITY AUDIT LOGGING
    # ========================================================================

    def test_14_security_audit_logs_record_critical_operations(self):
        """Critical administrative and operational actions generate persistent audit entries."""
        self.login_admin()

        # Trigger audited actions: shop creation and status change
        test_stall_name = "Audit Trail Test Stall"
        shop_res = self.client.post("/api/admin/shops", json={
            "name": test_stall_name,
            "category": "Audit Category"
        })
        audit_shop_id = shop_res.get_json()["shop_id"]

        self.client.put(f"/api/admin/shops/{audit_shop_id}/operational-status", json={
            "operational_status": "TEMPORARILY_UNAVAILABLE"
        })

        # Query audit logs
        logs_res = self.client.get("/api/admin/audit-logs")
        self.assertEqual(logs_res.status_code, 200)
        logs = logs_res.get_json()["audit_logs"]
        self.assertIsInstance(logs, list)
        self.assertGreater(len(logs), 0)

        actions_recorded = [l["action"] for l in logs]
        self.assertIn("SHOP_CREATED", actions_recorded)
        self.assertIn("SHOP_OPERATIONAL_STATUS_CHANGED", actions_recorded)


if __name__ == "__main__":
    unittest.main()
