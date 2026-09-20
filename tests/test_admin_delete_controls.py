"""Tests for Admin permanent deletion controls for vendors and stalls."""

import os
import sys
import unittest
from werkzeug.security import generate_password_hash

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ["FLASK_ENV"] = "development"
os.environ["USE_SQLITE"] = "1"
os.environ["SECRET_KEY"] = "admin-delete-controls-test-secret-key-32b"

import init_db
init_db.init_sqlite()

from app import app
from db import DB


class TestAdminDeleteControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()
        cls.admin_email = "admin.delete.test@kpriet.ac.in"
        cls.admin_password = "Admin@Delete123"
        admin = DB.get_one("SELECT id FROM users WHERE email = %s", (cls.admin_email,))
        if admin:
            cls.admin_id = admin["id"]
            DB.execute(
                "UPDATE users SET password_hash = %s, role = 'admin', is_active = 1 WHERE id = %s",
                (generate_password_hash(cls.admin_password), cls.admin_id),
            )
        else:
            cls.admin_id = DB.execute(
                "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'admin', 1)",
                (cls.admin_email, generate_password_hash(cls.admin_password)),
            )

    def setUp(self):
        self.client.post("/api/auth/logout")
        login = self.client.post(
            "/api/auth/admin/login",
            json={"username": self.admin_email, "password": self.admin_password},
        )
        self.assertEqual(login.status_code, 200)

    def tearDown(self):
        DB.execute("DELETE FROM shops WHERE name = 'Delete Control Test Stall'")
        DB.execute("DELETE FROM users WHERE email = 'delete.vendor.test@kpriet.ac.in'")
        self.client.post("/api/auth/logout")

    def test_admin_can_delete_empty_stall(self):
        created = self.client.post(
            "/api/admin/shops",
            json={"name": "Delete Control Test Stall", "category": "Test"},
        )
        self.assertEqual(created.status_code, 201)
        shop_id = created.get_json()["shop_id"]

        deleted = self.client.delete(f"/api/admin/shops/{shop_id}")
        self.assertEqual(deleted.status_code, 200)
        self.assertIsNone(DB.get_one("SELECT id FROM shops WHERE id = %s", (shop_id,)))

    def test_admin_can_delete_vendor_and_unassign_stall(self):
        created_shop = self.client.post(
            "/api/admin/shops",
            json={"name": "Delete Control Test Stall", "category": "Test"},
        )
        self.assertEqual(created_shop.status_code, 201)
        shop_id = created_shop.get_json()["shop_id"]

        created_vendor = self.client.post(
            "/api/admin/vendors",
            json={
                "email": "delete.vendor.test@kpriet.ac.in",
                "password": "Vendor@Delete123",
                "shop_id": shop_id,
            },
        )
        self.assertEqual(created_vendor.status_code, 201)
        vendor_id = created_vendor.get_json()["user_id"]

        deleted = self.client.delete(f"/api/admin/vendors/{vendor_id}")
        self.assertEqual(deleted.status_code, 200)
        self.assertIsNone(DB.get_one("SELECT id FROM users WHERE id = %s", (vendor_id,)))
        self.assertIsNone(
            DB.get_one("SELECT owner_user_id FROM shops WHERE id = %s", (shop_id,))["owner_user_id"]
        )

    def test_non_admin_cannot_delete(self):
        shop = self.client.post(
            "/api/admin/shops",
            json={"name": "Delete Control Test Stall", "category": "Test"},
        )
        self.assertEqual(shop.status_code, 201)
        shop_id = shop.get_json()["shop_id"]

        self.client.post("/api/auth/logout")
        response = self.client.delete(f"/api/admin/shops/{shop_id}")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
