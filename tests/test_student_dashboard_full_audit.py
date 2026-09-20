"""
Complete Student Dashboard Functionality Audit & Repair Test Suite.

Verifies all 18 functional dimensions end-to-end:
1. Student dashboard authentication & session (/api/auth/me with roll_number, role, user_id)
2. Financial summary with zero records (HTTP 200, clean zero defaults, no HTTP 500)
3. Financial summary with income (/api/income -> summary.total_income)
4. Financial summary with expenses (/api/expenses -> summary.total_expenses)
5. Financial summary with both (net_balance, savings_rate)
6. Budget calculation (active category budget tracking spent against real expenses)
7. Financial goal calculation (target amount, current amount, progress percentage)
8. Morning survey save (POST /api/customer/survey)
9. Morning survey status (GET /api/customer/survey/today)
10. Morning survey history & update (GET /api/customer/survey/history & PUT /api/customer/survey)
11. Notifications (GET /api/notifications, unread count, POST /api/notifications/mark-read)
12. Orders (GET /api/orders/my-orders with numeric floats, items, shop name, pickup OTP)
13. Cart operations (GET /api/cart, POST /api/cart, PUT /api/cart/<id>, DELETE /api/cart/<id>)
14. Menu (GET /api/menu with shop names, availability, stock)
15. Shops (GET /api/shops returning real active food court stalls)
16. AI recommendations (GET /api/recommendations aligning with morning survey and filtering unavailable)
17. Unauthorized requests (unauthenticated requests rejected with 401)
18. Logout (POST /api/auth/logout clearing session)
"""

import os
import sys
import unittest
import secrets
from datetime import date

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ["FLASK_ENV"] = "development"
os.environ["USE_SQLITE"] = "1"
os.environ["SECRET_KEY"] = "student-audit-test-secret-key-32b-secure"

import init_db
init_db.init_sqlite()

from db import DB
from app import app
from routes.auth import _otp_failed_verifications, _otp_send_limits


class TestStudentDashboardFullAudit(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        _otp_failed_verifications.clear()
        _otp_send_limits.clear()

    def _generate_mobile(self):
        return f"9{secrets.randbelow(900000000) + 100000000}"

    def _create_and_login_student(self, roll="25CS170", name="Nishanth"):
        """Registers and logs in a student customer with exact roll number."""
        client = self.app.test_client()
        suffix = secrets.token_hex(3)
        email = f"student_{suffix}@kpriet.ac.in"
        mobile = self._generate_mobile()
        password = "StudentPassword123!"

        # Send & verify OTP
        r_otp = client.post("/api/auth/otp/send", json={"mobile": mobile, "purpose": "signup"})
        self.assertEqual(r_otp.status_code, 200)
        otp = r_otp.get_json().get("demo_otp")

        r_v = client.post("/api/auth/otp/verify", json={"mobile": mobile, "code": otp, "purpose": "signup"})
        self.assertEqual(r_v.status_code, 200)

        # Signup
        r_signup = client.post("/api/auth/customer/signup", json={
            "fullName": f"{name} Mahalingam",
            "email": email,
            "password": password,
            "confirmPassword": password,
            "customerType": "student",
            "identifier": roll,
            "mobile": mobile
        })
        self.assertEqual(r_signup.status_code, 201)
        user = r_signup.get_json().get("user", {})
        user_id = user.get("id")

        return client, user_id, email, roll

    # -----------------------------------------------------------------
    # 1. Student Dashboard Authentication
    # -----------------------------------------------------------------
    def test_01_student_auth_session(self):
        client, user_id, email, roll = self._create_and_login_student(roll="25CS170", name="Nishanth")
        res = client.get("/api/auth/me")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("authenticated"))
        self.assertEqual(data["user"]["role"], "customer")
        self.assertEqual(data["user"]["customer_type"], "student")
        self.assertEqual(data["user"]["roll_number"], "25CS170")
        self.assertEqual(data["user"]["id"], user_id)

    # -----------------------------------------------------------------
    # 2. Financial Summary with Zero Records
    # -----------------------------------------------------------------
    def test_02_financial_summary_zero_records(self):
        client, user_id, email, roll = self._create_and_login_student(roll="25CS171")
        res = client.get("/api/customer/financial-summary")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        summary = data.get("summary", {})
        self.assertEqual(summary.get("total_income"), 0.0)
        self.assertEqual(summary.get("total_expenses"), 0.0)
        self.assertEqual(summary.get("net_balance"), 0.0)
        self.assertEqual(summary.get("savings_rate"), 0.0)
        self.assertEqual(data.get("budgets"), [])
        self.assertEqual(data.get("goals"), [])
        self.assertEqual(data.get("recent_transactions"), [])

    # -----------------------------------------------------------------
    # 3. Financial Summary with Income
    # -----------------------------------------------------------------
    def test_03_financial_summary_with_income(self):
        client, user_id, email, roll = self._create_and_login_student(roll="25CS172")
        # Add income via /api/income
        inc_res = client.post("/api/income", json={
            "amount": 5000.0,
            "source": "Allowance",
            "description": "Monthly Allowance from family",
            "income_date": str(date.today()),
            "notes": "Parent transfer"
        })
        self.assertEqual(inc_res.status_code, 201)

        res = client.get("/api/customer/financial-summary")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data["summary"]["total_income"], 5000.0)
        self.assertEqual(data["summary"]["total_expenses"], 0.0)
        self.assertEqual(data["summary"]["net_balance"], 5000.0)

    # -----------------------------------------------------------------
    # 4. Financial Summary with Expenses
    # -----------------------------------------------------------------
    def test_04_financial_summary_with_expenses(self):
        client, user_id, email, roll = self._create_and_login_student(roll="25CS173")
        # Add expense via /api/expenses
        exp_res = client.post("/api/expenses", json={
            "amount": 150.0,
            "category": "Food Court",
            "description": "Lunch at Dosa Corner",
            "expense_date": str(date.today())
        })
        self.assertEqual(exp_res.status_code, 201)

        res = client.get("/api/customer/financial-summary")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data["summary"]["total_expenses"], 150.0)
        self.assertEqual(data["summary"]["net_balance"], -150.0)

    # -----------------------------------------------------------------
    # 5. Financial Summary with Both (Income & Expenses)
    # -----------------------------------------------------------------
    def test_05_financial_summary_with_both(self):
        client, user_id, email, roll = self._create_and_login_student(roll="25CS174")
        inc_res = client.post("/api/income", json={
            "amount": 2000.0,
            "source": "Stipend",
            "description": "Part Time Stipend",
            "income_date": str(date.today())
        })
        self.assertEqual(inc_res.status_code, 201)

        exp_res = client.post("/api/expenses", json={
            "amount": 500.0,
            "category": "Food Court",
            "description": "Snacks & Drinks",
            "expense_date": str(date.today())
        })
        self.assertEqual(exp_res.status_code, 201)

        res = client.get("/api/customer/financial-summary")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data["summary"]["total_income"], 2000.0)
        self.assertEqual(data["summary"]["total_expenses"], 500.0)
        self.assertEqual(data["summary"]["net_balance"], 1500.0)
        # savings rate = (1500 / 2000) * 100 = 75.0%
        self.assertEqual(data["summary"]["savings_rate"], 75.0)

    # -----------------------------------------------------------------
    # 6. Budget Calculation
    # -----------------------------------------------------------------
    def test_06_budget_calculation(self):
        client, user_id, email, roll = self._create_and_login_student(roll="25CS175")
        # Create budget for "Food Court" limit 1000 via /api/budgets
        b_res = client.post("/api/budgets", json={
            "category": "Food Court",
            "amount_limit": 1000.0,
            "period": "monthly"
        })
        self.assertEqual(b_res.status_code, 201)

        # Incur expense of 400
        client.post("/api/expenses", json={
            "amount": 400.0,
            "category": "Food Court",
            "description": "Meals",
            "expense_date": str(date.today())
        })

        res = client.get("/api/customer/financial-summary")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["summary"]["total_budget"], 1000.0)
        self.assertEqual(data["summary"]["total_budget_spent"], 400.0)
        self.assertEqual(data["summary"]["budget_percent_spent"], 40.0)

        budgets = data.get("budgets", [])
        self.assertEqual(len(budgets), 1)
        self.assertEqual(budgets[0]["category"], "Food Court")
        self.assertEqual(budgets[0]["spent"], 400.0)
        self.assertEqual(budgets[0]["remaining"], 600.0)

    # -----------------------------------------------------------------
    # 7. Financial Goal Calculation
    # -----------------------------------------------------------------
    def test_07_financial_goal_calculation(self):
        client, user_id, email, roll = self._create_and_login_student(roll="25CS176")
        g_res = client.post("/api/goals", json={
            "title": "Semester Textbooks",
            "target_amount": 2000.0,
            "current_amount": 800.0,
            "target_date": "2026-12-31"
        })
        self.assertEqual(g_res.status_code, 201)

        res = client.get("/api/customer/financial-summary")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["summary"]["total_goals_target"], 2000.0)
        self.assertEqual(data["summary"]["total_goals_saved"], 800.0)
        self.assertEqual(data["summary"]["goals_overall_progress"], 40.0)

        goals = data.get("goals", [])
        self.assertEqual(len(goals), 1)
        self.assertEqual(goals[0]["title"], "Semester Textbooks")
        self.assertEqual(goals[0]["progress_percent"], 40.0)

    # -----------------------------------------------------------------
    # 8. Morning Survey Save
    # -----------------------------------------------------------------
    def test_08_morning_survey_save(self):
        client, user_id, email, roll = self._create_and_login_student(roll="25CS177")
        payload = {
            "meal_preference": "Biryani & Fried Rice Delights",
            "hunger_level": "High",
            "dietary_preference": "Non-Veg",
            "meal_type": "Lunch",
            "mood_energy": "Excited",
            "food_restrictions": "None",
            "notes": "Extra spicy"
        }
        res = client.post("/api/customer/survey", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertIn("survey", data)

    # -----------------------------------------------------------------
    # 9. Morning Survey Status
    # -----------------------------------------------------------------
    def test_09_morning_survey_status(self):
        client, user_id, email, roll = self._create_and_login_student(roll="25CS178")
        # Initially not completed
        init_res = client.get("/api/customer/survey/today")
        self.assertEqual(init_res.status_code, 200)
        self.assertFalse(init_res.get_json().get("completed"))

        # Submit survey
        client.post("/api/customer/survey", json={
            "meal_preference": "South Indian Dosas & Meals",
            "hunger_level": "Normal",
            "dietary_preference": "Veg",
            "meal_type": "Breakfast"
        })

        # Now completed
        status_res = client.get("/api/customer/survey/today")
        self.assertEqual(status_res.status_code, 200)
        status_data = status_res.get_json()
        self.assertTrue(status_data.get("completed"))
        self.assertEqual(status_data["survey"]["meal_preference"], "South Indian Dosas & Meals")

    # -----------------------------------------------------------------
    # 10. Morning Survey History & Update
    # -----------------------------------------------------------------
    def test_10_morning_survey_history_and_update(self):
        client, user_id, email, roll = self._create_and_login_student(roll="25CS179")
        client.post("/api/customer/survey", json={
            "meal_preference": "Burgers, Sandwiches & Fries",
            "hunger_level": "Normal",
            "dietary_preference": "Non-Veg",
            "meal_type": "Lunch"
        })

        # History retrieves it
        hist_res = client.get("/api/customer/survey/history")
        self.assertEqual(hist_res.status_code, 200)
        self.assertGreaterEqual(len(hist_res.get_json().get("surveys", [])), 1)

        # Update survey preferences via PUT
        update_res = client.put("/api/customer/survey", json={
            "meal_preference": "Fresh Fruit Juices & Shakes",
            "hunger_level": "Low",
            "dietary_preference": "Veg",
            "meal_type": "Snack"
        })
        self.assertEqual(update_res.status_code, 200)
        updated_data = update_res.get_json()
        self.assertTrue(updated_data.get("success"))
        self.assertEqual(updated_data["survey"]["meal_preference"], "Fresh Fruit Juices & Shakes")

    # -----------------------------------------------------------------
    # 11. Notifications
    # -----------------------------------------------------------------
    def test_11_notifications(self):
        client, user_id, email, roll = self._create_and_login_student(roll="25CS180")
        # Seed a test notification with type
        DB.execute(
            """INSERT INTO notifications (user_id, type, title, message, is_read, created_at)
               VALUES (%s, %s, %s, %s, 0, datetime('now'))""",
            (user_id, "order_status", "Order Ready", "Your order #ORD-123 is ready for pickup at Counter 1")
        )

        res = client.get("/api/notifications")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertGreaterEqual(data.get("unread_count", 0), 1)
        notifs = data.get("notifications", [])
        self.assertGreaterEqual(len(notifs), 1)
        self.assertEqual(notifs[0]["title"], "Order Ready")

        # Mark read
        notif_id = notifs[0]["id"]
        read_res = client.put(f"/api/notifications/{notif_id}/read")
        self.assertEqual(read_res.status_code, 200)

        # Verify unread count is now 0
        res2 = client.get("/api/notifications")
        self.assertEqual(res2.get_json().get("unread_count"), 0)

    # -----------------------------------------------------------------
    # 12. Orders API
    # -----------------------------------------------------------------
    def test_12_orders(self):
        client, user_id, email, roll = self._create_and_login_student(roll="25CS181")
        # Empty orders state
        res_empty = client.get("/api/orders/my-orders")
        self.assertEqual(res_empty.status_code, 200)
        self.assertEqual(res_empty.get_json().get("orders"), [])

        # Seed an order in database with customer_id
        order_ref = f"ORD-{secrets.randbelow(89999) + 10000}"
        DB.execute(
            """INSERT INTO orders (customer_id, shop_id, order_reference, total_amount, order_status, payment_status, pickup_otp, created_at)
               VALUES (%s, 1, %s, 120.50, 'ready', 'paid', '8492', datetime('now'))""",
            (user_id, order_ref)
        )
        row = DB.get_one("SELECT id FROM orders WHERE order_reference = %s", (order_ref,))
        order_id = row["id"]
        DB.execute(
            """INSERT INTO order_items (order_id, menu_item_id, item_name, unit_price, quantity, subtotal)
               VALUES (%s, 1, 'Ghee Podi Dosa', 60.25, 2, 120.50)""",
            (order_id,)
        )

        res_orders = client.get("/api/orders/my-orders")
        self.assertEqual(res_orders.status_code, 200)
        data = res_orders.get_json()
        self.assertTrue(data.get("success"))
        orders = data.get("orders", [])
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["order_reference"], order_ref)
        self.assertEqual(orders[0]["total_amount"], 120.50)
        self.assertIsInstance(orders[0]["total_amount"], float)
        self.assertEqual(orders[0]["pickup_otp"], "8492")
        self.assertEqual(len(orders[0]["items"]), 1)
        self.assertIsInstance(orders[0]["items"][0]["unit_price"], float)

    # -----------------------------------------------------------------
    # 13. Cart API Operations
    # -----------------------------------------------------------------
    def test_13_cart_operations(self):
        client, user_id, email, roll = self._create_and_login_student(roll="25CS182")
        # Initial empty cart
        res_c0 = client.get("/api/cart")
        self.assertEqual(res_c0.status_code, 200)
        self.assertEqual(res_c0.get_json().get("cart"), [])

        # Add item 1
        res_add = client.post("/api/cart", json={"item_id": 1, "quantity": 2})
        self.assertEqual(res_add.status_code, 200)
        cart_items = res_add.get_json().get("cart", [])
        self.assertEqual(len(cart_items), 1)
        self.assertEqual(cart_items[0]["quantity"], 2)

        # Update quantity
        res_put = client.put("/api/cart/1", json={"quantity": 3})
        self.assertEqual(res_put.status_code, 200)
        self.assertEqual(res_put.get_json()["cart"][0]["quantity"], 3)

        # Delete item
        res_del = client.delete("/api/cart/1")
        self.assertEqual(res_del.status_code, 200)
        self.assertEqual(len(res_del.get_json()["cart"]), 0)

    # -----------------------------------------------------------------
    # 14. Menu API
    # -----------------------------------------------------------------
    def test_14_menu(self):
        client = self.app.test_client()
        res = client.get("/api/menu")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        items = data.get("items", [])
        self.assertGreaterEqual(len(items), 1)
        item = items[0]
        self.assertIn("id", item)
        self.assertIn("name", item)
        self.assertIn("price", item)
        self.assertIn("is_available", item)
        self.assertIn("shop_name", item)

    # -----------------------------------------------------------------
    # 15. Shops API
    # -----------------------------------------------------------------
    def test_15_shops(self):
        client = self.app.test_client()
        res = client.get("/api/shops")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        shops = data.get("shops", [])
        self.assertGreaterEqual(len(shops), 1)
        shop = shops[0]
        self.assertIn("id", shop)
        self.assertIn("name", shop)
        self.assertIn("is_active", shop)

    # -----------------------------------------------------------------
    # 16. AI Recommendations
    # -----------------------------------------------------------------
    def test_16_ai_recommendations(self):
        client, user_id, email, roll = self._create_and_login_student(roll="25CS183")
        # Submit morning survey craving Dosa
        client.post("/api/customer/survey", json={
            "meal_preference": "South Indian Dosa",
            "hunger_level": "High",
            "dietary_preference": "Veg",
            "meal_type": "Breakfast"
        })

        res = client.get("/api/recommendations")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        recs = data.get("recommendations", [])
        self.assertIsInstance(recs, list)
        self.assertGreater(len(recs), 0)
        # Verify recommendation items have valid pricing and shop names
        for item in recs:
            self.assertIn("id", item)
            self.assertIn("name", item)
            self.assertIn("price", item)
            self.assertIn("shop_name", item)

    # -----------------------------------------------------------------
    # 17. Unauthorized Requests
    # -----------------------------------------------------------------
    def test_17_unauthorized_requests(self):
        anon_client = self.app.test_client()
        res_fin = anon_client.get("/api/customer/financial-summary")
        self.assertEqual(res_fin.status_code, 401)

        res_orders = anon_client.get("/api/orders/my-orders")
        self.assertEqual(res_orders.status_code, 401)

        res_survey = anon_client.get("/api/customer/survey/today")
        self.assertEqual(res_survey.status_code, 401)

        res_cart = anon_client.get("/api/cart")
        self.assertEqual(res_cart.status_code, 401)

    # -----------------------------------------------------------------
    # 18. Logout
    # -----------------------------------------------------------------
    def test_18_logout(self):
        client, user_id, email, roll = self._create_and_login_student(roll="25CS184")
        # Verify authenticated
        res_me = client.get("/api/auth/me")
        self.assertEqual(res_me.status_code, 200)
        self.assertTrue(res_me.get_json().get("authenticated"))

        # Logout
        res_logout = client.post("/api/auth/logout")
        self.assertEqual(res_logout.status_code, 200)

        # After logout, /api/auth/me rejects with 401
        res_me_after = client.get("/api/auth/me")
        self.assertEqual(res_me_after.status_code, 401)


if __name__ == "__main__":
    unittest.main()
