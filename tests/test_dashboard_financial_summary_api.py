"""
Automated Test Suite for Database-Backed Customer Dashboard Financial Summary API.

Validates:
1. Accurate calculation of total income, total expenses, and net balance.
2. Accurate aggregation of active category budgets and spending comparisons.
3. Accurate aggregation of financial goals targets and saved amounts.
4. Correct merging, chronological ordering, and capping (max 10) of recent transactions.
5. Graceful handling of a new user with zero transactions (0.00 totals, empty lists, no errors).
6. Strict multi-tenant isolation: User B never receives User A's financial data.
7. Unauthenticated requests are rejected with 401 Unauthorized.
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
os.environ["SECRET_KEY"] = "dashboard-finance-test-secret-key-32b"

import init_db
init_db.init_sqlite()

from db import DB
from app import app
from routes.auth import _otp_failed_verifications, _otp_send_limits


class TestDashboardFinancialSummaryAPI(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        _otp_failed_verifications.clear()
        _otp_send_limits.clear()

    def _generate_mobile(self):
        return f"9{secrets.randbelow(900000000) + 100000000}"

    def _register_and_login_user(self, name_prefix="DashUser"):
        """Creates a fresh user and returns test client and user metadata."""
        client = self.app.test_client()
        suffix = secrets.token_hex(4)
        email = f"dash_{suffix}@kpriet.ac.in"
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

        return client, user_id, email

    # -------------------------------------------------------------
    # 1. New User with Zero Transactions
    # -------------------------------------------------------------
    def test_new_user_zero_transactions(self):
        """A brand new user receives clean 0.00 totals, empty arrays, and no server errors."""
        client, user_id, email = self._register_and_login_user("ZeroActivity")

        res = client.get("/api/customer/financial-summary")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))

        summary = data.get("summary", {})
        self.assertEqual(summary.get("total_income"), 0.00)
        self.assertEqual(summary.get("total_expenses"), 0.00)
        self.assertEqual(summary.get("net_balance"), 0.00)
        self.assertEqual(summary.get("total_budget"), 0.00)
        self.assertEqual(summary.get("total_budget_spent"), 0.00)
        self.assertEqual(summary.get("budget_percent_spent"), 0.0)
        self.assertEqual(summary.get("total_goals_target"), 0.00)
        self.assertEqual(summary.get("total_goals_saved"), 0.00)
        self.assertEqual(summary.get("goals_overall_progress"), 0.0)

        self.assertEqual(len(data.get("budgets", [])), 0)
        self.assertEqual(len(data.get("goals", [])), 0)
        self.assertEqual(len(data.get("recent_transactions", [])), 0)
        self.assertEqual(len(data.get("category_breakdown", [])), 0)

    # -------------------------------------------------------------
    # 2. Financial Metrics Calculation Accuracy
    # -------------------------------------------------------------
    def test_financial_metrics_calculation(self):
        """Accurately calculates total income, total expenses, and net balance from database records."""
        client, user_id, email = self._register_and_login_user("MathUser")

        # Add Income: 3000.00 + 1500.00 = 4500.00
        client.post("/api/income", json={
            "amount": 3000.00,
            "source": "Campus Fellowship",
            "description": "Monthly research fellowship",
            "date": "2026-09-10"
        })
        client.post("/api/income", json={
            "amount": 1500.00,
            "source": "Allowance",
            "description": "Parent allowance",
            "date": "2026-09-12"
        })

        # Add Expenses: 350.00 + 150.00 + 200.00 = 700.00
        client.post("/api/expenses", json={
            "amount": 350.00,
            "category": "Canteen Meals",
            "description": "Lunch with friends",
            "date": "2026-09-14"
        })
        client.post("/api/expenses", json={
            "amount": 150.00,
            "category": "Beverages",
            "description": "Fresh fruit juice",
            "date": "2026-09-15"
        })
        client.post("/api/expenses", json={
            "amount": 200.00,
            "category": "Canteen Meals",
            "description": "Dinner at north counter",
            "date": "2026-09-16"
        })

        res = client.get("/api/customer/financial-summary")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))

        summary = data.get("summary", {})
        self.assertEqual(summary.get("total_income"), 4500.00)
        self.assertEqual(summary.get("total_expenses"), 700.00)
        self.assertEqual(summary.get("net_balance"), 3800.00)  # 4500 - 700 = 3800
        self.assertEqual(summary.get("counts", {}).get("income_entries"), 2)
        self.assertEqual(summary.get("counts", {}).get("expense_entries"), 3)

        # Verify category breakdown
        cat_breakdown = data.get("category_breakdown", [])
        self.assertEqual(len(cat_breakdown), 2)
        # Canteen Meals total: 350 + 200 = 550.00
        canteen_item = next((c for c in cat_breakdown if c["category"] == "Canteen Meals"), None)
        self.assertIsNotNone(canteen_item)
        self.assertEqual(canteen_item["amount"], 550.00)

        # Beverages total: 150.00
        bev_item = next((c for c in cat_breakdown if c["category"] == "Beverages"), None)
        self.assertIsNotNone(bev_item)
        self.assertEqual(bev_item["amount"], 150.00)

    # -------------------------------------------------------------
    # 3. Budgets & Goals Aggregation
    # -------------------------------------------------------------
    def test_budgets_and_goals_aggregation(self):
        """Accurately compares budget limits against category expenses and summarizes goals."""
        client, user_id, email = self._register_and_login_user("BudgetGoalUser")

        # Set budget: Canteen Meals = 1000.00
        client.post("/api/budgets", json={
            "category": "Canteen Meals",
            "amount_limit": 1000.00,
            "period": "monthly"
        })

        # Set goal: Semester Food Reserve = target 5000.00, saved 2000.00
        client.post("/api/goals", json={
            "title": "Semester Food Reserve",
            "target_amount": 5000.00,
            "current_amount": 2000.00,
            "target_date": "2026-12-31"
        })

        # Spend 400.00 in Canteen Meals
        client.post("/api/expenses", json={
            "amount": 400.00,
            "category": "Canteen Meals",
            "description": "Weekly meal coupons",
            "date": "2026-09-17"
        })

        res = client.get("/api/customer/financial-summary")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        # Budgets verification
        budgets = data.get("budgets", [])
        self.assertEqual(len(budgets), 1)
        b = budgets[0]
        self.assertEqual(b["category"], "Canteen Meals")
        self.assertEqual(b["amount_limit"], 1000.00)
        self.assertEqual(b["spent"], 400.00)
        self.assertEqual(b["remaining"], 600.00)
        self.assertEqual(b["percent_spent"], 40.0)
        self.assertEqual(b["status"], "on_track")

        # Goals verification
        goals = data.get("goals", [])
        self.assertEqual(len(goals), 1)
        g = goals[0]
        self.assertEqual(g["title"], "Semester Food Reserve")
        self.assertEqual(g["target_amount"], 5000.00)
        self.assertEqual(g["current_amount"], 2000.00)
        self.assertEqual(g["progress_percent"], 40.0)

    # -------------------------------------------------------------
    # 4. Large Transaction Lists & Query Capping
    # -------------------------------------------------------------
    def test_recent_transactions_chronological_and_capped(self):
        """Recent transactions combines expenses & income, orders by date desc, and caps at 10."""
        client, user_id, email = self._register_and_login_user("HighVolumeUser")

        # Create 8 expenses
        for i in range(1, 9):
            client.post("/api/expenses", json={
                "amount": 50.00 + i,
                "category": "Dining",
                "description": f"Expense #{i}",
                "date": f"2026-09-{i:02d}"
            })

        # Create 8 income records
        for i in range(1, 9):
            client.post("/api/income", json={
                "amount": 100.00 + i,
                "source": "Stipend",
                "description": f"Income #{i}",
                "date": f"2026-09-{10+i:02d}"
            })

        res = client.get("/api/customer/financial-summary")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        recent = data.get("recent_transactions", [])
        # Must be capped at exactly 10 items
        self.assertEqual(len(recent), 10)

        # Most recent date should be at the top (2026-09-18)
        self.assertEqual(recent[0]["date"], "2026-09-18")
        self.assertEqual(recent[0]["type"], "income")

    # -------------------------------------------------------------
    # 5. Multi-Tenant Data Isolation (No Cross-User Leaks)
    # -------------------------------------------------------------
    def test_multi_tenant_isolation(self):
        """User A's financial transactions, budgets, and goals are strictly isolated from User B."""
        client_a, user_a_id, _ = self._register_and_login_user("UserAlpha")
        client_b, user_b_id, _ = self._register_and_login_user("UserBeta")

        # User A creates records
        client_a.post("/api/income", json={"amount": 9000.00, "source": "A Funds", "description": "Secret A income", "date": "2026-09-17"})
        client_a.post("/api/expenses", json={"amount": 3000.00, "category": "A Dining", "description": "Secret A expense", "date": "2026-09-17"})
        client_a.post("/api/budgets", json={"category": "A Budget", "amount_limit": 4000.00})
        client_a.post("/api/goals", json={"title": "A Goal", "target_amount": 10000.00, "current_amount": 2500.00})

        # User B queries financial summary
        res_b = client_b.get("/api/customer/financial-summary")
        self.assertEqual(res_b.status_code, 200)
        b_data = res_b.get_json()

        # User B must have 0 income, 0 expenses, 0 budgets, 0 goals
        self.assertEqual(b_data["summary"]["total_income"], 0.00)
        self.assertEqual(b_data["summary"]["total_expenses"], 0.00)
        self.assertEqual(b_data["summary"]["net_balance"], 0.00)
        self.assertEqual(len(b_data["budgets"]), 0)
        self.assertEqual(len(b_data["goals"]), 0)
        self.assertEqual(len(b_data["recent_transactions"]), 0)

    # -------------------------------------------------------------
    # 6. Unauthenticated Access Rejected
    # -------------------------------------------------------------
    def test_unauthenticated_access_rejected(self):
        """Unauthenticated requests return 401 Unauthorized."""
        unauth = self.app.test_client()
        res = unauth.get("/api/customer/financial-summary")
        self.assertEqual(res.status_code, 401)


if __name__ == "__main__":
    unittest.main()
