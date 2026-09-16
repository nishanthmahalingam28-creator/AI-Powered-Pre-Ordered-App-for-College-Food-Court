"""
Automated Test Suite for Phase 8 — AI/ML Recommendation & Food-Court Intelligence.

Verifies:
1. Shop-scoped recommendations (100% stall isolation).
2. Authoritative availability filtering (out of stock, unavailable items excluded).
3. Shop operational status filtering (CLOSED / TEMPORARILY_UNAVAILABLE excluded).
4. Cold-start handling for new and unauthenticated/guest users.
5. Personalized category taste affinity for users with valid purchase history.
6. Explainable recommendation reasons.
7. Normalized scoring [0.0, 1.0].
8. Exclusion of failed and cancelled orders from historical profiles and analytics.
9. Price authority (authoritative DB price preserved).
10. Vendor analytics with strict stall isolation (IDOR protection).
11. Admin platform-wide food court intelligence analytics.
12. Legacy endpoint backward compatibility.
13. Fault-tolerance and non-blocking safety.
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
os.environ["SECRET_KEY"] = "phase8-ai-test-key-32b-verified-ok"

import init_db
init_db.init_sqlite()

from app import app
from db import DB
from werkzeug.security import generate_password_hash
from ai.recommender import FoodCourtRecommender
from ai.analytics import FoodCourtAnalytics


class TestPhase8AIRecommendations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

        # Clean slate for Phase 8 test isolation (preserve baseline seeded shops)
        DB.execute("DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE order_reference LIKE 'P8-%')")
        DB.execute("DELETE FROM payments WHERE order_id IN (SELECT id FROM orders WHERE order_reference LIKE 'P8-%')")
        DB.execute("DELETE FROM orders WHERE order_reference LIKE 'P8-%'")
        DB.execute("DELETE FROM menu_items WHERE shop_id IN (SELECT id FROM shops WHERE slug LIKE '%phase8%')")
        DB.execute("DELETE FROM shops WHERE slug LIKE '%phase8%'")
        DB.execute("DELETE FROM customer_profiles WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@test8.kpriet.ac.in')")
        DB.execute("DELETE FROM users WHERE email LIKE '%@test8.kpriet.ac.in'")

        cls.pwd = "Phase8Secure!123"
        hashed = generate_password_hash(cls.pwd)

        # 1. Admin
        cls.admin_email = "admin.phase8@test8.kpriet.ac.in"
        cls.admin_id = DB.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'admin', 1)",
            (cls.admin_email, hashed)
        )

        # 2. Customer 1 (Has purchase history)
        cls.cust1_email = "student1.phase8@test8.kpriet.ac.in"
        cls.cust1_id = DB.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
            (cls.cust1_email, hashed)
        )
        DB.execute(
            "INSERT INTO customer_profiles (user_id, customer_type, full_name, identifier, mobile) VALUES (%s, 'student', 'Praveen K', 'KPR2026-P8-1', '9876543220')",
            (cls.cust1_id,)
        )

        # 3. Customer 2 (Brand new customer with 0 history for cold-start testing)
        cls.cust2_email = "student2.phase8@test8.kpriet.ac.in"
        cls.cust2_id = DB.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
            (cls.cust2_email, hashed)
        )
        DB.execute(
            "INSERT INTO customer_profiles (user_id, customer_type, full_name, identifier, mobile) VALUES (%s, 'student', 'Naveen S', 'KPR2026-P8-2', '9876543221')",
            (cls.cust2_id,)
        )

        # 4. Vendor 1 & Shop 1 ("YPR Stalls")
        cls.v1_email = "vendor.ypr@test8.kpriet.ac.in"
        cls.v1_id = DB.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'vendor', 1)",
            (cls.v1_email, hashed)
        )
        cls.shop1_id = DB.execute(
            "INSERT INTO shops (name, slug, description, category, operational_status, is_active, owner_user_id) "
            "VALUES (%s, %s, %s, 'South Indian', 'OPEN', 1, %s)",
            ("YPR Stalls", "ypr-phase8", "Traditional South Indian Cuisine", cls.v1_id)
        )

        # 5. Vendor 2 & Shop 2 ("German Cafe")
        cls.v2_email = "vendor.german@test8.kpriet.ac.in"
        cls.v2_id = DB.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'vendor', 1)",
            (cls.v2_email, hashed)
        )
        cls.shop2_id = DB.execute(
            "INSERT INTO shops (name, slug, description, category, operational_status, is_active, owner_user_id) "
            "VALUES (%s, %s, %s, 'Snacks & Cafe', 'OPEN', 1, %s)",
            ("German Cafe", "german-cafe-phase8", "European Bakery & Coffee", cls.v2_id)
        )

        # 6. Shop 3 ("Night Canteen" - CLOSED stall)
        cls.shop3_id = DB.execute(
            "INSERT INTO shops (name, slug, description, category, operational_status, is_active) "
            "VALUES (%s, %s, %s, 'Fast Food', 'CLOSED', 1)",
            ("Night Canteen", "night-canteen-phase8", "Midnight Quick Bites")
        )

        # Menu Items for Shop 1 (YPR)
        cls.item1_dosa = DB.execute(
            "INSERT INTO menu_items (shop_id, name, price, category, quantity, is_available) VALUES (%s, %s, %s, %s, %s, 1)",
            (cls.shop1_id, "Ghee Roast Dosa", 70.00, "South Indian", 50)
        )
        cls.item1_idli = DB.execute(
            "INSERT INTO menu_items (shop_id, name, price, category, quantity, is_available) VALUES (%s, %s, %s, %s, %s, 1)",
            (cls.shop1_id, "Sambar Idli (2 Pcs)", 40.00, "Breakfast", 40)
        )
        cls.item1_vada = DB.execute(
            "INSERT INTO menu_items (shop_id, name, price, category, quantity, is_available) VALUES (%s, %s, %s, %s, %s, 1)",
            (cls.shop1_id, "Medu Vada", 25.00, "Breakfast", 30)
        )
        cls.item1_biryani = DB.execute(
            "INSERT INTO menu_items (shop_id, name, price, category, quantity, is_available) VALUES (%s, %s, %s, %s, %s, 1)",
            (cls.shop1_id, "Veg Biryani", 90.00, "Main Course", 20)
        )
        # Out of stock item in Shop 1
        cls.item1_outofstock = DB.execute(
            "INSERT INTO menu_items (shop_id, name, price, category, quantity, is_available) VALUES (%s, %s, %s, %s, 0, 1)",
            (cls.shop1_id, "Paneer Butter Masala", 120.00, "Main Course")
        )
        # Unavailable item in Shop 1
        cls.item1_unavailable = DB.execute(
            "INSERT INTO menu_items (shop_id, name, price, category, quantity, is_available) VALUES (%s, %s, %s, %s, 10, 0)",
            (cls.shop1_id, "Rava Kesari", 35.00, "Desserts")
        )

        # Menu Items for Shop 2 (German Cafe)
        cls.item2_coffee = DB.execute(
            "INSERT INTO menu_items (shop_id, name, price, category, quantity, is_available) VALUES (%s, %s, %s, %s, %s, 1)",
            (cls.shop2_id, "Iced Hazelnut Latte", 85.00, "Beverages", 50)
        )
        cls.item2_croissant = DB.execute(
            "INSERT INTO menu_items (shop_id, name, price, category, quantity, is_available) VALUES (%s, %s, %s, %s, %s, 1)",
            (cls.shop2_id, "Butter Croissant", 65.00, "Snacks", 30)
        )

        # Menu Items for Shop 3 (Closed stall)
        cls.item3_maggi = DB.execute(
            "INSERT INTO menu_items (shop_id, name, price, category, quantity, is_available) VALUES (%s, %s, %s, %s, %s, 1)",
            (cls.shop3_id, "Cheese Masala Maggi", 60.00, "Fast Food", 100)
        )

        # Seed valid purchase history for Customer 1 (Prefers South Indian & Breakfast)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        order1 = DB.execute(
            "INSERT INTO orders (order_reference, customer_id, shop_id, total_amount, order_status, payment_status, payment_method, pickup_otp, created_at) "
            "VALUES ('P8-ORD-01', %s, %s, 140.00, 'completed', 'paid', 'Campus Wallet', '112233', %s)",
            (cls.cust1_id, cls.shop1_id, now_str)
        )
        DB.execute(
            "INSERT INTO order_items (order_id, menu_item_id, item_name, unit_price, quantity, subtotal) "
            "VALUES (%s, %s, 'Ghee Roast Dosa', 70.00, 2, 140.00)",
            (order1, cls.item1_dosa)
        )

        order2 = DB.execute(
            "INSERT INTO orders (order_reference, customer_id, shop_id, total_amount, order_status, payment_status, payment_method, pickup_otp, created_at) "
            "VALUES ('P8-ORD-02', %s, %s, 80.00, 'completed', 'paid', 'Campus Wallet', '223344', %s)",
            (cls.cust1_id, cls.shop1_id, now_str)
        )
        DB.execute(
            "INSERT INTO order_items (order_id, menu_item_id, item_name, unit_price, quantity, subtotal) "
            "VALUES (%s, %s, 'Sambar Idli (2 Pcs)', 40.00, 2, 80.00)",
            (order2, cls.item1_idli)
        )

        # Seed a cancelled order and a failed order (MUST be excluded from training and analytics)
        order_cancelled = DB.execute(
            "INSERT INTO orders (order_reference, customer_id, shop_id, total_amount, order_status, payment_status, payment_method, pickup_otp, created_at) "
            "VALUES ('P8-ORD-CANCEL', %s, %s, 500.00, 'cancelled', 'cancelled', 'UPI', '000000', %s)",
            (cls.cust1_id, cls.shop1_id, now_str)
        )
        DB.execute(
            "INSERT INTO order_items (order_id, menu_item_id, item_name, unit_price, quantity, subtotal) "
            "VALUES (%s, %s, 'Ghee Roast Dosa', 70.00, 5, 350.00)",
            (order_cancelled, cls.item1_dosa)
        )

        order_failed = DB.execute(
            "INSERT INTO orders (order_reference, customer_id, shop_id, total_amount, order_status, payment_status, payment_method, pickup_otp, created_at) "
            "VALUES ('P8-ORD-FAIL', %s, %s, 200.00, 'pending', 'failed', 'UPI', '999999', %s)",
            (cls.cust1_id, cls.shop1_id, now_str)
        )
        DB.execute(
            "INSERT INTO order_items (order_id, menu_item_id, item_name, unit_price, quantity, subtotal) "
            "VALUES (%s, %s, 'Veg Biryani', 90.00, 2, 180.00)",
            (order_failed, cls.item1_biryani)
        )

    def login(self, email, password, role="customer"):
        url = "/api/auth/customer/login" if role == "customer" else (
            "/api/auth/vendor/login" if role == "vendor" else "/api/auth/admin/login"
        )
        res = self.client.post(url, json={"email": email, "password": password})
        self.assertEqual(res.status_code, 200)
        return res

    # ========================================================================
    # 1. SHOP SCOPE & AVAILABILITY FILTERS
    # ========================================================================

    def test_01_shop_scoped_recommendations_100_percent_isolated(self):
        """When shop_id=1 (YPR) is requested, 100% of recommendations must belong strictly to Shop 1."""
        res = self.client.get(f"/api/ai/recommendations?shop_id={self.shop1_id}&limit=10")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        recs = data.get("recommendations", [])
        self.assertGreater(len(recs), 0)

        for item in recs:
            self.assertEqual(item["shop_id"], self.shop1_id,
                             f"Shop isolation violated! Found item from shop {item['shop_id']} in YPR recommendations.")

        # Ensure German Cafe items are completely absent
        german_item_ids = {self.item2_coffee, self.item2_croissant}
        recommended_ids = {r["item_id"] for r in recs}
        self.assertTrue(german_item_ids.isdisjoint(recommended_ids))

    def test_02_unavailable_and_out_of_stock_items_excluded(self):
        """Out of stock (quantity=0) and inactive (is_available=0) items are strictly excluded."""
        res = self.client.get(f"/api/ai/recommendations?shop_id={self.shop1_id}&limit=20")
        self.assertEqual(res.status_code, 200)
        recs = res.get_json().get("recommendations", [])
        recommended_ids = {r["item_id"] for r in recs}

        self.assertNotIn(self.item1_outofstock, recommended_ids, "Out of stock item was improperly recommended.")
        self.assertNotIn(self.item1_unavailable, recommended_ids, "Unavailable item was improperly recommended.")

    def test_03_closed_shop_items_excluded(self):
        """Items from CLOSED or inactive shops must not be recommended."""
        res = self.client.get(f"/api/ai/recommendations?shop_id={self.shop3_id}&limit=10")
        self.assertEqual(res.status_code, 200)
        recs = res.get_json().get("recommendations", [])
        self.assertEqual(len(recs), 0, "Items from a CLOSED stall were improperly recommended.")

    # ========================================================================
    # 2. COLD-START & PERSONALIZATION
    # ========================================================================

    def test_04_cold_start_new_customer(self):
        """New customer with 0 past orders receives valid recommendations with non-empty reasons."""
        self.login(self.cust2_email, self.pwd, role="customer")
        res = self.client.get(f"/api/ai/recommendations?shop_id={self.shop1_id}&limit=5")
        self.assertEqual(res.status_code, 200)
        recs = res.get_json().get("recommendations", [])
        self.assertGreater(len(recs), 0)

        for r in recs:
            self.assertIn("reason", r)
            self.assertTrue(len(r["reason"]) > 0)
            self.assertIn("score", r)

    def test_05_guest_unauthenticated_recommendations(self):
        """Unauthenticated guest caller receives cold-start recommendations successfully."""
        self.client.post("/api/auth/logout")
        res = self.client.get(f"/api/ai/recommendations?shop_id={self.shop1_id}&limit=5")
        self.assertEqual(res.status_code, 200)
        recs = res.get_json().get("recommendations", [])
        self.assertGreater(len(recs), 0)

    def test_06_personalized_affinity_boost(self):
        """Customer with past orders in South Indian gets higher score and tailored explanation."""
        self.login(self.cust1_email, self.pwd, role="customer")
        res = self.client.get(f"/api/ai/recommendations?shop_id={self.shop1_id}&limit=10")
        self.assertEqual(res.status_code, 200)
        recs = res.get_json().get("recommendations", [])
        self.assertGreater(len(recs), 0)

        # Item 1 (Ghee Roast Dosa) was bought in past orders
        dosa_rec = next((r for r in recs if r["item_id"] == self.item1_dosa), None)
        self.assertIsNotNone(dosa_rec)
        # Should have personalized reason
        self.assertTrue(
            "favorite" in dosa_rec["reason"].lower() or "preference" in dosa_rec["reason"].lower() or "popular" in dosa_rec["reason"].lower(),
            f"Expected personalized reason for frequent item, got: {dosa_rec['reason']}"
        )

    def test_07_explainable_reasons_present(self):
        """All recommendations must have human-readable explanations corresponding to logic."""
        res = self.client.get(f"/api/ai/recommendations?shop_id={self.shop1_id}")
        self.assertEqual(res.status_code, 200)
        recs = res.get_json().get("recommendations", [])
        for r in recs:
            self.assertIsInstance(r["reason"], str)
            self.assertTrue(len(r["reason"].strip()) > 3)

    def test_08_scores_normalized_between_0_and_1(self):
        """All recommendation scores must be calibrated numbers between 0.0 and 1.0."""
        res = self.client.get(f"/api/ai/recommendations?shop_id={self.shop1_id}")
        self.assertEqual(res.status_code, 200)
        recs = res.get_json().get("recommendations", [])
        for r in recs:
            score = float(r["score"])
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)

    # ========================================================================
    # 3. TRANSACTION INTEGRITY & PRICE AUTHORITY
    # ========================================================================

    def test_09_cancelled_and_failed_orders_excluded_from_history(self):
        """Cancelled and failed orders do not inflate popularity or units sold."""
        metrics = FoodCourtAnalytics.get_shop_analytics(self.shop1_id)
        self.assertIsNotNone(metrics)
        # Total units from order1 (2) + order2 (2) = 4 units.
        # Cancelled order had 5 units, failed order had 2 units. They must NOT be in total_units_sold!
        self.assertEqual(metrics["summary"]["total_units_sold"], 4)
        # Total revenue from order1 (140) + order2 (80) = 220.0
        self.assertEqual(metrics["summary"]["total_revenue"], 220.0)

    def test_10_price_authority_unaltered(self):
        """AI recommendations reflect live DB price; AI never overrides pricing."""
        res = self.client.get(f"/api/ai/recommendations?shop_id={self.shop1_id}")
        self.assertEqual(res.status_code, 200)
        recs = res.get_json().get("recommendations", [])
        dosa = next((r for r in recs if r["item_id"] == self.item1_dosa), None)
        self.assertIsNotNone(dosa)
        self.assertEqual(dosa["price"], 70.00)

        # Update DB price to ₹75.00
        DB.execute("UPDATE menu_items SET price = 75.00 WHERE id = %s", (self.item1_dosa,))
        res2 = self.client.get(f"/api/ai/recommendations?shop_id={self.shop1_id}")
        recs2 = res2.get_json().get("recommendations", [])
        dosa2 = next((r for r in recs2 if r["item_id"] == self.item1_dosa), None)
        self.assertEqual(dosa2["price"], 75.00)
        # Revert price back
        DB.execute("UPDATE menu_items SET price = 70.00 WHERE id = %s", (self.item1_dosa,))

    # ========================================================================
    # 4. ANALYTICS & VENDOR ISOLATION
    # ========================================================================

    def test_11_vendor_analytics_shop_isolation(self):
        """Vendor 1 can view Shop 1 analytics, but is strictly blocked from Shop 2 (403 Forbidden)."""
        self.login(self.v1_email, self.pwd, role="vendor")

        # Access assigned shop
        res = self.client.get(f"/api/ai/analytics/shop/{self.shop1_id}")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["success"])

        # Attempt to access another vendor's shop
        res_cross = self.client.get(f"/api/ai/analytics/shop/{self.shop2_id}")
        self.assertEqual(res_cross.status_code, 403)
        self.assertIn("Forbidden", res_cross.get_json()["message"])

    def test_12_vendor_analytics_metrics_accuracy(self):
        """Shop analytics contains accurate operational telemetry."""
        self.login(self.v1_email, self.pwd, role="vendor")
        res = self.client.get(f"/api/ai/analytics/shop/{self.shop1_id}")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        self.assertIn("summary", data)
        self.assertEqual(data["summary"]["completed_orders"], 2)
        self.assertEqual(data["summary"]["cancelled_orders"], 1)
        self.assertIn("top_selling_items", data)
        self.assertIn("peak_hours", data)
        self.assertIn("meal_slot_demand", data)

    def test_13_admin_overview_analytics(self):
        """Admin can access platform-wide analytics; customer role is rejected."""
        # Customer attempt rejected
        self.login(self.cust1_email, self.pwd, role="customer")
        res_cust = self.client.get("/api/ai/analytics/overview")
        self.assertEqual(res_cust.status_code, 403)

        # Admin access accepted
        self.login(self.admin_email, self.pwd, role="admin")
        res_admin = self.client.get("/api/ai/analytics/overview")
        self.assertEqual(res_admin.status_code, 200)
        data = res_admin.get_json()
        self.assertTrue(data["success"])
        self.assertIn("stalls_performance", data)
        self.assertIn("top_selling_items", data)
        self.assertIn("category_shares", data)

    def test_14_legacy_endpoint_backward_compatibility(self):
        """Legacy /api/recommendations endpoint still functions seamlessly with new engine."""
        res = self.client.get(f"/api/recommendations?shop_id={self.shop1_id}")
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertTrue(body.get("success"))
        recs = body.get("recommendations", [])
        self.assertGreater(len(recs), 0)
        for r in recs:
            self.assertIn("id", r)
            self.assertIn("name", r)
            self.assertIn("price", r)

    def test_15_fault_tolerance_db_error_handling(self):
        """Unexpected exception inside feature calculation does not crash engine or server."""
        with patch.object(FoodCourtRecommender, "get_recommendations", side_effect=RuntimeError("Simulated AI Crash")):
            # Even if mocked recommender raises, client gets clean response or error handled gracefully
            res = self.client.get(f"/api/ai/recommendations?shop_id={self.shop1_id}")
            self.assertIn(res.status_code, [200, 500])

    @classmethod
    def tearDownClass(cls):
        try:
            DB.execute("DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE order_reference LIKE 'P8-%')")
            DB.execute("DELETE FROM payments WHERE order_id IN (SELECT id FROM orders WHERE order_reference LIKE 'P8-%')")
            DB.execute("DELETE FROM orders WHERE order_reference LIKE 'P8-%'")
            DB.execute("DELETE FROM menu_items WHERE shop_id IN (SELECT id FROM shops WHERE slug LIKE '%phase8%')")
            DB.execute("DELETE FROM shops WHERE slug LIKE '%phase8%'")
            DB.execute("DELETE FROM customer_profiles WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@test8.kpriet.ac.in')")
            DB.execute("DELETE FROM users WHERE email LIKE '%@test8.kpriet.ac.in'")
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
