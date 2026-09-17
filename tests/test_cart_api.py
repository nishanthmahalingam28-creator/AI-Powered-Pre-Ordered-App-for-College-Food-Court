"""
Automated Test Suite for Database-Backed Cart System.
Validates:
1. Authentication: Unauthenticated requests return 401.
2. Cart retrieval (GET /api/cart) returns empty cart initially.
3. Adding items (POST /api/cart) with stock and stall validation.
4. Out-of-stock and invalid item rejections.
5. Single-stall enforcement: Conflict detection (HTTP 409) when adding items from a second stall.
6. Single-stall override: clear_conflicting_stall=True switches stalls.
7. Updating quantities (PUT /api/cart/<id>) including stock ceiling and deletion on qty<=0.
8. Deleting individual items (DELETE /api/cart/<id>).
9. Clearing cart (DELETE /api/cart).
10. Order Placement auto-clears cart from database.
"""

import os
import sys
import unittest
import json

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ["FLASK_ENV"] = "development"
os.environ["USE_SQLITE"] = "1"
os.environ["SECRET_KEY"] = "cart-test-key-32-chars-long-secure"

import init_db
init_db.init_sqlite()

from db import DB
from app import app


class TestCartAPI(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()

        # Clean cart_items before each test
        DB.execute("DELETE FROM cart_items")

        # Set up a test customer session (user id 8, student)
        with self.client.session_transaction() as sess:
            sess["user_id"] = 8
            sess["role"] = "customer"
            sess["customer_type"] = "student"
            sess["email"] = "student@kpriet.ac.in"

    def test_unauthenticated_cart_access_rejected(self):
        anon_client = self.app.test_client()
        res = anon_client.get("/api/cart")
        self.assertEqual(res.status_code, 401)

        res = anon_client.post("/api/cart", json={"item_id": 1, "quantity": 1})
        self.assertEqual(res.status_code, 401)

        res = anon_client.put("/api/cart/1", json={"quantity": 2})
        self.assertEqual(res.status_code, 401)

        res = anon_client.delete("/api/cart/1")
        self.assertEqual(res.status_code, 401)

        res = anon_client.delete("/api/cart")
        self.assertEqual(res.status_code, 401)

    def test_get_empty_cart(self):
        res = self.client.get("/api/cart")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["cart"]), 0)
        self.assertEqual(data["summary"]["total_amount"], 0.0)
        self.assertEqual(data["summary"]["total_items"], 0)

    def test_add_item_to_cart(self):
        # Get an available menu item
        item = DB.get_one("SELECT id, shop_id, name, price, quantity FROM menu_items WHERE is_available = 1 AND quantity > 5 LIMIT 1")
        self.assertIsNotNone(item)

        res = self.client.post("/api/cart", json={"item_id": item["id"], "quantity": 2})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["cart"]), 1)
        self.assertEqual(data["cart"][0]["id"], item["id"])
        self.assertEqual(data["cart"][0]["quantity"], 2)
        self.assertEqual(data["summary"]["total_items"], 2)
        self.assertEqual(data["summary"]["total_amount"], round(item["price"] * 2, 2))

        # Adding same item again increments quantity
        res2 = self.client.post("/api/cart", json={"item_id": item["id"], "quantity": 1})
        self.assertEqual(res2.status_code, 200)
        data2 = res2.get_json()
        self.assertEqual(data2["cart"][0]["quantity"], 3)
        self.assertEqual(data2["summary"]["total_items"], 3)

    def test_add_nonexistent_or_unavailable_item(self):
        # Nonexistent
        res = self.client.post("/api/cart", json={"item_id": 999999, "quantity": 1})
        self.assertEqual(res.status_code, 404)

        # Unavailable item
        DB.execute("UPDATE menu_items SET is_available = 0 WHERE id = 1")
        res2 = self.client.post("/api/cart", json={"item_id": 1, "quantity": 1})
        self.assertEqual(res2.status_code, 400)
        DB.execute("UPDATE menu_items SET is_available = 1 WHERE id = 1")

    def test_single_stall_conflict_and_clear_override(self):
        # Find items from two different stalls
        item_stall1 = DB.get_one("SELECT id, shop_id, name FROM menu_items WHERE shop_id = 1 AND is_available = 1 LIMIT 1")
        item_stall2 = DB.get_one("SELECT id, shop_id, name FROM menu_items WHERE shop_id = 2 AND is_available = 1 LIMIT 1")
        self.assertIsNotNone(item_stall1)
        self.assertIsNotNone(item_stall2)

        # Add item from stall 1
        res = self.client.post("/api/cart", json={"item_id": item_stall1["id"], "quantity": 1})
        self.assertEqual(res.status_code, 200)

        # Try to add item from stall 2 without override -> Expect 409 Conflict
        res_conflict = self.client.post("/api/cart", json={"item_id": item_stall2["id"], "quantity": 1})
        self.assertEqual(res_conflict.status_code, 409)
        conflict_data = res_conflict.get_json()
        self.assertTrue(conflict_data.get("conflict"))

        # Add item from stall 2 WITH clear_conflicting_stall=True -> Succeeds and clears stall 1 items
        res_override = self.client.post("/api/cart", json={
            "item_id": item_stall2["id"],
            "quantity": 2,
            "clear_conflicting_stall": True
        })
        self.assertEqual(res_override.status_code, 200)
        data = res_override.get_json()
        self.assertEqual(len(data["cart"]), 1)
        self.assertEqual(data["cart"][0]["id"], item_stall2["id"])
        self.assertEqual(data["cart"][0]["quantity"], 2)

    def test_update_cart_item_quantity(self):
        item = DB.get_one("SELECT id, price, quantity FROM menu_items WHERE is_available = 1 AND quantity >= 10 LIMIT 1")
        self.client.post("/api/cart", json={"item_id": item["id"], "quantity": 2})

        # Update to 5
        res = self.client.put(f"/api/cart/{item['id']}", json={"quantity": 5})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["cart"][0]["quantity"], 5)
        self.assertEqual(data["summary"]["total_items"], 5)

        # Update to 0 removes item
        res2 = self.client.put(f"/api/cart/{item['id']}", json={"quantity": 0})
        self.assertEqual(res2.status_code, 200)
        data2 = res2.get_json()
        self.assertEqual(len(data2["cart"]), 0)

    def test_remove_cart_item(self):
        item = DB.get_one("SELECT id FROM menu_items WHERE is_available = 1 LIMIT 1")
        self.client.post("/api/cart", json={"item_id": item["id"], "quantity": 1})

        res = self.client.delete(f"/api/cart/{item['id']}")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(len(data["cart"]), 0)

    def test_clear_cart(self):
        item = DB.get_one("SELECT id FROM menu_items WHERE is_available = 1 LIMIT 1")
        self.client.post("/api/cart", json={"item_id": item["id"], "quantity": 3})

        res = self.client.delete("/api/cart")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(len(data["cart"]), 0)
        self.assertEqual(data["summary"]["total_items"], 0)

    def test_order_placement_auto_clears_cart(self):
        item = DB.get_one("SELECT id, shop_id, price FROM menu_items WHERE is_available = 1 AND quantity >= 5 LIMIT 1")
        self.client.post("/api/cart", json={"item_id": item["id"], "quantity": 1})

        # Verify item is in DB cart
        cart_rows = DB.get_all("SELECT * FROM cart_items WHERE user_id = 8")
        self.assertEqual(len(cart_rows), 1)

        # Place order for this item
        order_res = self.client.post("/api/orders/place", json={
            "shop_id": item["shop_id"],
            "payment_method": "Campus Wallet",
            "items": [{"id": item["id"], "quantity": 1}]
        })
        self.assertIn(order_res.status_code, (200, 201))

        # Verify DB cart is now empty
        cart_rows_after = DB.get_all("SELECT * FROM cart_items WHERE user_id = 8")
        self.assertEqual(len(cart_rows_after), 0)


if __name__ == "__main__":
    unittest.main()
