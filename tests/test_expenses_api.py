"""
Automated Test Suite for Database-Backed Authenticated Expense Persistence.

Covers all requirements:
1. Authenticated expense API endpoints (rejects unauthenticated requests with 401).
2. Owner/user ID derived strictly from authenticated session, never from client-supplied userId.
3. Full CRUD:
   - Create expense (POST /api/expenses)
   - Get current user's expenses (GET /api/expenses)
   - Get single expense (GET /api/expenses/<id>)
   - Update expense (PUT /api/expenses/<id>)
   - Delete expense (DELETE /api/expenses/<id>)
4. Strict validation:
   - amount (positive numeric value, bounded)
   - date (valid YYYY-MM-DD calendar date)
   - category (non-empty string, length checked)
   - description (non-empty string, length checked)
5. Multi-tenant IDOR security test:
   - User A creates an expense.
   - User B cannot read, modify, or delete User A's expense by swapping IDs.
6. Database persistence verified directly in DB.
"""

import os
import sys
import secrets
import unittest
from datetime import date

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ["FLASK_ENV"] = "development"
os.environ["USE_SQLITE"] = "1"
os.environ["SECRET_KEY"] = "expense-test-key-32b-secret-min-key"

import init_db
init_db.init_sqlite()

from db import DB
from app import app
from routes.auth import _otp_failed_verifications, _otp_send_limits


class TestExpensesAPI(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        _otp_failed_verifications.clear()
        _otp_send_limits.clear()

    def _generate_mobile(self):
        return f"9{secrets.randbelow(900000000) + 100000000}"

    def _register_and_login_user(self, name_prefix="Expense Tester"):
        """Helper to create and log in a fresh user, returning user details and client."""
        client = self.app.test_client()
        suffix = secrets.token_hex(4)
        email = f"user_{suffix}@kpriet.ac.in"
        mobile = self._generate_mobile()
        password = "SecurePassword123!"

        # Send & verify OTP
        r_send = client.post("/api/auth/otp/send", json={"mobile": mobile, "purpose": "signup"})
        self.assertEqual(r_send.status_code, 200)
        otp = r_send.get_json().get("demo_otp")

        r_v = client.post("/api/auth/otp/verify", json={"mobile": mobile, "code": otp, "purpose": "signup"})
        self.assertEqual(r_v.status_code, 200)

        # Register
        r_signup = client.post("/api/auth/customer/signup", json={
            "fullName": f"{name_prefix} Alpha",
            "email": email,
            "password": password,
            "confirmPassword": password,
            "customerType": "student",
            "identifier": f"23CS{secrets.randbelow(899) + 100}",
            "mobile": mobile
        })
        self.assertEqual(r_signup.status_code, 201)
        user_data = r_signup.get_json().get("user", {})
        user_id = user_data.get("id")

        return client, user_id, email

    # -------------------------------------------------------------
    # 1. Create Expense & DB Persistence
    # -------------------------------------------------------------
    def test_create_expense_success(self):
        """Authenticated user creates an expense; verified in database."""
        client, user_id, email = self._register_and_login_user("Buyer")

        payload = {
            "amount": 185.50,
            "category": "Food & Dining",
            "description": "Lunch with Chicken Biryani at Royal Kitchen",
            "date": "2026-09-17"
        }

        res = client.post("/api/expenses", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        expense = data.get("expense", {})
        self.assertEqual(expense.get("amount"), 185.50)
        self.assertEqual(expense.get("category"), payload["category"])
        self.assertEqual(expense.get("description"), payload["description"])
        self.assertEqual(expense.get("expense_date"), payload["date"])
        self.assertEqual(expense.get("user_id"), user_id)

        # Verify record in database
        db_row = DB.get_one("SELECT * FROM expenses WHERE id = %s", (expense["id"],))
        self.assertIsNotNone(db_row)
        self.assertEqual(db_row["user_id"], user_id)
        self.assertEqual(float(db_row["amount"]), 185.50)
        self.assertEqual(db_row["category"], payload["category"])
        self.assertEqual(db_row["description"], payload["description"])
        self.assertEqual(str(db_row["expense_date"]), payload["date"])

    # -------------------------------------------------------------
    # 2. Session-Derived Ownership (Ignore Client-Supplied userId)
    # -------------------------------------------------------------
    def test_user_id_derived_from_session_only(self):
        """Client-supplied userId or user_id in payload is strictly ignored."""
        client, user_id, email = self._register_and_login_user("Spoofer")

        payload = {
            "amount": 75.00,
            "category": "Snacks & Beverages",
            "description": "Evening Tea and Snacks",
            "date": "2026-09-17",
            "userId": 99999,
            "user_id": 88888
        }

        res = client.post("/api/expenses", json=payload)
        self.assertEqual(res.status_code, 201)
        expense = res.get_json().get("expense", {})

        # The stored user_id must match the authenticated session's user_id, NOT 99999 or 88888
        self.assertEqual(expense.get("user_id"), user_id)
        db_row = DB.get_one("SELECT user_id FROM expenses WHERE id = %s", (expense["id"],))
        self.assertEqual(db_row["user_id"], user_id)
        self.assertNotEqual(db_row["user_id"], 99999)
        self.assertNotEqual(db_row["user_id"], 88888)

    # -------------------------------------------------------------
    # 3. Get Current User's Expenses
    # -------------------------------------------------------------
    def test_get_current_user_expenses(self):
        """Retrieves only the authenticated user's expenses."""
        client, user_id, email = self._register_and_login_user("Lister")

        # Create two expenses
        client.post("/api/expenses", json={
            "amount": 50.00,
            "category": "Snacks & Beverages",
            "description": "Juice at Mario",
            "date": "2026-09-16"
        })
        client.post("/api/expenses", json={
            "amount": 120.00,
            "category": "Food & Dining",
            "description": "Meals at Campus Kitchen",
            "date": "2026-09-17"
        })

        res = client.get("/api/expenses")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("count"), 2)
        self.assertEqual(data.get("total_amount"), 170.00)
        expenses = data.get("expenses", [])
        self.assertEqual(len(expenses), 2)
        for exp in expenses:
            self.assertEqual(exp.get("user_id"), user_id)

    # -------------------------------------------------------------
    # 4. Update Expense
    # -------------------------------------------------------------
    def test_update_expense_success(self):
        """Owner can update their expense record."""
        client, user_id, email = self._register_and_login_user("Updater")

        # Create initial expense
        create_res = client.post("/api/expenses", json={
            "amount": 60.00,
            "category": "Food & Dining",
            "description": "Mini Tiffin",
            "date": "2026-09-15"
        })
        self.assertEqual(create_res.status_code, 201)
        exp_id = create_res.get_json()["expense"]["id"]

        # Update expense
        update_payload = {
            "amount": 75.00,
            "category": "Food & Dining",
            "description": "Special Mini Tiffin with Coffee",
            "date": "2026-09-15"
        }
        put_res = client.put(f"/api/expenses/{exp_id}", json=update_payload)
        self.assertEqual(put_res.status_code, 200)
        updated = put_res.get_json().get("expense", {})
        self.assertEqual(updated.get("amount"), 75.00)
        self.assertEqual(updated.get("description"), "Special Mini Tiffin with Coffee")

        # Verify in DB
        db_row = DB.get_one("SELECT amount, description FROM expenses WHERE id = %s", (exp_id,))
        self.assertEqual(float(db_row["amount"]), 75.00)
        self.assertEqual(db_row["description"], "Special Mini Tiffin with Coffee")

    # -------------------------------------------------------------
    # 5. Delete Expense
    # -------------------------------------------------------------
    def test_delete_expense_success(self):
        """Owner can delete their expense record."""
        client, user_id, email = self._register_and_login_user("Deleter")

        create_res = client.post("/api/expenses", json={
            "amount": 40.00,
            "category": "Snacks & Beverages",
            "description": "Cold Drink",
            "date": "2026-09-16"
        })
        self.assertEqual(create_res.status_code, 201)
        exp_id = create_res.get_json()["expense"]["id"]

        # Delete expense
        del_res = client.delete(f"/api/expenses/{exp_id}")
        self.assertEqual(del_res.status_code, 200)
        self.assertTrue(del_res.get_json().get("success"))

        # Verify removed from DB
        db_row = DB.get_one("SELECT id FROM expenses WHERE id = %s", (exp_id,))
        self.assertIsNone(db_row)

    # -------------------------------------------------------------
    # 6. Validation Rules
    # -------------------------------------------------------------
    def test_validation_rules(self):
        """Validates amount, date, category, and description."""
        client, user_id, email = self._register_and_login_user("Validator")

        base_valid = {
            "amount": 100.00,
            "category": "Food & Dining",
            "description": "Lunch Meal",
            "date": "2026-09-17"
        }

        # 1. Negative or zero amount
        res1 = client.post("/api/expenses", json={**base_valid, "amount": 0})
        self.assertEqual(res1.status_code, 400)
        self.assertIn("positive number", res1.get_json().get("message", "").lower())

        res2 = client.post("/api/expenses", json={**base_valid, "amount": -25.50})
        self.assertEqual(res2.status_code, 400)
        self.assertIn("positive number", res2.get_json().get("message", "").lower())

        # 2. Non-numeric amount
        res3 = client.post("/api/expenses", json={**base_valid, "amount": "abc"})
        self.assertEqual(res3.status_code, 400)
        self.assertIn("valid numeric", res3.get_json().get("message", "").lower())

        # 3. Invalid date format
        res4 = client.post("/api/expenses", json={**base_valid, "date": "17-09-2026"})
        self.assertEqual(res4.status_code, 400)
        self.assertIn("yyyy-mm-dd", res4.get_json().get("message", "").lower())

        # 4. Invalid calendar date (e.g. Feb 31)
        res5 = client.post("/api/expenses", json={**base_valid, "date": "2026-02-31"})
        self.assertEqual(res5.status_code, 400)
        self.assertIn("valid calendar date", res5.get_json().get("message", "").lower())

        # 5. Empty category
        res6 = client.post("/api/expenses", json={**base_valid, "category": "   "})
        self.assertEqual(res6.status_code, 400)
        self.assertIn("category", res6.get_json().get("message", "").lower())

        # 6. Empty description
        res7 = client.post("/api/expenses", json={**base_valid, "description": ""})
        self.assertEqual(res7.status_code, 400)
        self.assertIn("description", res7.get_json().get("message", "").lower())

    # -------------------------------------------------------------
    # 7. Multi-Tenant IDOR Security Test
    # -------------------------------------------------------------
    def test_idor_cross_user_isolation(self):
        """
        Security requirement:
        Create two users and verify that User A cannot access, modify, or delete
        User B's expenses by changing IDs in the request.
        """
        client_a, user_a_id, email_a = self._register_and_login_user("UserAlpha")
        client_b, user_b_id, email_b = self._register_and_login_user("UserBeta")

        # User A creates an expense
        res_a = client_a.post("/api/expenses", json={
            "amount": 250.00,
            "category": "Food & Dining",
            "description": "User A Private Feast",
            "date": "2026-09-17"
        })
        self.assertEqual(res_a.status_code, 201)
        exp_a_id = res_a.get_json()["expense"]["id"]

        # 1. User B lists expenses -> Must NOT include User A's expense
        list_b = client_b.get("/api/expenses")
        self.assertEqual(list_b.status_code, 200)
        b_expenses = list_b.get_json().get("expenses", [])
        self.assertEqual(len(b_expenses), 0, "User B's list must not contain User A's expense")

        # 2. User B tries to GET User A's expense by ID -> Must be rejected (403 or 404)
        get_b = client_b.get(f"/api/expenses/{exp_a_id}")
        self.assertIn(get_b.status_code, [403, 404], "User B must not be able to read User A's expense")
        self.assertFalse(get_b.get_json().get("success"))

        # 3. User B tries to UPDATE User A's expense by ID -> Must be rejected (403 or 404)
        put_b = client_b.put(f"/api/expenses/{exp_a_id}", json={
            "amount": 1.00,
            "category": "Hacked",
            "description": "Tampered By User B",
            "date": "2026-09-17"
        })
        self.assertIn(put_b.status_code, [403, 404], "User B must not be able to update User A's expense")

        # Verify in DB: User A's expense is COMPLETELY UNTOUCHED
        db_a = DB.get_one("SELECT amount, description FROM expenses WHERE id = %s", (exp_a_id,))
        self.assertEqual(float(db_a["amount"]), 250.00)
        self.assertEqual(db_a["description"], "User A Private Feast")

        # 4. User B tries to DELETE User A's expense by ID -> Must be rejected (403 or 404)
        del_b = client_b.delete(f"/api/expenses/{exp_a_id}")
        self.assertIn(del_b.status_code, [403, 404], "User B must not be able to delete User A's expense")

        # Verify in DB: User A's expense STILL EXISTS
        db_a_still_exists = DB.get_one("SELECT id FROM expenses WHERE id = %s", (exp_a_id,))
        self.assertIsNotNone(db_a_still_exists, "User A's expense must not be deleted by User B")

    # -------------------------------------------------------------
    # 8. Unauthenticated Requests Rejected
    # -------------------------------------------------------------
    def test_unauthenticated_requests_rejected(self):
        """Unauthenticated requests return 401 Unauthorized across all endpoints."""
        unauth_client = self.app.test_client()

        r_post = unauth_client.post("/api/expenses", json={
            "amount": 50.00,
            "category": "Food & Dining",
            "description": "Unauth Attempt",
            "date": "2026-09-17"
        })
        self.assertEqual(r_post.status_code, 401)

        r_get = unauth_client.get("/api/expenses")
        self.assertEqual(r_get.status_code, 401)

        r_put = unauth_client.put("/api/expenses/1", json={"amount": 20.00})
        self.assertEqual(r_put.status_code, 401)

        r_del = unauth_client.delete("/api/expenses/1")
        self.assertEqual(r_del.status_code, 401)


if __name__ == "__main__":
    unittest.main()
