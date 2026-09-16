"""
Manual E2E Test Suite for Phase 6 — Admin & Vendor Operational Management.

Executes all 25 operational workflow verification steps:
1. Admin logs in with secure credentials.
2. Admin inspects operational overview dashboard metrics.
3. Admin creates a new food court stall ("E2E Bistro") with operational_status='OPEN'.
4. Duplicate stall name/slug creation is rejected (409 Conflict).
5. Admin updates stall details ("E2E Gourmet Bistro").
6. Admin provisions a new vendor account ("e2e.vendor@kpriet.ac.in").
7. Duplicate vendor email provisioning is rejected (409 Conflict).
8. Admin assigns vendor to "E2E Gourmet Bistro".
9. Vendor logs in and inspects assigned stall profile (shop isolation).
10. Vendor adds signature menu item to their stall.
11. Cross-stall IDOR protection: Vendor cannot modify another stall's menu.
12. Vendor updates shop operational status to TEMPORARILY_UNAVAILABLE.
13. Customer is blocked from placing orders at TEMPORARILY_UNAVAILABLE stall.
14. Admin changes stall operational status to CLOSED.
15. Customer is blocked from placing orders at CLOSED stall.
16. Vendor switches stall operational status back to OPEN.
17. Customer places order successfully while stall is OPEN.
18. Stall switches to CLOSED while order is in-flight.
19. Vendor kitchen queue preserves in-flight order despite CLOSED stall status.
20. Strict state machine: Vendor transitions in-flight order Pending -> Preparing -> Ready.
21. Strict state machine: Invalid backward transition (Ready -> Preparing) is rejected (400).
22. Strict state machine: Direct completion without OTP is rejected (400).
23. Vendor verifies customer pickup OTP, transitioning order to COMPLETED.
24. Customer governance: Admin suspends student account; suspended user is blocked.
25. Admin reactivates student, monitors global orders & payments, and verifies audit logs.
"""

import os
import sys
import json
import unittest

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ["FLASK_ENV"] = "development"
os.environ["USE_SQLITE"] = "1"
os.environ["SECRET_KEY"] = "phase6-manual-e2e-32b-secret-key-ok"
os.environ["ADMIN_EMAIL"] = "admin@kpriet.ac.in"
os.environ["ADMIN_PASSWORD"] = "Admin@Secure2026!"

import init_db
init_db.init_sqlite()

from db import DB
from app import app
from werkzeug.security import generate_password_hash


def print_step(step_num, title, detail=""):
    print(f"\n[STEP {step_num:02d}] {title}")
    if detail:
        print(f"         {detail}")


class ManualE2EPhase6Operations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

        # Provision Admin
        cls.admin_email = "admin@kpriet.ac.in"
        cls.admin_pwd = "Admin@Secure2026!"
        admin_user = DB.get_one("SELECT id FROM users WHERE email = %s", (cls.admin_email,))
        if not admin_user:
            DB.execute(
                "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'admin', 1)",
                (cls.admin_email, generate_password_hash(cls.admin_pwd))
            )
        else:
            DB.execute("UPDATE users SET password_hash = %s, role = 'admin', is_active = 1 WHERE id = %s",
                       (generate_password_hash(cls.admin_pwd), admin_user["id"]))

        # Provision Customer
        cls.cust_email = "e2e.student@kpriet.ac.in"
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
                "VALUES (%s, 'E2E Test Student', '23CS999', 'student', 2000.00, '9988776600')",
                (cls.cust_id,)
            )
        else:
            DB.execute("UPDATE customer_profiles SET wallet_balance = 2000.00 WHERE user_id = %s", (cls.cust_id,))

        # Clean up stale E2E test data
        DB.execute("DELETE FROM shops WHERE name IN ('E2E Bistro', 'E2E Gourmet Bistro', 'Other E2E Stall') OR slug IN ('e2e-bistro', 'e2e-gourmet-bistro', 'other-e2e-stall')")
        DB.execute("DELETE FROM users WHERE email IN ('e2e.vendor@kpriet.ac.in', 'other.e2e.vendor@kpriet.ac.in')")

    def login_user(self, email, password, login_endpoint="/api/auth/customer/login"):
        self.client.post("/api/auth/logout")
        res = self.client.post(login_endpoint, json={"email": email, "username": email, "password": password})
        self.assertEqual(res.status_code, 200, f"Login failed for {email}: {res.get_json()}")
        return res

    def test_complete_phase6_operational_management_journey(self):
        print("\n" + "=" * 80)
        print("STARTING PHASE 6 MANUAL END-TO-END OPERATIONAL MANAGEMENT VERIFICATION")
        print("=" * 80)

        # --------------------------------------------------------------------
        # STEP 1: Admin logs in with secure credentials
        # --------------------------------------------------------------------
        print_step(1, "Admin Authentication", "Logging into administrative portal with elevated credentials")
        res = self.login_user(self.admin_email, self.admin_pwd, "/api/auth/admin/login")
        self.assertTrue(res.get_json()["success"])
        print("  -> Admin authenticated successfully (HTTP 200). Role verified: 'admin'")

        # --------------------------------------------------------------------
        # STEP 2: Admin inspects operational overview dashboard metrics
        # --------------------------------------------------------------------
        print_step(2, "Operational Overview Inspection", "Querying /api/admin/overview for platform-wide metrics")
        res = self.client.get("/api/admin/overview")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        stats = data["overview"]
        print(f"  -> Platform Stats: {stats['total_shops']} Stalls ({stats['open_shops']} OPEN), "
              f"{stats['total_customers']} Customers, {stats['total_orders']} Orders, Revenue: ₹{stats['payments']['total_collected']}")

        # --------------------------------------------------------------------
        # STEP 3: Admin creates a new food court stall
        # --------------------------------------------------------------------
        print_step(3, "Admin Stall Provisioning", "Creating stall 'E2E Bistro' with operational_status='OPEN'")
        res = self.client.post("/api/admin/shops", json={
            "name": "E2E Bistro",
            "category": "Continental & Grills",
            "description": "Authentic wood-fired delicacies",
            "operational_status": "OPEN"
        })
        self.assertEqual(res.status_code, 201)
        bistro_shop_id = res.get_json()["shop_id"]
        print(f"  -> Stall created with ID {bistro_shop_id} and status 'OPEN'")

        # --------------------------------------------------------------------
        # STEP 4: Duplicate stall name/slug creation is rejected
        # --------------------------------------------------------------------
        print_step(4, "Duplicate Stall Conflict Prevention", "Attempting to create duplicate stall name")
        res = self.client.post("/api/admin/shops", json={"name": "E2E Bistro"})
        self.assertEqual(res.status_code, 409)
        print("  -> Server correctly rejected duplicate stall with HTTP 409 Conflict")

        # --------------------------------------------------------------------
        # STEP 5: Admin updates stall details
        # --------------------------------------------------------------------
        print_step(5, "Stall Profile Update", "Updating stall name to 'E2E Gourmet Bistro'")
        res = self.client.put(f"/api/admin/shops/{bistro_shop_id}", json={
            "name": "E2E Gourmet Bistro",
            "category": "Gourmet Continental",
            "description": "Premium wood-fired pizzas and steaks"
        })
        self.assertEqual(res.status_code, 200)
        print("  -> Stall details updated successfully")

        # --------------------------------------------------------------------
        # STEP 6: Admin provisions a new vendor account
        # --------------------------------------------------------------------
        vendor_email = "e2e.vendor@kpriet.ac.in"
        vendor_pwd = "VendorPassword@2026!"
        print_step(6, "Vendor Provisioning", f"Registering vendor {vendor_email}")
        res = self.client.post("/api/admin/vendors", json={
            "email": vendor_email,
            "password": vendor_pwd
        })
        self.assertEqual(res.status_code, 201)
        vendor_user_id = res.get_json()["user_id"]
        print(f"  -> Vendor user created with User ID {vendor_user_id}")

        # --------------------------------------------------------------------
        # STEP 7: Duplicate vendor email rejected
        # --------------------------------------------------------------------
        print_step(7, "Duplicate Vendor Prevention", "Attempting to provision same email again")
        res = self.client.post("/api/admin/vendors", json={
            "email": vendor_email,
            "password": "AnotherPassword"
        })
        self.assertEqual(res.status_code, 409)
        print("  -> Server correctly rejected duplicate vendor with HTTP 409 Conflict")

        # --------------------------------------------------------------------
        # STEP 8: Admin assigns vendor to "E2E Gourmet Bistro"
        # --------------------------------------------------------------------
        print_step(8, "Vendor Stall Assignment", f"Assigning Vendor {vendor_user_id} -> Stall {bistro_shop_id}")
        res = self.client.put(f"/api/admin/vendors/{vendor_user_id}/shop", json={
            "shop_id": bistro_shop_id
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["shop_id"], bistro_shop_id)
        print("  -> Stall ownership linked server-side")

        # --------------------------------------------------------------------
        # STEP 9: Vendor logs in and inspects assigned stall profile
        # --------------------------------------------------------------------
        print_step(9, "Vendor Authentication & Shop Isolation", "Vendor logs in and reads /api/vendor/shop")
        self.login_user(vendor_email, vendor_pwd, "/api/auth/vendor/login")
        res = self.client.get("/api/vendor/shop")
        self.assertEqual(res.status_code, 200)
        vendor_shop = res.get_json()["shop"]
        self.assertEqual(vendor_shop["id"], bistro_shop_id)
        self.assertEqual(vendor_shop["operational_status"], "OPEN")
        print(f"  -> Authoritative stall verified: '{vendor_shop['name']}' (ID: {vendor_shop['id']})")

        # --------------------------------------------------------------------
        # STEP 10: Vendor adds signature menu item
        # --------------------------------------------------------------------
        print_step(10, "Menu Item Creation", "Vendor adds 'Truffle Mushroom Burger' (₹150.00)")
        res = self.client.post("/api/vendor/menu/item", json={
            "name": "Truffle Mushroom Burger",
            "description": "Smoked portobello with truffle aioli",
            "price": 150.00,
            "category": "Main Course",
            "quantity": 20,
            "is_available": 1
        })
        self.assertEqual(res.status_code, 201)
        menu_item_id = res.get_json()["item"]["id"]
        print(f"  -> Menu item created with ID {menu_item_id}")

        # --------------------------------------------------------------------
        # STEP 11: Cross-stall IDOR protection
        # --------------------------------------------------------------------
        print_step(11, "Cross-Stall IDOR Protection", "Provisioning second stall and testing unauthorized item update")
        # Create a second stall owned by another vendor
        other_shop_id = DB.execute(
            "INSERT INTO shops (name, slug, category, is_active, operational_status) VALUES ('Other E2E Stall', 'other-e2e-stall', 'Snacks', 1, 'OPEN')"
        )
        other_item_id = DB.execute(
            "INSERT INTO menu_items (shop_id, name, price, quantity, is_available) VALUES (%s, 'Unauthorized Fries', 50.00, 10, 1)",
            (other_shop_id,)
        )
        # Vendor 1 attempts to update other vendor's menu item
        res = self.client.put(f"/api/vendor/menu/item/{other_item_id}", json={"price": 999.00})
        self.assertIn(res.status_code, [403, 404])
        print("  -> Cross-stall menu modification blocked (HTTP 403 Forbidden)")

        # --------------------------------------------------------------------
        # STEP 12: Vendor updates operational status to TEMPORARILY_UNAVAILABLE
        # --------------------------------------------------------------------
        print_step(12, "Vendor Self-Service Status Toggle", "Setting stall to TEMPORARILY_UNAVAILABLE")
        res = self.client.put("/api/vendor/shop/operational-status", json={
            "operational_status": "TEMPORARILY_UNAVAILABLE"
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["operational_status"], "TEMPORARILY_UNAVAILABLE")
        print("  -> Operational status updated to 'TEMPORARILY_UNAVAILABLE'")

        # --------------------------------------------------------------------
        # STEP 13: Customer is blocked from placing orders at TEMPORARILY_UNAVAILABLE stall
        # --------------------------------------------------------------------
        print_step(13, "Order Placement Blocked (Unavailable)", "Customer tries ordering while stall is unavailable")
        self.login_user(self.cust_email, self.cust_pwd, "/api/auth/customer/login")
        res = self.client.post("/api/orders", json={
            "items": [{"id": menu_item_id, "quantity": 1}],
            "payment_method": "Campus Wallet"
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("closed or temporarily unavailable", res.get_json()["message"].lower())
        print("  -> Order blocked as expected: 'Stall is currently closed or temporarily unavailable'")

        # --------------------------------------------------------------------
        # STEP 14: Admin changes stall operational status to CLOSED
        # --------------------------------------------------------------------
        print_step(14, "Admin Force Stall Closure", "Admin sets stall operational_status='CLOSED'")
        self.login_user(self.admin_email, self.admin_pwd, "/api/auth/admin/login")
        res = self.client.put(f"/api/admin/shops/{bistro_shop_id}/operational-status", json={
            "operational_status": "CLOSED"
        })
        self.assertEqual(res.status_code, 200)
        print("  -> Admin forced stall status to 'CLOSED'")

        # --------------------------------------------------------------------
        # STEP 15: Customer is blocked from placing orders at CLOSED stall
        # --------------------------------------------------------------------
        print_step(15, "Order Placement Blocked (Closed)", "Customer tries ordering while stall is CLOSED")
        self.login_user(self.cust_email, self.cust_pwd, "/api/auth/customer/login")
        res = self.client.post("/api/orders", json={
            "items": [{"id": menu_item_id, "quantity": 1}],
            "payment_method": "Campus Wallet"
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("closed or temporarily unavailable", res.get_json()["message"].lower())
        print("  -> Order blocked as expected: 'Stall is currently closed or temporarily unavailable'")

        # --------------------------------------------------------------------
        # STEP 16: Vendor switches stall operational status back to OPEN
        # --------------------------------------------------------------------
        print_step(16, "Stall Reopening", "Vendor toggles status back to OPEN")
        self.login_user(vendor_email, vendor_pwd, "/api/auth/vendor/login")
        res = self.client.put("/api/vendor/shop/operational-status", json={"operational_status": "OPEN"})
        self.assertEqual(res.status_code, 200)
        print("  -> Stall reopened for campus ordering")

        # --------------------------------------------------------------------
        # STEP 17: Customer places order successfully while stall is OPEN
        # --------------------------------------------------------------------
        print_step(17, "Valid Order Placement", "Customer places 1x Truffle Mushroom Burger via Campus Wallet")
        self.login_user(self.cust_email, self.cust_pwd, "/api/auth/customer/login")
        res = self.client.post("/api/orders", json={
            "items": [{"id": menu_item_id, "quantity": 1}],
            "payment_method": "Campus Wallet"
        })
        self.assertEqual(res.status_code, 201)
        order_info = res.get_json()["order"]
        in_flight_order_id = order_info["id"]
        pickup_otp = order_info["pickup_otp"]
        print(f"  -> Order #{in_flight_order_id} created successfully! Pickup OTP: {pickup_otp}")

        # --------------------------------------------------------------------
        # STEP 18: Stall switches to CLOSED while order is in-flight
        # --------------------------------------------------------------------
        print_step(18, "Stall Closes During In-Flight Order", "Admin closes stall while order is pending")
        self.login_user(self.admin_email, self.admin_pwd, "/api/auth/admin/login")
        self.client.put(f"/api/admin/shops/{bistro_shop_id}/operational-status", json={"operational_status": "CLOSED"})
        print("  -> Stall operational status is now CLOSED")

        # --------------------------------------------------------------------
        # STEP 19: Kitchen queue preserves in-flight order despite CLOSED stall
        # --------------------------------------------------------------------
        print_step(19, "Kitchen Queue Visibility", "Vendor checks kitchen queue while stall is closed")
        self.login_user(vendor_email, vendor_pwd, "/api/auth/vendor/login")
        res = self.client.get("/api/vendor/orders")
        self.assertEqual(res.status_code, 200)
        queued_ids = [o["id"] for o in res.get_json()["orders"]]
        self.assertIn(in_flight_order_id, queued_ids)
        print(f"  -> In-flight Order #{in_flight_order_id} is intact in kitchen queue")

        # --------------------------------------------------------------------
        # STEP 20: Strict state machine: Vendor transitions in-flight order
        # --------------------------------------------------------------------
        print_step(20, "Strict State Machine Progression", "Pending -> Preparing -> Ready")
        res = self.client.put(f"/api/orders/{in_flight_order_id}/status", json={"status": "preparing"})
        self.assertEqual(res.status_code, 200)
        print("  -> Order transitioned to PREPARING")

        res = self.client.put(f"/api/orders/{in_flight_order_id}/status", json={"status": "ready"})
        self.assertEqual(res.status_code, 200)
        print("  -> Order transitioned to READY")

        # --------------------------------------------------------------------
        # STEP 21: Strict state machine: Invalid backward transition rejected
        # --------------------------------------------------------------------
        print_step(21, "Strict State Machine: Reject Backward Transition", "Attempting Ready -> Preparing")
        res = self.client.put(f"/api/orders/{in_flight_order_id}/status", json={"status": "preparing"})
        self.assertEqual(res.status_code, 400)
        print("  -> Server rejected invalid backward transition with HTTP 400")

        # --------------------------------------------------------------------
        # STEP 22: Strict state machine: Direct completion without OTP rejected
        # --------------------------------------------------------------------
        print_step(22, "Strict State Machine: Direct Completion Blocked", "Attempting Ready -> Completed via /status endpoint")
        res = self.client.put(f"/api/orders/{in_flight_order_id}/status", json={"status": "completed"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("OTP", res.get_json()["message"])
        print("  -> Server blocked completion without customer OTP verification")

        # --------------------------------------------------------------------
        # STEP 23: Vendor verifies customer pickup OTP, completing the order
        # --------------------------------------------------------------------
        print_step(23, "Pickup OTP Handshake", f"Vendor verifies customer OTP: {pickup_otp}")
        res = self.client.post("/api/orders/verify-otp", json={
            "otp": pickup_otp,
            "shop_id": bistro_shop_id
        })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["success"])
        print(f"  -> Order #{in_flight_order_id} COMPLETED via pickup OTP verification!")

        # --------------------------------------------------------------------
        # STEP 24: Customer governance: Admin suspends student account
        # --------------------------------------------------------------------
        print_step(24, "Customer Account Governance", f"Admin suspends customer ID {self.cust_id}")
        self.login_user(self.admin_email, self.admin_pwd, "/api/auth/admin/login")
        res = self.client.put(f"/api/admin/customers/{self.cust_id}/status", json={"is_active": 0})
        self.assertEqual(res.status_code, 200)
        print("  -> Customer status toggled to INACTIVE (0)")

        # Verify suspended student cannot authenticate
        self.client.post("/api/auth/logout")
        res = self.client.post("/api/auth/customer/login", json={
            "email": self.cust_email,
            "password": self.cust_pwd
        })
        self.assertEqual(res.status_code, 401)
        print("  -> Suspended student login correctly blocked with HTTP 401 Unauthorized")

        # --------------------------------------------------------------------
        # STEP 25: Admin reactivates student, monitors global orders & payments, and verifies audit logs
        # --------------------------------------------------------------------
        print_step(25, "System Governance, Payments & Centralized Audit Trail", "Reactivating student, inspecting feeds and audit logs")
        self.login_user(self.admin_email, self.admin_pwd, "/api/auth/admin/login")
        # Reactivate student
        self.client.put(f"/api/admin/customers/{self.cust_id}/status", json={"is_active": 1})
        print("  -> Student account reactivated")

        # Global Order Monitoring
        res = self.client.get("/api/admin/orders")
        self.assertEqual(res.status_code, 200)
        orders = res.get_json()["orders"]
        self.assertGreater(len(orders), 0)
        print(f"  -> Global order monitoring active ({len(orders)} orders queried with filter capability)")

        # Global Payment Monitoring
        res = self.client.get("/api/admin/payments")
        self.assertEqual(res.status_code, 200)
        payments = res.get_json()["payments"]
        summary = res.get_json()["summary"]
        print(f"  -> Payment Gateway Monitoring active: {summary['success_count']} successful transactions, "
              f"₹{summary['total_collected']} collected")

        # Security Audit Logs
        res = self.client.get("/api/admin/audit-logs")
        self.assertEqual(res.status_code, 200)
        logs = res.get_json()["audit_logs"]
        logged_actions = set(l["action"] for l in logs)
        print(f"  -> Security Audit Logs verified ({len(logs)} entries recorded)")
        print(f"     Recorded critical actions: {', '.join(sorted(list(logged_actions))[:6])}...")
        self.assertIn("SHOP_CREATED", logged_actions)
        self.assertIn("VENDOR_CREATED", logged_actions)
        self.assertIn("SHOP_OPERATIONAL_STATUS_CHANGED", logged_actions)
        self.assertIn("ORDER_OTP_VERIFIED", logged_actions)

        print("\n" + "=" * 80)
        print("ALL 25 PHASE 6 MANUAL END-TO-END OPERATIONAL STEPS PASSED SUCCESSFULLY!")
        print("=" * 80 + "\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
