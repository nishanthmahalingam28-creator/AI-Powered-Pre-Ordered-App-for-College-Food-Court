"""
Automated Test Suite for Database-Backed Authenticated Budgets & Financial Goals Persistence.

Covers all requirements:
1. Authenticated users only (rejects unauthenticated requests with 401).
2. Ownership strictly determined by backend session (ignores client-supplied userId).
3. Full CRUD operations for budgets:
   - POST /api/budgets (create)
   - GET /api/budgets (list current user's budgets)
   - GET /api/budgets/<id> (retrieve single budget)
   - PUT /api/budgets/<id> (update budget)
   - DELETE /api/budgets/<id> (delete budget)
4. Full CRUD operations for financial goals:
   - POST /api/goals (create)
   - GET /api/goals (list current user's goals)
   - GET /api/goals/<id> (retrieve single goal)
   - PUT /api/goals/<id> (update goal)
   - DELETE /api/goals/<id> (delete goal)
   - Also verifies /api/financial-goals alias
5. Input validation (limits, targets, categories, titles, dates).
6. Multi-tenant IDOR protection (User B cannot access or modify User A's budgets or goals).
7. Refresh persistence (records persist across queries).
8. Logout & login persistence (records persist across session invalidation and re-login).
"""

import os
import sys
import secrets
import unittest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ["FLASK_ENV"] = "development"
os.environ["USE_SQLITE"] = "1"
os.environ["SECRET_KEY"] = "budgets-goals-test-key-32b-secret"

import init_db
init_db.init_sqlite()

from db import DB
from app import app
from routes.auth import _otp_failed_verifications, _otp_send_limits


class TestBudgetsAndGoalsAPI(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        _otp_failed_verifications.clear()
        _otp_send_limits.clear()

    def _generate_mobile(self):
        return f"9{secrets.randbelow(900000000) + 100000000}"

    def _register_and_login_user(self, name_prefix="Finance User"):
        """Helper to create and log in a fresh user, returning client, user_id, email, password."""
        client = self.app.test_client()
        suffix = secrets.token_hex(4)
        email = f"user_{suffix}@kpriet.ac.in"
        mobile = self._generate_mobile()
        password = "SecurePassword123!"

        # OTP send & verify
        r_send = client.post("/api/auth/otp/send", json={"mobile": mobile, "purpose": "signup"})
        self.assertEqual(r_send.status_code, 200)
        otp = r_send.get_json().get("demo_otp")

        r_v = client.post("/api/auth/otp/verify", json={"mobile": mobile, "code": otp, "purpose": "signup"})
        self.assertEqual(r_v.status_code, 200)

        # Signup
        r_signup = client.post("/api/auth/customer/signup", json={
            "fullName": f"{name_prefix} Person",
            "email": email,
            "password": password,
            "confirmPassword": password,
            "customerType": "student",
            "identifier": f"23CS{secrets.randbelow(899) + 100}",
            "mobile": mobile
        })
        self.assertEqual(r_signup.status_code, 201)
        user_id = r_signup.get_json().get("user", {}).get("id")

        return client, user_id, email, password

    # -------------------------------------------------------------
    # 1. Budget CRUD & DB Persistence
    # -------------------------------------------------------------
    def test_budget_crud_operations(self):
        """Creates, reads, updates, and deletes a budget record."""
        client, user_id, email, _ = self._register_and_login_user("BudgetTester")

        # 1. Create Budget
        payload = {
            "category": "Canteen Meals",
            "amount_limit": 1500.00,
            "period": "monthly",
            "start_date": "2026-09-01",
            "end_date": "2026-09-30"
        }
        create_res = client.post("/api/budgets", json=payload)
        self.assertEqual(create_res.status_code, 201)
        res_data = create_res.get_json()
        self.assertTrue(res_data.get("success"))
        budget = res_data.get("budget", {})
        self.assertEqual(budget.get("user_id"), user_id)
        self.assertEqual(budget.get("category"), "Canteen Meals")
        self.assertEqual(budget.get("amount_limit"), 1500.00)
        budget_id = budget.get("id")

        # Verify in DB
        db_row = DB.get_one("SELECT * FROM budgets WHERE id = %s", (budget_id,))
        self.assertIsNotNone(db_row)
        self.assertEqual(db_row["user_id"], user_id)
        self.assertEqual(float(db_row["amount_limit"]), 1500.00)

        # 2. Get All Budgets for user
        get_res = client.get("/api/budgets")
        self.assertEqual(get_res.status_code, 200)
        get_data = get_res.get_json()
        self.assertEqual(get_data.get("count"), 1)
        self.assertEqual(get_data.get("total_limit"), 1500.00)

        # 3. Get Single Budget
        single_res = client.get(f"/api/budgets/{budget_id}")
        self.assertEqual(single_res.status_code, 200)
        self.assertEqual(single_res.get_json()["budget"]["category"], "Canteen Meals")

        # 4. Update Budget
        update_res = client.put(f"/api/budgets/{budget_id}", json={
            "amount_limit": 1800.00,
            "category": "Canteen & Snack Bar"
        })
        self.assertEqual(update_res.status_code, 200)
        updated_budget = update_res.get_json()["budget"]
        self.assertEqual(updated_budget["amount_limit"], 1800.00)
        self.assertEqual(updated_budget["category"], "Canteen & Snack Bar")

        # Verify update in DB
        db_updated = DB.get_one("SELECT amount_limit, category FROM budgets WHERE id = %s", (budget_id,))
        self.assertEqual(float(db_updated["amount_limit"]), 1800.00)
        self.assertEqual(db_updated["category"], "Canteen & Snack Bar")

        # 5. Delete Budget
        del_res = client.delete(f"/api/budgets/{budget_id}")
        self.assertEqual(del_res.status_code, 200)
        self.assertTrue(del_res.get_json()["success"])

        # Verify deleted from DB
        db_deleted = DB.get_one("SELECT id FROM budgets WHERE id = %s", (budget_id,))
        self.assertIsNone(db_deleted)

    # -------------------------------------------------------------
    # 2. Financial Goal CRUD & DB Persistence
    # -------------------------------------------------------------
    def test_goal_crud_operations(self):
        """Creates, reads, updates, and deletes a financial goal record."""
        client, user_id, email, _ = self._register_and_login_user("GoalTester")

        # 1. Create Goal
        payload = {
            "title": "Semester Food Reserve",
            "target_amount": 5000.00,
            "current_amount": 1250.00,
            "target_date": "2026-12-15",
            "category": "Dining"
        }
        create_res = client.post("/api/goals", json=payload)
        self.assertEqual(create_res.status_code, 201)
        res_data = create_res.get_json()
        self.assertTrue(res_data.get("success"))
        goal = res_data.get("goal", {})
        self.assertEqual(goal.get("user_id"), user_id)
        self.assertEqual(goal.get("title"), "Semester Food Reserve")
        self.assertEqual(goal.get("target_amount"), 5000.00)
        self.assertEqual(goal.get("current_amount"), 1250.00)
        self.assertEqual(goal.get("progress_percent"), 25.0)
        goal_id = goal.get("id")

        # Verify in DB
        db_row = DB.get_one("SELECT * FROM financial_goals WHERE id = %s", (goal_id,))
        self.assertIsNotNone(db_row)
        self.assertEqual(db_row["user_id"], user_id)
        self.assertEqual(float(db_row["target_amount"]), 5000.00)
        self.assertEqual(float(db_row["current_amount"]), 1250.00)

        # 2. Get All Goals for user (both /api/goals and /api/financial-goals alias)
        get_res = client.get("/api/goals")
        self.assertEqual(get_res.status_code, 200)
        get_data = get_res.get_json()
        self.assertEqual(get_data.get("count"), 1)
        self.assertEqual(get_data.get("total_target"), 5000.00)
        self.assertEqual(get_data.get("total_saved"), 1250.00)

        alias_res = client.get("/api/financial-goals")
        self.assertEqual(alias_res.status_code, 200)
        self.assertEqual(alias_res.get_json().get("count"), 1)

        # 3. Get Single Goal
        single_res = client.get(f"/api/goals/{goal_id}")
        self.assertEqual(single_res.status_code, 200)
        self.assertEqual(single_res.get_json()["goal"]["title"], "Semester Food Reserve")

        # 4. Update Goal (add savings)
        update_res = client.put(f"/api/goals/{goal_id}", json={
            "current_amount": 2500.00,
            "target_amount": 5000.00
        })
        self.assertEqual(update_res.status_code, 200)
        updated_goal = update_res.get_json()["goal"]
        self.assertEqual(updated_goal["current_amount"], 2500.00)
        self.assertEqual(updated_goal["progress_percent"], 50.0)

        # Verify update in DB
        db_updated = DB.get_one("SELECT current_amount FROM financial_goals WHERE id = %s", (goal_id,))
        self.assertEqual(float(db_updated["current_amount"]), 2500.00)

        # 5. Delete Goal
        del_res = client.delete(f"/api/goals/{goal_id}")
        self.assertEqual(del_res.status_code, 200)
        self.assertTrue(del_res.get_json()["success"])

        # Verify deleted from DB
        db_deleted = DB.get_one("SELECT id FROM financial_goals WHERE id = %s", (goal_id,))
        self.assertIsNone(db_deleted)

    # -------------------------------------------------------------
    # 3. Session-Derived Ownership (Ignore Client-Supplied userId)
    # -------------------------------------------------------------
    def test_session_derived_ownership(self):
        """Client-supplied userId or user_id in payload is strictly ignored."""
        client, user_id, email, _ = self._register_and_login_user("SpoofAttempt")

        # Budget with spoofed userId
        b_res = client.post("/api/budgets", json={
            "category": "Snacks",
            "amount_limit": 500.00,
            "userId": 99999,
            "user_id": 88888
        })
        self.assertEqual(b_res.status_code, 201)
        b_rec = b_res.get_json()["budget"]
        self.assertEqual(b_rec["user_id"], user_id)
        db_b = DB.get_one("SELECT user_id FROM budgets WHERE id = %s", (b_rec["id"],))
        self.assertEqual(db_b["user_id"], user_id)
        self.assertNotEqual(db_b["user_id"], 99999)

        # Goal with spoofed userId
        g_res = client.post("/api/goals", json={
            "title": "New Laptop Meal Fund",
            "target_amount": 3000.00,
            "userId": 99999,
            "user_id": 88888
        })
        self.assertEqual(g_res.status_code, 201)
        g_rec = g_res.get_json()["goal"]
        self.assertEqual(g_rec["user_id"], user_id)
        db_g = DB.get_one("SELECT user_id FROM financial_goals WHERE id = %s", (g_rec["id"],))
        self.assertEqual(db_g["user_id"], user_id)
        self.assertNotEqual(db_g["user_id"], 99999)

    # -------------------------------------------------------------
    # 4. Input Validations (Budgets & Goals)
    # -------------------------------------------------------------
    def test_budget_and_goal_validations(self):
        """Tests input bounds, numeric types, non-empty categories, and date validations."""
        client, user_id, email, _ = self._register_and_login_user("Validator")

        # Budget invalid: 0 or negative limit
        r1 = client.post("/api/budgets", json={"category": "Food", "amount_limit": 0})
        self.assertEqual(r1.status_code, 400)
        self.assertIn("positive number", r1.get_json()["message"].lower())

        r2 = client.post("/api/budgets", json={"category": "Food", "amount_limit": -50})
        self.assertEqual(r2.status_code, 400)
        self.assertIn("positive number", r2.get_json()["message"].lower())

        # Budget invalid: non-numeric
        r3 = client.post("/api/budgets", json={"category": "Food", "amount_limit": "not-a-number"})
        self.assertEqual(r3.status_code, 400)
        self.assertIn("valid numeric", r3.get_json()["message"].lower())

        # Budget invalid: empty category
        r4 = client.post("/api/budgets", json={"category": "   ", "amount_limit": 500})
        self.assertEqual(r4.status_code, 400)
        self.assertIn("category", r4.get_json()["message"].lower())

        # Budget invalid: bad date format
        r5 = client.post("/api/budgets", json={"category": "Food", "amount_limit": 500, "start_date": "2026/09/01"})
        self.assertEqual(r5.status_code, 400)
        self.assertIn("yyyy-mm-dd", r5.get_json()["message"].lower())

        # Goal invalid: 0 target amount
        rg1 = client.post("/api/goals", json={"title": "Goal 1", "target_amount": 0})
        self.assertEqual(rg1.status_code, 400)
        self.assertIn("positive number", rg1.get_json()["message"].lower())

        # Goal invalid: negative current amount
        rg2 = client.post("/api/goals", json={"title": "Goal 2", "target_amount": 1000, "current_amount": -10})
        self.assertEqual(rg2.status_code, 400)
        self.assertIn("cannot be negative", rg2.get_json()["message"].lower())

        # Goal invalid: empty title
        rg3 = client.post("/api/goals", json={"title": "  ", "target_amount": 1000})
        self.assertEqual(rg3.status_code, 400)
        self.assertIn("title", rg3.get_json()["message"].lower())

        # Goal invalid: bad target date
        rg4 = client.post("/api/goals", json={"title": "Valid Goal", "target_amount": 1000, "target_date": "2026-02-30"})
        self.assertEqual(rg4.status_code, 400)
        self.assertIn("valid calendar date", rg4.get_json()["message"].lower())

    # -------------------------------------------------------------
    # 5. Multi-Tenant IDOR Security (Budgets)
    # -------------------------------------------------------------
    def test_idor_cross_user_budgets_isolation(self):
        """User A creates a budget; User B cannot read, modify, or delete it."""
        client_a, user_a_id, _, _ = self._register_and_login_user("UserAlpha")
        client_b, user_b_id, _, _ = self._register_and_login_user("UserBeta")

        # User A creates budget
        res_a = client_a.post("/api/budgets", json={
            "category": "Confidential Budget A",
            "amount_limit": 2000.00
        })
        self.assertEqual(res_a.status_code, 201)
        budget_a_id = res_a.get_json()["budget"]["id"]

        # 1. User B lists budgets -> Must NOT see User A's budget
        list_b = client_b.get("/api/budgets")
        self.assertEqual(list_b.status_code, 200)
        self.assertEqual(len(list_b.get_json().get("budgets", [])), 0)

        # 2. User B tries to GET User A's budget by ID -> 403 or 404
        get_b = client_b.get(f"/api/budgets/{budget_a_id}")
        self.assertIn(get_b.status_code, [403, 404])

        # 3. User B tries to PUT User A's budget by ID -> 403 or 404
        put_b = client_b.put(f"/api/budgets/{budget_a_id}", json={
            "amount_limit": 5.00,
            "category": "Hacked"
        })
        self.assertIn(put_b.status_code, [403, 404])

        # Verify in DB: User A's budget unchanged
        db_b = DB.get_one("SELECT amount_limit, category FROM budgets WHERE id = %s", (budget_a_id,))
        self.assertEqual(float(db_b["amount_limit"]), 2000.00)
        self.assertEqual(db_b["category"], "Confidential Budget A")

        # 4. User B tries to DELETE User A's budget by ID -> 403 or 404
        del_b = client_b.delete(f"/api/budgets/{budget_a_id}")
        self.assertIn(del_b.status_code, [403, 404])

        # Verify in DB: User A's budget still exists
        self.assertIsNotNone(DB.get_one("SELECT id FROM budgets WHERE id = %s", (budget_a_id,)))

    # -------------------------------------------------------------
    # 6. Multi-Tenant IDOR Security (Financial Goals)
    # -------------------------------------------------------------
    def test_idor_cross_user_goals_isolation(self):
        """User A creates a financial goal; User B cannot read, modify, or delete it."""
        client_a, user_a_id, _, _ = self._register_and_login_user("GoalAlpha")
        client_b, user_b_id, _, _ = self._register_and_login_user("GoalBeta")

        # User A creates goal
        res_a = client_a.post("/api/goals", json={
            "title": "Secret Emergency Fund A",
            "target_amount": 10000.00,
            "current_amount": 2500.00
        })
        self.assertEqual(res_a.status_code, 201)
        goal_a_id = res_a.get_json()["goal"]["id"]

        # 1. User B lists goals -> Must NOT see User A's goal
        list_b = client_b.get("/api/goals")
        self.assertEqual(list_b.status_code, 200)
        self.assertEqual(len(list_b.get_json().get("goals", [])), 0)

        # 2. User B tries to GET User A's goal by ID -> 403 or 404
        get_b = client_b.get(f"/api/goals/{goal_a_id}")
        self.assertIn(get_b.status_code, [403, 404])

        # 3. User B tries to PUT User A's goal by ID -> 403 or 404
        put_b = client_b.put(f"/api/goals/{goal_a_id}", json={
            "target_amount": 1.00,
            "title": "Hacked Goal"
        })
        self.assertIn(put_b.status_code, [403, 404])

        # Verify in DB: User A's goal unchanged
        db_g = DB.get_one("SELECT target_amount, title FROM financial_goals WHERE id = %s", (goal_a_id,))
        self.assertEqual(float(db_g["target_amount"]), 10000.00)
        self.assertEqual(db_g["title"], "Secret Emergency Fund A")

        # 4. User B tries to DELETE User A's goal by ID -> 403 or 404
        del_b = client_b.delete(f"/api/goals/{goal_a_id}")
        self.assertIn(del_b.status_code, [403, 404])

        # Verify in DB: User A's goal still exists
        self.assertIsNotNone(DB.get_one("SELECT id FROM financial_goals WHERE id = %s", (goal_a_id,)))

    # -------------------------------------------------------------
    # 7. Refresh Persistence & Logout/Login Persistence
    # -------------------------------------------------------------
    def test_refresh_and_logout_login_persistence(self):
        """
        Verifies:
        1. Created records persist across simulated page refreshes (subsequent API queries).
        2. User logs out: session invalidated; endpoints reject with 401.
        3. User logs back in: previous budgets and goals are completely preserved and retrievable.
        """
        client, user_id, email, password = self._register_and_login_user("PersistenceUser")

        # Create budget & goal
        b_res = client.post("/api/budgets", json={"category": "Weekend Cafeteria", "amount_limit": 600.00})
        self.assertEqual(b_res.status_code, 201)
        budget_id = b_res.get_json()["budget"]["id"]

        g_res = client.post("/api/goals", json={"title": "Tech Fest Food Stalls", "target_amount": 1200.00, "current_amount": 300.00})
        self.assertEqual(g_res.status_code, 201)
        goal_id = g_res.get_json()["goal"]["id"]

        # Refresh persistence test (subsequent read operations)
        refresh_b = client.get("/api/budgets")
        self.assertEqual(refresh_b.status_code, 200)
        self.assertEqual(refresh_b.get_json()["count"], 1)
        self.assertEqual(refresh_b.get_json()["budgets"][0]["id"], budget_id)

        refresh_g = client.get("/api/goals")
        self.assertEqual(refresh_g.status_code, 200)
        self.assertEqual(refresh_g.get_json()["count"], 1)
        self.assertEqual(refresh_g.get_json()["goals"][0]["id"], goal_id)

        # User logs out
        logout_res = client.post("/api/auth/logout")
        self.assertEqual(logout_res.status_code, 200)

        # Verify unauthenticated access blocked after logout
        unauth_b = client.get("/api/budgets")
        self.assertEqual(unauth_b.status_code, 401)
        unauth_g = client.get("/api/goals")
        self.assertEqual(unauth_g.status_code, 401)

        # User logs back in with same credentials
        login_res = client.post("/api/auth/customer/login", json={
            "email": email,
            "password": password
        })
        self.assertEqual(login_res.status_code, 200)
        logged_in_data = login_res.get_json()
        self.assertTrue(logged_in_data.get("success"))
        self.assertEqual(logged_in_data.get("user", {}).get("id"), user_id)

        # Verify budget and goal records are completely intact and accessible
        post_login_b = client.get("/api/budgets")
        self.assertEqual(post_login_b.status_code, 200)
        b_list = post_login_b.get_json().get("budgets", [])
        self.assertEqual(len(b_list), 1)
        self.assertEqual(b_list[0]["id"], budget_id)
        self.assertEqual(b_list[0]["category"], "Weekend Cafeteria")
        self.assertEqual(b_list[0]["amount_limit"], 600.00)

        post_login_g = client.get("/api/goals")
        self.assertEqual(post_login_g.status_code, 200)
        g_list = post_login_g.get_json().get("goals", [])
        self.assertEqual(len(g_list), 1)
        self.assertEqual(g_list[0]["id"], goal_id)
        self.assertEqual(g_list[0]["title"], "Tech Fest Food Stalls")
        self.assertEqual(g_list[0]["target_amount"], 1200.00)
        self.assertEqual(g_list[0]["current_amount"], 300.00)

    # -------------------------------------------------------------
    # 8. Unauthenticated Requests Rejected (401)
    # -------------------------------------------------------------
    def test_unauthenticated_requests_rejected(self):
        """Unauthenticated requests to budgets and goals return 401 Unauthorized."""
        unauth = self.app.test_client()

        # Budgets endpoints
        self.assertEqual(unauth.post("/api/budgets", json={"category": "Food", "amount_limit": 100}).status_code, 401)
        self.assertEqual(unauth.get("/api/budgets").status_code, 401)
        self.assertEqual(unauth.get("/api/budgets/1").status_code, 401)
        self.assertEqual(unauth.put("/api/budgets/1", json={"amount_limit": 200}).status_code, 401)
        self.assertEqual(unauth.delete("/api/budgets/1").status_code, 401)

        # Goals endpoints
        self.assertEqual(unauth.post("/api/goals", json={"title": "Goal", "target_amount": 500}).status_code, 401)
        self.assertEqual(unauth.get("/api/goals").status_code, 401)
        self.assertEqual(unauth.get("/api/goals/1").status_code, 401)
        self.assertEqual(unauth.put("/api/goals/1", json={"current_amount": 100}).status_code, 401)
        self.assertEqual(unauth.delete("/api/goals/1").status_code, 401)


if __name__ == "__main__":
    unittest.main()
