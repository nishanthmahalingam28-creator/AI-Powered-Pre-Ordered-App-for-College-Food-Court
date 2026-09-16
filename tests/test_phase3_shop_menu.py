"""
Phase 3 Shop & Menu Management Automated Test Suite.

Validates the full chain:
ADMIN -> SHOP MANAGEMENT -> VENDOR ASSIGNMENT -> VENDOR MENU MANAGEMENT ->
MYSQL/DATABASE -> FLASK REST API -> CUSTOMER MENU -> CUSTOMER ORDERS

Covers all 38 requirements specified in Section 23:
- Shop Tests (1-5)
- Menu Tests (6-13)
- Vendor Tests (14-24)
- Validation Tests (25-32)
- Customer Integration Tests (33-38)
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
os.environ["SECRET_KEY"] = "phase3-shop-menu-test-key-32b-secret"

import init_db
init_db.init_sqlite()

from db import DB
from app import app
from werkzeug.security import generate_password_hash


class TestPhase3ShopMenuManagement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Refresh test database state
        init_db.init_sqlite()

        # Admin User
        cls.admin_email = "admin@kpriet.ac.in"
        cls.admin_pwd = "admin123"
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

        # Vendor 1: YPR
        cls.vendor1_email = "ypr@kpriet.ac.in"
        cls.vendor1_pwd = "vendor123"
        v1 = DB.get_one("SELECT id FROM users WHERE email = %s", (cls.vendor1_email,))
        if not v1:
            cls.vendor1_id = DB.execute(
                "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'vendor', 1)",
                (cls.vendor1_email, generate_password_hash(cls.vendor1_pwd))
            )
        else:
            cls.vendor1_id = v1["id"]
            DB.execute("UPDATE users SET password_hash = %s, role = 'vendor', is_active = 1 WHERE id = %s",
                       (generate_password_hash(cls.vendor1_pwd), cls.vendor1_id))

        ypr = DB.get_one("SELECT id FROM shops WHERE name = 'YPR'")
        cls.ypr_shop_id = ypr["id"]
        DB.execute("UPDATE shops SET owner_user_id = %s, is_active = 1 WHERE id = %s", (cls.vendor1_id, cls.ypr_shop_id))

        # Vendor 2: Royal Kitchen
        cls.vendor2_email = "royal@kpriet.ac.in"
        cls.vendor2_pwd = "vendor123"
        v2 = DB.get_one("SELECT id FROM users WHERE email = %s", (cls.vendor2_email,))
        if not v2:
            cls.vendor2_id = DB.execute(
                "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'vendor', 1)",
                (cls.vendor2_email, generate_password_hash(cls.vendor2_pwd))
            )
        else:
            cls.vendor2_id = v2["id"]
            DB.execute("UPDATE users SET password_hash = %s, role = 'vendor', is_active = 1 WHERE id = %s",
                       (generate_password_hash(cls.vendor2_pwd), cls.vendor2_id))

        rk = DB.get_one("SELECT id FROM shops WHERE name = 'Royal Kitchen'")
        cls.rk_shop_id = rk["id"]
        DB.execute("UPDATE shops SET owner_user_id = %s, is_active = 1 WHERE id = %s", (cls.vendor2_id, cls.rk_shop_id))

        # Create Inactive Stall and an Assigned Vendor for Inactive Stall Tests
        cls.inactive_vendor_email = "inactive_vendor_p3@kpriet.ac.in"
        cls.inactive_vendor_pwd = "VendorPass123!"
        v_inact = DB.get_one("SELECT id FROM users WHERE email = %s", (cls.inactive_vendor_email,))
        if not v_inact:
            cls.inactive_vendor_id = DB.execute(
                "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'vendor', 1)",
                (cls.inactive_vendor_email, generate_password_hash(cls.inactive_vendor_pwd))
            )
        else:
            cls.inactive_vendor_id = v_inact["id"]

        inact_shop = DB.get_one("SELECT id FROM shops WHERE slug = 'test-closed-stall'")
        if not inact_shop:
            cls.inactive_shop_id = DB.execute(
                "INSERT INTO shops (name, slug, description, category, owner_user_id, is_active) VALUES ('Closed Stall', 'test-closed-stall', 'Temporarily closed', 'Food', %s, 0)",
                (cls.inactive_vendor_id,)
            )
        else:
            cls.inactive_shop_id = inact_shop["id"]
            DB.execute("UPDATE shops SET is_active = 0, owner_user_id = %s WHERE id = %s", (cls.inactive_vendor_id, cls.inactive_shop_id))

        # Customer User
        cls.customer_email = "p3_student@kpriet.ac.in"
        cls.customer_pwd = "StudentPass123!"
        cust = DB.get_one("SELECT id FROM users WHERE email = %s", (cls.customer_email,))
        if not cust:
            cls.customer_id = DB.execute(
                "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
                (cls.customer_email, generate_password_hash(cls.customer_pwd))
            )
            DB.execute(
                "INSERT INTO customer_profiles (user_id, full_name, mobile, customer_type, identifier) VALUES (%s, 'Test Student P3', '9876543210', 'student', '21CS001')",
                (cls.customer_id,)
            )
        else:
            cls.customer_id = cust["id"]

    def setUp(self):
        self.client = app.test_client()

    def _login_admin(self, client=None):
        c = client or self.client
        resp = c.post("/api/auth/admin/login", json={"email": self.admin_email, "password": self.admin_pwd})
        self.assertEqual(resp.status_code, 200, f"Admin login failed: {resp.get_data(as_text=True)}")
        return c

    def _login_vendor(self, email=None, pwd=None, client=None):
        c = client or self.client
        e = email or self.vendor1_email
        p = pwd or self.vendor1_pwd
        resp = c.post("/api/auth/vendor/login", json={"email": e, "password": p})
        return resp, c

    def _login_customer(self, client=None):
        c = client or self.client
        resp = c.post("/api/auth/customer/login", json={
            "email": self.customer_email,
            "password": self.customer_pwd,
            "customerType": "student"
        })
        self.assertEqual(resp.status_code, 200, f"Customer login failed: {resp.get_data(as_text=True)}")
        return c

    # =========================================================================
    # 1. SHOP TESTS (1-5)
    # =========================================================================

    def test_01_active_shops_can_be_retrieved(self):
        """1. Active shops can be retrieved via GET /api/shops."""
        resp = self.client.get("/api/shops")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertIsInstance(data["shops"], list)
        self.assertGreaterEqual(len(data["shops"]), 5)
        names = [s["name"] for s in data["shops"]]
        self.assertIn("YPR", names)
        self.assertIn("German Cafe", names)
        self.assertIn("Royal Kitchen", names)
        self.assertIn("Mario", names)
        self.assertIn("Saaral", names)

    def test_02_inactive_shops_are_excluded_from_customer_listing(self):
        """2. Inactive shops are excluded from customer listing."""
        resp = self.client.get("/api/shops")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        slugs = [s["slug"] for s in data["shops"]]
        self.assertNotIn("test-closed-stall", slugs)
        for s in data["shops"]:
            self.assertEqual(s["is_active"], 1)

    def test_03_shop_details_are_correct(self):
        """3. Shop details are correct and do not expose sensitive credentials."""
        resp = self.client.get(f"/api/shops/{self.ypr_shop_id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        shop = data["shop"]
        self.assertEqual(shop["name"], "YPR")
        self.assertEqual(shop["category"], "Food")
        self.assertIn("total_items", shop)
        # Sensitive credentials must never be leaked
        self.assertNotIn("password", shop)
        self.assertNotIn("password_hash", shop)
        self.assertNotIn("owner_user_id", shop)

    def test_04_duplicate_shop_handling(self):
        """4. Duplicate shop creation rejected with HTTP 409 Conflict."""
        admin_client = self._login_admin()
        resp = admin_client.post("/api/admin/shops", json={
            "name": "YPR",
            "category": "Food",
            "description": "Duplicate YPR"
        })
        self.assertEqual(resp.status_code, 409)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertIn("already exists", data["message"].lower())

    def test_05_invalid_shop_id_rejected_safely(self):
        """5. Invalid shop ID returns 404 cleanly without database crash."""
        resp = self.client.get("/api/shops/999999")
        self.assertEqual(resp.status_code, 404)
        data = resp.get_json()
        self.assertFalse(data["success"])

        # Invalid query param on menu returns empty or clean validation
        resp2 = self.client.get("/api/menu?shop_id=invalid_id")
        self.assertEqual(resp2.status_code, 400)

    # =========================================================================
    # 2. MENU TESTS (6-13)
    # =========================================================================

    def test_06_customer_can_retrieve_menu(self):
        """6. Customer can retrieve menu from database."""
        resp = self.client.get("/api/menu")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertIsInstance(data["items"], list)
        self.assertGreater(len(data["items"]), 0)

    def test_07_menu_can_be_filtered_by_shop(self):
        """7. Menu can be filtered by shop_id and returns only that shop's items."""
        resp = self.client.get(f"/api/menu?shop_id={self.ypr_shop_id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertGreater(len(data["items"]), 0)
        for item in data["items"]:
            self.assertEqual(item["shop_id"], self.ypr_shop_id)
            self.assertEqual(item["shop_name"], "YPR")

    def test_08_menu_can_be_filtered_by_category(self):
        """8. Menu can be filtered by category."""
        resp = self.client.get(f"/api/menu?category=Food")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        for item in data["items"]:
            self.assertEqual(item["category"], "Food")

    def test_09_menu_search_works(self):
        """9. Menu search works case-insensitively across name and description."""
        resp = self.client.get("/api/menu?q=Dosa")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertGreaterEqual(len(data["items"]), 1)
        names = [item["name"].lower() for item in data["items"]]
        self.assertTrue(any("dosa" in n for n in names))

    def test_10_item_details_work(self):
        """10. Item details work via GET /api/menu/<id>."""
        item = DB.get_one("SELECT id, name, price FROM menu_items WHERE is_available = 1 LIMIT 1")
        self.assertIsNotNone(item)
        resp = self.client.get(f"/api/menu/{item['id']}")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["item"]["id"], item["id"])
        self.assertEqual(data["item"]["name"], item["name"])

    def test_11_unavailable_items_are_marked_correctly(self):
        """11. Unavailable or 0-quantity items are marked is_available = 0."""
        # Insert a 0-stock item
        test_item_id = DB.execute(
            """
            INSERT INTO menu_items (shop_id, name, description, category, price, quantity, is_available)
            VALUES (%s, 'Sold Out Samosa', 'Crispy samosa', 'Snacks', 15.00, 0, 0)
            """,
            (self.ypr_shop_id,)
        )
        resp = self.client.get(f"/api/menu/{test_item_id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["item"]["quantity"], 0)
        self.assertEqual(data["item"]["is_available"], 0)

    def test_12_invalid_item_id_returns_404(self):
        """12. Invalid item ID returns 404 Not Found."""
        resp = self.client.get("/api/menu/99999999")
        self.assertEqual(resp.status_code, 404)
        data = resp.get_json()
        self.assertFalse(data["success"])

    def test_13_menu_item_belongs_to_correct_shop(self):
        """13. Menu item belongs to correct shop and does not bleed into other shop listings."""
        ypr_resp = self.client.get(f"/api/menu?shop_id={self.ypr_shop_id}")
        rk_resp = self.client.get(f"/api/menu?shop_id={self.rk_shop_id}")
        ypr_ids = {i["id"] for i in ypr_resp.get_json()["items"]}
        rk_ids = {i["id"] for i in rk_resp.get_json()["items"]}
        # No overlap between distinct shops
        self.assertEqual(ypr_ids.intersection(rk_ids), set())

    # =========================================================================
    # 3. VENDOR TESTS (14-24)
    # =========================================================================

    def test_14_vendor_can_add_item_to_assigned_shop(self):
        """14. Vendor can add food item to assigned shop and it persists to database."""
        login_resp, v_client = self._login_vendor(self.vendor1_email, self.vendor1_pwd)
        self.assertEqual(login_resp.status_code, 200)

        resp = v_client.post("/api/vendor/menu/item", json={
            "name": "Phase 3 Special Pongal",
            "price": 45.00,
            "quantity": 25,
            "category": "Food",
            "available": True,
            "description": "Hot ghee pongal"
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertTrue(data["success"])
        item_id = data["item"]["id"]

        # Verify in DB
        db_item = DB.get_one("SELECT * FROM menu_items WHERE id = %s", (item_id,))
        self.assertIsNotNone(db_item)
        self.assertEqual(db_item["shop_id"], self.ypr_shop_id)
        self.assertEqual(db_item["name"], "Phase 3 Special Pongal")
        self.assertEqual(float(db_item["price"]), 45.00)
        self.assertEqual(db_item["quantity"], 25)

    def test_15_vendor_can_update_own_shop_item(self):
        """15. Vendor can update own shop item."""
        _, v_client = self._login_vendor(self.vendor1_email, self.vendor1_pwd)

        # Create item to update
        add_resp = v_client.post("/api/vendor/menu/item", json={
            "name": "Updatable Vada",
            "price": 12.00,
            "quantity": 30,
            "category": "Food",
            "available": True
        })
        item_id = add_resp.get_json()["item"]["id"]

        # Update name and description
        put_resp = v_client.put(f"/api/vendor/menu/item/{item_id}", json={
            "name": "Crispy Medu Vada",
            "description": "Served with hot sambar and chutney"
        })
        self.assertEqual(put_resp.status_code, 200)
        db_item = DB.get_one("SELECT name, description FROM menu_items WHERE id = %s", (item_id,))
        self.assertEqual(db_item["name"], "Crispy Medu Vada")
        self.assertEqual(db_item["description"], "Served with hot sambar and chutney")

    def test_16_vendor_can_delete_or_deactivate_own_shop_item(self):
        """16. Vendor can delete/deactivate own shop item; preserves historical orders safely."""
        _, v_client = self._login_vendor(self.vendor1_email, self.vendor1_pwd)
        add_resp = v_client.post("/api/vendor/menu/item", json={
            "name": "Disposable Item",
            "price": 10.00,
            "quantity": 5,
            "category": "Food"
        })
        item_id = add_resp.get_json()["item"]["id"]

        del_resp = v_client.delete(f"/api/vendor/menu/item/{item_id}")
        self.assertEqual(del_resp.status_code, 200)
        # Without order history, item is removed
        db_item = DB.get_one("SELECT * FROM menu_items WHERE id = %s", (item_id,))
        self.assertIsNone(db_item)

    def test_17_vendor_can_change_price(self):
        """17. Vendor can change price."""
        _, v_client = self._login_vendor(self.vendor1_email, self.vendor1_pwd)
        add_resp = v_client.post("/api/vendor/menu/item", json={
            "name": "Price Change Tea",
            "price": 15.00,
            "quantity": 50,
            "category": "Food"
        })
        item_id = add_resp.get_json()["item"]["id"]

        resp = v_client.put(f"/api/vendor/menu/item/{item_id}", json={"price": 20.00})
        self.assertEqual(resp.status_code, 200)
        db_item = DB.get_one("SELECT price FROM menu_items WHERE id = %s", (item_id,))
        self.assertEqual(float(db_item["price"]), 20.00)

    def test_18_vendor_can_change_stock(self):
        """18. Vendor can change stock/quantity."""
        _, v_client = self._login_vendor(self.vendor1_email, self.vendor1_pwd)
        add_resp = v_client.post("/api/vendor/menu/item", json={
            "name": "Stock Change Item",
            "price": 25.00,
            "quantity": 10,
            "category": "Food"
        })
        item_id = add_resp.get_json()["item"]["id"]

        resp = v_client.put(f"/api/vendor/menu/item/{item_id}", json={"quantity": 40})
        self.assertEqual(resp.status_code, 200)
        db_item = DB.get_one("SELECT quantity FROM menu_items WHERE id = %s", (item_id,))
        self.assertEqual(db_item["quantity"], 40)

    def test_19_vendor_can_change_availability(self):
        """19. Vendor can toggle item availability."""
        _, v_client = self._login_vendor(self.vendor1_email, self.vendor1_pwd)
        add_resp = v_client.post("/api/vendor/menu/item", json={
            "name": "Toggle Available Dish",
            "price": 30.00,
            "quantity": 15,
            "category": "Food",
            "available": True
        })
        item_id = add_resp.get_json()["item"]["id"]

        # Toggle to unavailable
        resp = v_client.put(f"/api/vendor/menu/item/{item_id}", json={"available": False})
        self.assertEqual(resp.status_code, 200)
        db_item = DB.get_one("SELECT is_available FROM menu_items WHERE id = %s", (item_id,))
        self.assertEqual(db_item["is_available"], 0)

        # Toggle back to available
        resp2 = v_client.put(f"/api/vendor/menu/item/{item_id}", json={"available": True})
        self.assertEqual(resp2.status_code, 200)
        db_item2 = DB.get_one("SELECT is_available FROM menu_items WHERE id = %s", (item_id,))
        self.assertEqual(db_item2["is_available"], 1)

    def test_20_vendor_cannot_modify_another_shop_item(self):
        """20. CRITICAL IDOR: Vendor 1 (YPR) cannot modify Royal Kitchen's menu item."""
        # Create an item belonging to Royal Kitchen (Vendor 2)
        _, v2_client = self._login_vendor(self.vendor2_email, self.vendor2_pwd)
        rk_add = v2_client.post("/api/vendor/menu/item", json={
            "name": "Royal Chicken Biryani",
            "price": 140.00,
            "quantity": 15,
            "category": "Food"
        })
        rk_item_id = rk_add.get_json()["item"]["id"]

        # Now Vendor 1 (YPR) attempts to modify Royal Kitchen item
        _, v1_client = self._login_vendor(self.vendor1_email, self.vendor1_pwd)
        idor_resp = v1_client.put(f"/api/vendor/menu/item/{rk_item_id}", json={"price": 1.00})
        self.assertEqual(idor_resp.status_code, 403)
        data = idor_resp.get_json()
        self.assertFalse(data["success"])
        self.assertTrue("forbidden" in data["message"].lower() or "cannot modify" in data["message"].lower())

        # Vendor 1 attempts to delete Royal Kitchen item
        idor_del = v1_client.delete(f"/api/vendor/menu/item/{rk_item_id}")
        self.assertEqual(idor_del.status_code, 403)

    def test_21_vendor_cannot_create_item_for_another_shop(self):
        """21. Backend forces item to vendor's own shop even if frontend sends a spoofed shop_id."""
        _, v1_client = self._login_vendor(self.vendor1_email, self.vendor1_pwd)
        resp = v1_client.post("/api/vendor/menu/item", json={
            "shop_id": self.rk_shop_id,  # Spoofed shop_id
            "name": "Spoofed Stall Item",
            "price": 50.00,
            "quantity": 10,
            "category": "Food"
        })
        self.assertEqual(resp.status_code, 201)
        item_id = resp.get_json()["item"]["id"]
        # Database MUST have assigned YPR (vendor1's actual shop), never Royal Kitchen
        db_item = DB.get_one("SELECT shop_id FROM menu_items WHERE id = %s", (item_id,))
        self.assertEqual(db_item["shop_id"], self.ypr_shop_id)
        self.assertNotEqual(db_item["shop_id"], self.rk_shop_id)

    def test_22_vendor_cannot_operate_on_inactive_shop(self):
        """22. Vendor assigned to an inactive shop is rejected with HTTP 403."""
        login_resp, _ = self._login_vendor(self.inactive_vendor_email, self.inactive_vendor_pwd)
        self.assertEqual(login_resp.status_code, 403)

    def test_23_customer_cannot_use_vendor_apis(self):
        """23. Customer cannot access vendor menu modification APIs."""
        cust_client = self._login_customer()
        resp = cust_client.post("/api/vendor/menu/item", json={
            "name": "Hacker Dish",
            "price": 10.00,
            "quantity": 10,
            "category": "Food"
        })
        self.assertEqual(resp.status_code, 403)

    def test_24_admin_shop_operations_require_admin_role(self):
        """24. Non-admins cannot invoke admin shop management endpoints."""
        _, v_client = self._login_vendor(self.vendor1_email, self.vendor1_pwd)
        resp = v_client.post("/api/admin/shops", json={
            "name": "Unauthorized Stall",
            "category": "Food"
        })
        self.assertEqual(resp.status_code, 403)

    # =========================================================================
    # 4. VALIDATION TESTS (25-32)
    # =========================================================================

    def test_25_negative_price_rejected(self):
        """25. Negative and zero price rejected."""
        _, v_client = self._login_vendor(self.vendor1_email, self.vendor1_pwd)
        resp_neg = v_client.post("/api/vendor/menu/item", json={
            "name": "Negative Price Dish",
            "price": -15.00,
            "quantity": 10,
            "category": "Food"
        })
        self.assertEqual(resp_neg.status_code, 400)
        self.assertIn("price", resp_neg.get_json()["message"].lower())

        resp_zero = v_client.post("/api/vendor/menu/item", json={
            "name": "Zero Price Dish",
            "price": 0.00,
            "quantity": 10,
            "category": "Food"
        })
        self.assertEqual(resp_zero.status_code, 400)

    def test_26_invalid_price_rejected(self):
        """26. Invalid price formats (NaN, Infinity, malformed strings, ₹ symbols) rejected."""
        _, v_client = self._login_vendor(self.vendor1_email, self.vendor1_pwd)
        for bad_price in ["NaN", "Infinity", "₹50", "free", "100.999", None]:
            resp = v_client.post("/api/vendor/menu/item", json={
                "name": "Bad Price Dish",
                "price": bad_price,
                "quantity": 10,
                "category": "Food"
            })
            self.assertEqual(resp.status_code, 400, f"Expected 400 for price: {bad_price}")

    def test_27_negative_stock_rejected(self):
        """27. Negative stock and fractional stock rejected."""
        _, v_client = self._login_vendor(self.vendor1_email, self.vendor1_pwd)
        resp_neg = v_client.post("/api/vendor/menu/item", json={
            "name": "Negative Stock Dish",
            "price": 30.00,
            "quantity": -5,
            "category": "Food"
        })
        self.assertEqual(resp_neg.status_code, 400)

        resp_float = v_client.post("/api/vendor/menu/item", json={
            "name": "Float Stock Dish",
            "price": 30.00,
            "quantity": 5.5,
            "category": "Food"
        })
        self.assertEqual(resp_float.status_code, 400)

    def test_28_invalid_category_rejected_where_appropriate(self):
        """28. Category with special/malformed characters rejected."""
        _, v_client = self._login_vendor(self.vendor1_email, self.vendor1_pwd)
        resp = v_client.post("/api/vendor/menu/item", json={
            "name": "Invalid Category Dish",
            "price": 20.00,
            "quantity": 5,
            "category": "<script>alert(1)</script>"
        })
        self.assertEqual(resp.status_code, 400)

    def test_29_missing_item_name_rejected(self):
        """29. Missing item name rejected."""
        _, v_client = self._login_vendor(self.vendor1_email, self.vendor1_pwd)
        resp = v_client.post("/api/vendor/menu/item", json={
            "name": "   ",
            "price": 25.00,
            "quantity": 10,
            "category": "Food"
        })
        self.assertEqual(resp.status_code, 400)

    def test_30_missing_shop_rejected(self):
        """30. Vendor without active shop assignment cannot perform menu operations."""
        # Unassigned vendor
        unassigned_email = "unassigned_p3@kpriet.ac.in"
        unassigned_pwd = "VendorPass123!"
        u = DB.get_one("SELECT id FROM users WHERE email = %s", (unassigned_email,))
        if not u:
            uid = DB.execute(
                "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'vendor', 1)",
                (unassigned_email, generate_password_hash(unassigned_pwd))
            )
        else:
            uid = u["id"]
        DB.execute("UPDATE shops SET owner_user_id = NULL WHERE owner_user_id = %s", (uid,))

        resp, _ = self._login_vendor(unassigned_email, unassigned_pwd)
        self.assertEqual(resp.status_code, 403)

    def test_31_oversized_input_rejected_safely(self):
        """31. Oversized item name and description rejected safely."""
        _, v_client = self._login_vendor(self.vendor1_email, self.vendor1_pwd)
        resp = v_client.post("/api/vendor/menu/item", json={
            "name": "A" * 300,
            "price": 20.00,
            "quantity": 5,
            "category": "Food"
        })
        self.assertEqual(resp.status_code, 400)

    def test_32_sql_injection_attempt_rejected_safely(self):
        """32. SQL injection payload handled safely via parameterized queries."""
        sqli_payload = "Paneer' OR '1'='1"
        resp = self.client.get(f"/api/menu?q={sqli_payload}")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        # Should not dump entire database or crash
        self.assertIsInstance(data["items"], list)

    # =========================================================================
    # 5. CUSTOMER INTEGRATION TESTS (33-38)
    # =========================================================================

    def test_33_customer_sees_active_shops_from_database(self):
        """33. Customer sees active shops queried directly from database."""
        resp = self.client.get("/api/shops")
        self.assertEqual(resp.status_code, 200)
        shops = resp.get_json()["shops"]
        db_count = DB.get_one("SELECT COUNT(*) as cnt FROM shops WHERE is_active = 1")["cnt"]
        self.assertEqual(len(shops), db_count)

    def test_34_customer_sees_current_menu_from_api(self):
        """34. Customer sees current authoritative menu from API/database."""
        resp = self.client.get(f"/api/menu?shop_id={self.ypr_shop_id}")
        self.assertEqual(resp.status_code, 200)
        items = resp.get_json()["items"]
        for item in items:
            self.assertIn("price", item)
            self.assertIn("quantity", item)
            self.assertIn("is_available", item)

    def test_35_vendor_changes_menu_reflected_in_customer_api(self):
        """35. Vendor changes menu (price update) -> Customer API immediately returns updated price."""
        _, v_client = self._login_vendor(self.vendor1_email, self.vendor1_pwd)
        add_resp = v_client.post("/api/vendor/menu/item", json={
            "name": "Live Price Reflection Item",
            "price": 50.00,
            "quantity": 20,
            "category": "Food",
            "available": True
        })
        item_id = add_resp.get_json()["item"]["id"]

        # Customer sees ₹50
        cust_resp1 = self.client.get(f"/api/menu/{item_id}")
        self.assertEqual(float(cust_resp1.get_json()["item"]["price"]), 50.00)

        # Vendor updates to ₹60
        update_resp = v_client.put(f"/api/vendor/menu/item/{item_id}", json={"price": 60.00})
        self.assertEqual(update_resp.status_code, 200)

        # Customer immediately sees ₹60
        cust_resp2 = self.client.get(f"/api/menu/{item_id}")
        self.assertEqual(float(cust_resp2.get_json()["item"]["price"]), 60.00)

    def test_36_out_of_stock_item_cannot_be_ordered(self):
        """36. Out-of-stock item cannot be ordered by customer."""
        _, v_client = self._login_vendor(self.vendor1_email, self.vendor1_pwd)
        add_resp = v_client.post("/api/vendor/menu/item", json={
            "name": "Depleted Stock Item",
            "price": 35.00,
            "quantity": 0,
            "available": False,
            "category": "Food"
        })
        item_id = add_resp.get_json()["item"]["id"]

        cust_client = self._login_customer()
        order_resp = cust_client.post("/api/orders/place", json={
            "items": [{"id": item_id, "quantity": 1}],
            "payment_method": "Campus Wallet"
        })
        self.assertEqual(order_resp.status_code, 400)
        data = order_resp.get_json()
        self.assertFalse(data["success"])
        self.assertIn("out of stock", data["message"].lower())

    def test_37_one_shop_cart_restriction_works(self):
        """37. Backend rejects orders containing items from multiple stalls."""
        ypr_item = DB.get_one("SELECT id FROM menu_items WHERE shop_id = %s AND is_available = 1 AND quantity > 0 LIMIT 1", (self.ypr_shop_id,))
        rk_item = DB.get_one("SELECT id FROM menu_items WHERE shop_id = %s AND is_available = 1 AND quantity > 0 LIMIT 1", (self.rk_shop_id,))

        self.assertIsNotNone(ypr_item)
        self.assertIsNotNone(rk_item)

        cust_client = self._login_customer()
        mixed_order = cust_client.post("/api/orders/place", json={
            "items": [
                {"id": ypr_item["id"], "quantity": 1},
                {"id": rk_item["id"], "quantity": 1}
            ],
            "payment_method": "Campus Wallet"
        })
        self.assertEqual(mixed_order.status_code, 400)
        data = mixed_order.get_json()
        self.assertFalse(data["success"])
        self.assertIn("one shop", data["message"].lower())

    def test_38_backend_rejects_inactive_shop_order(self):
        """38. Backend rejects order attempts on items belonging to an inactive shop."""
        # Insert item into inactive shop
        inact_item_id = DB.execute(
            """
            INSERT INTO menu_items (shop_id, name, description, category, price, quantity, is_available)
            VALUES (%s, 'Inactive Shop Dish', 'Dish in closed shop', 'Food', 50.00, 20, 1)
            """,
            (self.inactive_shop_id,)
        )

        cust_client = self._login_customer()
        order_resp = cust_client.post("/api/orders/place", json={
            "items": [{"id": inact_item_id, "quantity": 1}],
            "payment_method": "Campus Wallet"
        })
        self.assertEqual(order_resp.status_code, 400)
        data = order_resp.get_json()
        self.assertFalse(data["success"])
        self.assertIn("closed or inactive", data["message"].lower())


if __name__ == "__main__":
    unittest.main()
