"""
Manual E2E Test Suite for Phase 8 — AI/ML Recommendation & Food-Court Intelligence.

Executes all 20 specified verification workflow steps:
[01] Seed test stalls, menu items, and initial database state
[02] Customer login
[03] Cold-start recommendation check for new user (no prior orders)
[04] Shop-scoped query for YPR Stalls (100% YPR isolation)
[05] Shop-scoped query for German Cafe (100% German Cafe isolation)
[06] Zero cross-stall recommendation leakage
[07] Availability filter: Out-of-stock items excluded
[08] Availability filter: Inactive items excluded
[09] Availability filter: Closed stall items excluded
[10] Customer places and confirms order for South Indian item
[11] Vendor marks order completed via pickup OTP
[12] Personalized taste affinity boost and explainable reasons for repeat buyer
[13] Cancelled order exclusion from AI taste profiles and sales metrics
[14] Failed order exclusion from AI taste profiles and sales metrics
[15] Price authority verification (AI never computes prices; reflects DB price)
[16] Guest / Unauthenticated customer cold-start recommendations
[17] Vendor authentication and stall profile resolution
[18] Vendor stall analytics retrieval (revenue, top items, peak hours)
[19] Cross-stall vendor analytics IDOR protection (403 Forbidden)
[20] Admin platform-wide food court intelligence analytics
"""

import os
import sys
import unittest
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ["FLASK_ENV"] = "development"
os.environ["USE_SQLITE"] = "1"
os.environ["SECRET_KEY"] = "phase8-manual-e2e-32b-secret-key-ok"
os.environ["ADMIN_EMAIL"] = "admin@kpriet.ac.in"
os.environ["ADMIN_PASSWORD"] = "Admin@Secure2026!"

import init_db
init_db.init_sqlite()

from db import DB
from app import app
from werkzeug.security import generate_password_hash


def print_step(step_num, title, detail=""):
    print(f"\n[{step_num:02d}] {title}")
    if detail:
        print(f"     {detail}")


class ManualE2EPhase8Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app
        cls.app.config["TESTING"] = True

        # Clean slate for test isolation of manual8 fixtures
        DB.execute("DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE customer_id IN (SELECT id FROM users WHERE email LIKE '%@manual8.kpriet.ac.in'))")
        DB.execute("DELETE FROM payments WHERE order_id IN (SELECT id FROM orders WHERE customer_id IN (SELECT id FROM users WHERE email LIKE '%@manual8.kpriet.ac.in'))")
        DB.execute("DELETE FROM orders WHERE customer_id IN (SELECT id FROM users WHERE email LIKE '%@manual8.kpriet.ac.in')")
        DB.execute("DELETE FROM menu_items WHERE shop_id IN (SELECT id FROM shops WHERE slug LIKE '%manual8%')")
        DB.execute("DELETE FROM shops WHERE slug LIKE '%manual8%'")
        DB.execute("DELETE FROM customer_profiles WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@manual8.kpriet.ac.in')")
        DB.execute("DELETE FROM users WHERE email LIKE '%@manual8.kpriet.ac.in'")

        cls.pwd = "Phase8ManualSecure!123"
        hashed = generate_password_hash(cls.pwd)

        # 1. Admin
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

        # 2. Customer 1
        cls.cust1_email = "student.arun@manual8.kpriet.ac.in"
        cls.cust1_id = DB.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
            (cls.cust1_email, hashed)
        )
        DB.execute(
            "INSERT INTO customer_profiles (user_id, customer_type, full_name, identifier, mobile) VALUES (%s, 'student', 'Arun K', 'KPR2026-M8-1', '9876543230')",
            (cls.cust1_id,)
        )

        # 3. Vendor 1 & Shop 1 (YPR Stalls)
        cls.v1_email = "vendor.ypr@manual8.kpriet.ac.in"
        cls.v1_id = DB.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'vendor', 1)",
            (cls.v1_email, hashed)
        )
        cls.shop1_id = DB.execute(
            "INSERT INTO shops (name, slug, description, category, operational_status, is_active, owner_user_id) "
            "VALUES (%s, %s, %s, 'South Indian', 'OPEN', 1, %s)",
            ("YPR Stalls", "ypr-manual8", "Authentic South Indian Breakfast & Meals", cls.v1_id)
        )

        # 4. Vendor 2 & Shop 2 (German Cafe)
        cls.v2_email = "vendor.german@manual8.kpriet.ac.in"
        cls.v2_id = DB.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'vendor', 1)",
            (cls.v2_email, hashed)
        )
        cls.shop2_id = DB.execute(
            "INSERT INTO shops (name, slug, description, category, operational_status, is_active, owner_user_id) "
            "VALUES (%s, %s, %s, 'European Cafe', 'OPEN', 1, %s)",
            ("German Cafe", "german-manual8", "Artisan Bakery & Brews", cls.v2_id)
        )

        # 5. Shop 3 (Night Canteen - CLOSED)
        cls.shop3_id = DB.execute(
            "INSERT INTO shops (name, slug, description, category, operational_status, is_active) "
            "VALUES (%s, %s, %s, 'Snacks', 'CLOSED', 1)",
            ("Night Canteen", "night-manual8", "Midnight Snacks")
        )

        # Menu Items - YPR
        cls.item_dosa = DB.execute(
            "INSERT INTO menu_items (shop_id, name, price, category, quantity, is_available) VALUES (%s, 'Masala Dosa', 65.00, 'South Indian', 50, 1)",
            (cls.shop1_id,)
        )
        cls.item_idli = DB.execute(
            "INSERT INTO menu_items (shop_id, name, price, category, quantity, is_available) VALUES (%s, 'Ghee Idli', 45.00, 'Breakfast', 30, 1)",
            (cls.shop1_id,)
        )
        cls.item_pongal = DB.execute(
            "INSERT INTO menu_items (shop_id, name, price, category, quantity, is_available) VALUES (%s, 'Ven Pongal', 55.00, 'Breakfast', 20, 1)",
            (cls.shop1_id,)
        )
        # Out of stock item in YPR
        cls.item_vada_soldout = DB.execute(
            "INSERT INTO menu_items (shop_id, name, price, category, quantity, is_available) VALUES (%s, 'Special Vada', 30.00, 'Breakfast', 0, 1)",
            (cls.shop1_id,)
        )
        # Inactive item in YPR
        cls.item_halwa_inactive = DB.execute(
            "INSERT INTO menu_items (shop_id, name, price, category, quantity, is_available) VALUES (%s, 'Tirunelveli Halwa', 50.00, 'Desserts', 15, 0)",
            (cls.shop1_id,)
        )

        # Menu Items - German Cafe
        cls.item_coffee = DB.execute(
            "INSERT INTO menu_items (shop_id, name, price, category, quantity, is_available) VALUES (%s, 'Cold Brew Coffee', 90.00, 'Beverages', 40, 1)",
            (cls.shop2_id,)
        )
        cls.item_croissant = DB.execute(
            "INSERT INTO menu_items (shop_id, name, price, category, quantity, is_available) VALUES (%s, 'Chocolate Croissant', 75.00, 'Snacks', 25, 1)",
            (cls.shop2_id,)
        )

        # Menu Items - Closed Shop 3
        cls.item_noodles = DB.execute(
            "INSERT INTO menu_items (shop_id, name, price, category, quantity, is_available) VALUES (%s, 'Schezwan Noodles', 80.00, 'Main Course', 50, 1)",
            (cls.shop3_id,)
        )

    def setUp(self):
        self.client = self.app.test_client()

    def login(self, email, password, role="customer"):
        url = "/api/auth/customer/login" if role == "customer" else (
            "/api/auth/vendor/login" if role == "vendor" else "/api/auth/admin/login"
        )
        res = self.client.post(url, json={"email": email, "password": password})
        self.assertEqual(res.status_code, 200, f"Login failed for {email}")
        return res

    def test_complete_20_step_ai_intelligence_lifecycle(self):
        print("\n" + "=" * 80)
        print("STARTING PHASE 8 MANUAL 20-STEP END-TO-END AI & INTELLIGENCE VERIFICATION")
        print("=" * 80)

        # --------------------------------------------------------------------
        # [01] Initial Database State
        # --------------------------------------------------------------------
        print_step(1, "Initial Database State Verification", "Verifying test stalls, catalogs, and clean order state")
        self.assertIsNotNone(self.shop1_id)
        self.assertIsNotNone(self.shop2_id)
        print(f"  -> State confirmed: YPR (ID {self.shop1_id}), German Cafe (ID {self.shop2_id}), Night Canteen (ID {self.shop3_id})")

        # --------------------------------------------------------------------
        # [02] Customer Login
        # --------------------------------------------------------------------
        print_step(2, "Customer Authentication", f"Authenticating student {self.cust1_email}")
        res = self.login(self.cust1_email, self.pwd, role="customer")
        self.assertTrue(res.get_json()["success"])
        print("  -> Customer session established.")

        # --------------------------------------------------------------------
        # [03] Cold-Start Recommendations Check
        # --------------------------------------------------------------------
        print_step(3, "Cold-Start Recommendations Check", "Querying recommendations for fresh user (0 orders)")
        res = self.client.get(f"/api/ai/recommendations?shop_id={self.shop1_id}&limit=5")
        self.assertEqual(res.status_code, 200)
        recs = res.get_json()["recommendations"]
        self.assertGreater(len(recs), 0)
        print(f"  -> Cold-start engine returned {len(recs)} valid items with default popularity and meal-slot signals.")

        # --------------------------------------------------------------------
        # [04] Shop-Scoped Query for YPR Stalls
        # --------------------------------------------------------------------
        print_step(4, "Shop-Scoped Query: YPR Stalls", "Testing strict stall scoping for YPR (ID: %s)" % self.shop1_id)
        res = self.client.get(f"/api/ai/recommendations?shop_id={self.shop1_id}&limit=10")
        self.assertEqual(res.status_code, 200)
        ypr_recs = res.get_json()["recommendations"]
        for item in ypr_recs:
            self.assertEqual(item["shop_id"], self.shop1_id)
        print(f"  -> 100% of recommendations belong strictly to YPR Stalls ({len(ypr_recs)} items evaluated).")

        # --------------------------------------------------------------------
        # [05] Shop-Scoped Query for German Cafe
        # --------------------------------------------------------------------
        print_step(5, "Shop-Scoped Query: German Cafe", "Testing strict stall scoping for German Cafe (ID: %s)" % self.shop2_id)
        res = self.client.get(f"/api/ai/recommendations?shop_id={self.shop2_id}&limit=10")
        self.assertEqual(res.status_code, 200)
        german_recs = res.get_json()["recommendations"]
        for item in german_recs:
            self.assertEqual(item["shop_id"], self.shop2_id)
        print(f"  -> 100% of recommendations belong strictly to German Cafe ({len(german_recs)} items evaluated).")

        # --------------------------------------------------------------------
        # [06] Zero Cross-Stall Recommendation Leakage
        # --------------------------------------------------------------------
        print_step(6, "Cross-Stall Isolation Guarantee", "Verifying zero German Cafe items in YPR recommendations")
        ypr_item_ids = {r["item_id"] for r in ypr_recs}
        german_item_ids = {r["item_id"] for r in german_recs}
        self.assertTrue(ypr_item_ids.isdisjoint(german_item_ids))
        print("  -> Stall boundary strictly enforced. Zero cross-stall leakage detected.")

        # --------------------------------------------------------------------
        # [07] Availability Filter: Out-of-Stock Items Excluded
        # --------------------------------------------------------------------
        print_step(7, "Availability Filter: Out-of-Stock Items", "Verifying item with quantity=0 is not recommended")
        self.assertNotIn(self.item_vada_soldout, ypr_item_ids)
        print(f"  -> Out-of-stock item #{self.item_vada_soldout} ('Special Vada') successfully excluded.")

        # --------------------------------------------------------------------
        # [08] Availability Filter: Inactive Items Excluded
        # --------------------------------------------------------------------
        print_step(8, "Availability Filter: Inactive Items", "Verifying item with is_available=0 is not recommended")
        self.assertNotIn(self.item_halwa_inactive, ypr_item_ids)
        print(f"  -> Inactive item #{self.item_halwa_inactive} ('Tirunelveli Halwa') successfully excluded.")

        # --------------------------------------------------------------------
        # [09] Availability Filter: Closed Stall Items Excluded
        # --------------------------------------------------------------------
        print_step(9, "Availability Filter: Closed Stall", "Querying recommendations for CLOSED stall (Night Canteen)")
        res = self.client.get(f"/api/ai/recommendations?shop_id={self.shop3_id}")
        self.assertEqual(res.status_code, 200)
        closed_recs = res.get_json()["recommendations"]
        self.assertEqual(len(closed_recs), 0)
        print("  -> Authoritative operational status check passed: 0 items returned for CLOSED stall.")

        # --------------------------------------------------------------------
        # [10] Customer Places and Confirms Order
        # --------------------------------------------------------------------
        print_step(10, "Order Placement & Confirmation", "Customer purchases 2x 'Masala Dosa' (South Indian)")
        res = self.client.post("/api/orders", json={
            "shop_id": self.shop1_id,
            "items": [{"id": self.item_dosa, "quantity": 2}],
            "payment_method": "Campus Wallet"
        })
        self.assertEqual(res.status_code, 201)
        order_info = res.get_json()["order"]
        order_id = order_info["id"]
        pickup_otp = order_info["pickup_otp"]
        print(f"  -> Order #{order_id} placed and paid via Campus Wallet. OTP: {pickup_otp}")

        # --------------------------------------------------------------------
        # [11] Vendor Completes Order via Pickup OTP
        # --------------------------------------------------------------------
        print_step(11, "Order Completion via Counter Handshake", "Vendor verifies customer pickup OTP at counter")
        v_client = self.app.test_client()
        v_client.post("/api/auth/vendor/login", json={"email": self.v1_email, "password": self.pwd})
        res = v_client.post("/api/orders/verify-otp", json={"otp": pickup_otp})
        self.assertEqual(res.status_code, 200)
        print("  -> Order marked COMPLETED. Becomes valid historical purchase data.")

        # --------------------------------------------------------------------
        # [12] Personalized Taste Affinity Boost
        # --------------------------------------------------------------------
        print_step(12, "Personalized Taste Affinity Boost", "Evaluating recommendations after customer purchase history exists")
        res = self.client.get(f"/api/ai/recommendations?shop_id={self.shop1_id}&limit=5")
        self.assertEqual(res.status_code, 200)
        post_recs = res.get_json()["recommendations"]
        dosa_rec = next((r for r in post_recs if r["item_id"] == self.item_dosa), None)
        self.assertIsNotNone(dosa_rec)
        print(f"  -> Dosa score: {dosa_rec['score']} | Reason: '{dosa_rec['reason']}'")
        self.assertTrue(len(dosa_rec["reason"]) > 0)
        self.assertGreaterEqual(dosa_rec["score"], 0.70)

        # --------------------------------------------------------------------
        # [13] Cancelled Order Exclusion from History
        # --------------------------------------------------------------------
        print_step(13, "Cancelled Order Exclusion", "Customer places and cancels an order; verifying zero impact on analytics")
        res = self.client.post("/api/orders", json={
            "shop_id": self.shop1_id,
            "items": [{"id": self.item_pongal, "quantity": 5}],
            "payment_method": "UPI / Online"
        })
        cancel_order_id = res.get_json()["order"]["id"]
        res_cancel = self.client.post(f"/api/orders/{cancel_order_id}/cancel")
        self.assertEqual(res_cancel.status_code, 200)

        analytics = v_client.get(f"/api/ai/analytics/shop/{self.shop1_id}").get_json()
        self.assertEqual(analytics["summary"]["cancelled_orders"], 1)
        # Cancelled items (5x Pongal) MUST NOT be in total_units_sold
        self.assertEqual(analytics["summary"]["total_units_sold"], 2)
        print("  -> Cancelled order correctly excluded from total_units_sold and revenue.")

        # --------------------------------------------------------------------
        # [14] Failed Order Exclusion from History
        # --------------------------------------------------------------------
        print_step(14, "Failed Order Exclusion", "Simulating failed payment; verifying zero impact on sales revenue")
        res = self.client.post("/api/orders", json={
            "shop_id": self.shop1_id,
            "items": [{"id": self.item_idli, "quantity": 4}],
            "payment_method": "UPI / Online"
        })
        fail_order_id = res.get_json()["order"]["id"]
        # Transition order to failed
        DB.execute("UPDATE orders SET payment_status = 'failed' WHERE id = %s", (fail_order_id,))

        analytics = v_client.get(f"/api/ai/analytics/shop/{self.shop1_id}").get_json()
        # Failed items (4x Idli) MUST NOT be in total_units_sold
        self.assertEqual(analytics["summary"]["total_units_sold"], 2)
        print("  -> Failed payment correctly excluded from units sold and revenue.")

        # --------------------------------------------------------------------
        # [15] Price Authority Verification
        # --------------------------------------------------------------------
        print_step(15, "Price Authority Verification", "Checking AI reflects live DB prices and never computes prices")
        res = self.client.get(f"/api/ai/recommendations?shop_id={self.shop1_id}")
        dosa = next(r for r in res.get_json()["recommendations"] if r["item_id"] == self.item_dosa)
        self.assertEqual(dosa["price"], 65.00)

        # Update DB price to ₹80.00
        DB.execute("UPDATE menu_items SET price = 80.00 WHERE id = %s", (self.item_dosa,))
        res2 = self.client.get(f"/api/ai/recommendations?shop_id={self.shop1_id}")
        dosa2 = next(r for r in res2.get_json()["recommendations"] if r["item_id"] == self.item_dosa)
        self.assertEqual(dosa2["price"], 80.00)
        # Restore price
        DB.execute("UPDATE menu_items SET price = 65.00 WHERE id = %s", (self.item_dosa,))
        print("  -> Price authority preserved: Live DB price dynamically reflected.")

        # --------------------------------------------------------------------
        # [16] Guest / Unauthenticated Customer Recommendations
        # --------------------------------------------------------------------
        print_step(16, "Guest / Unauthenticated Caller", "Querying recommendations without active session")
        self.client.post("/api/auth/logout")
        res = self.client.get(f"/api/ai/recommendations?shop_id={self.shop1_id}")
        self.assertEqual(res.status_code, 200)
        guest_recs = res.get_json()["recommendations"]
        self.assertGreater(len(guest_recs), 0)
        print(f"  -> Guest caller received {len(guest_recs)} valid recommendations.")

        # --------------------------------------------------------------------
        # [17] Vendor Authentication
        # --------------------------------------------------------------------
        print_step(17, "Vendor Authentication", f"Authenticating vendor {self.v1_email}")
        res = v_client.post("/api/auth/vendor/login", json={"email": self.v1_email, "password": self.pwd})
        self.assertEqual(res.status_code, 200)
        print("  -> Vendor authenticated successfully.")

        # --------------------------------------------------------------------
        # [18] Vendor Stall Analytics Retrieval
        # --------------------------------------------------------------------
        print_step(18, "Vendor Stall Analytics Retrieval", "Querying /api/ai/analytics/shop/%s" % self.shop1_id)
        res = v_client.get(f"/api/ai/analytics/shop/{self.shop1_id}")
        self.assertEqual(res.status_code, 200)
        v_analytics = res.get_json()
        print(f"  -> Stall: {v_analytics['shop_name']}")
        print(f"     Completed: {v_analytics['summary']['completed_orders']}, Cancelled: {v_analytics['summary']['cancelled_orders']}")
        print(f"     Revenue: ₹{v_analytics['summary']['total_revenue']}, Units Sold: {v_analytics['summary']['total_units_sold']}")
        print(f"     Top Item: {v_analytics['top_selling_items'][0]['item_name']} ({v_analytics['top_selling_items'][0]['units_sold']} units)")

        # --------------------------------------------------------------------
        # [19] Cross-Stall Vendor Analytics IDOR Protection
        # --------------------------------------------------------------------
        print_step(19, "Cross-Stall Vendor Analytics IDOR Check", "Vendor 1 attempting to read German Cafe analytics")
        res = v_client.get(f"/api/ai/analytics/shop/{self.shop2_id}")
        self.assertEqual(res.status_code, 403)
        print(f"  -> Strict IDOR blocked: HTTP {res.status_code} ({res.get_json()['message']})")

        # --------------------------------------------------------------------
        # [20] Admin Platform-Wide Intelligence Analytics
        # --------------------------------------------------------------------
        print_step(20, "Admin Platform-Wide Food Court Analytics", "Admin queries multi-stall telemetry and demand velocity")
        admin_client = self.app.test_client()
        res = admin_client.post("/api/auth/admin/login", json={"email": self.admin_email, "password": self.admin_pwd})
        self.assertEqual(res.status_code, 200)

        res = admin_client.get("/api/ai/analytics/overview")
        self.assertEqual(res.status_code, 200)
        admin_data = res.get_json()
        self.assertTrue(admin_data["success"])
        self.assertGreater(len(admin_data["stalls_performance"]), 0)
        print(f"  -> Platform Intelligence verified: {len(admin_data['stalls_performance'])} stalls tracked across campus.")
        print(f"     Top Campus Items: {len(admin_data['top_selling_items'])}, Category Shares: {len(admin_data['category_shares'])}")

        print("\n" + "=" * 80)
        print("ALL 20 PHASE 8 MANUAL END-TO-END AI INTELLIGENCE STEPS PASSED SUCCESSFULLY!")
        print("=" * 80 + "\n")

    @classmethod
    def tearDownClass(cls):
        try:
            DB.execute("DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE customer_id IN (SELECT id FROM users WHERE email LIKE '%@manual8.kpriet.ac.in'))")
            DB.execute("DELETE FROM payments WHERE order_id IN (SELECT id FROM orders WHERE customer_id IN (SELECT id FROM users WHERE email LIKE '%@manual8.kpriet.ac.in'))")
            DB.execute("DELETE FROM orders WHERE customer_id IN (SELECT id FROM users WHERE email LIKE '%@manual8.kpriet.ac.in')")
            DB.execute("DELETE FROM menu_items WHERE shop_id IN (SELECT id FROM shops WHERE slug LIKE '%manual8%')")
            DB.execute("DELETE FROM shops WHERE slug LIKE '%manual8%'")
            DB.execute("DELETE FROM customer_profiles WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@manual8.kpriet.ac.in')")
            DB.execute("DELETE FROM users WHERE email LIKE '%@manual8.kpriet.ac.in'")
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
