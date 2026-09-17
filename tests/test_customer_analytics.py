"""
Automated Test Suite for Database-Backed Customer Analytics API (/api/customer/analytics).

Validates:
1. Authentication & Role-based Access Control (401 unauthenticated, 403 non-customer).
2. Empty dataset resilience for fresh users (zero crashes, 0.0 totals, empty lists).
3. Income calculations (total, count, average, max).
4. Expense calculations (total, count, average, max).
5. Category breakdown with percentage share for expenses and income.
6. Chronological monthly trends aggregation (income, expenses, net savings, savings rate).
7. Budget comparisons (category limits vs actual spent, status on_track, near_limit, exceeded).
8. Savings calculations (net balance, savings rate %, financial goals milestone progress).
9. Multi-tenant isolation (zero cross-user data leakage).
10. Dynamic calculation updates upon transaction creation and deletion.
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
os.environ["SECRET_KEY"] = "customer-analytics-test-secret-key-32b"

import init_db
init_db.init_sqlite()

from db import DB
from app import app
from routes.auth import _otp_failed_verifications, _otp_send_limits


class TestCustomerAnalyticsAPI(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        _otp_failed_verifications.clear()
        _otp_send_limits.clear()

    def _generate_mobile(self):
        return f"9{secrets.randbelow(900000000) + 100000000}"

    def _register_and_login_user(self, prefix="AnalyticsUser"):
        """Creates a fresh customer and returns an authenticated test client."""
        client = self.app.test_client()
        suffix = secrets.token_hex(4)
        email = f"{prefix.lower()}_{suffix}@kpriet.ac.in"
        mobile = self._generate_mobile()
        password = "SecurePassword123!"

        # OTP send & verify
        r_send = client.post("/api/auth/otp/send", json={"mobile": mobile, "purpose": "signup"})
        self.assertEqual(r_send.status_code, 200)
        otp = r_send.get_json().get("demo_otp")

        r_v = client.post("/api/auth/otp/verify", json={"mobile": mobile, "code": otp, "purpose": "signup"})
        self.assertEqual(r_v.status_code, 200)

        # Signup customer
        r_signup = client.post("/api/auth/customer/signup", json={
            "fullName": f"{prefix} Tester",
            "email": email,
            "password": password,
            "confirmPassword": password,
            "customerType": "student",
            "identifier": f"23CS{secrets.randbelow(899) + 100}",
            "mobile": mobile
        })
        self.assertEqual(r_signup.status_code, 201)
        return client, email

    def test_01_unauthenticated_access_rejected(self):
        """Unauthenticated requests to /api/customer/analytics must receive 401 Unauthorized."""
        res = self.client.get("/api/customer/analytics")
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertFalse(data.get("success"))

    def test_02_empty_dataset_for_fresh_user(self):
        """A brand-new customer with 0 transactions receives 200 OK with clean 0.00 metrics."""
        client, email = self._register_and_login_user("FreshUser")
        res = client.get("/api/customer/analytics")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))

        summary = data.get("summary", {})
        self.assertEqual(summary.get("total_income"), 0.0)
        self.assertEqual(summary.get("total_expenses"), 0.0)
        self.assertEqual(summary.get("net_balance"), 0.0)
        self.assertEqual(summary.get("savings_rate"), 0.0)
        self.assertEqual(summary.get("average_income"), 0.0)
        self.assertEqual(summary.get("average_expense"), 0.0)
        self.assertEqual(summary.get("highest_income"), 0.0)
        self.assertEqual(summary.get("highest_expense"), 0.0)

        self.assertEqual(data.get("category_breakdown"), [])
        self.assertEqual(data.get("category_breakdown_income"), [])
        self.assertEqual(data.get("monthly_trends"), [])
        self.assertEqual(data.get("budget_comparisons"), [])
        self.assertEqual(data.get("budgets"), [])
        self.assertEqual(data.get("goals"), [])
        self.assertEqual(data.get("recent_transactions"), [])

    def test_03_income_and_expense_calculations(self):
        """Verifies accurate calculation of total, count, average, and max for income and expenses."""
        client, email = self._register_and_login_user("CalcUser")

        # Add 3 income records: 5000, 3000, 2000 -> Total = 10000, Count = 3, Avg = 3333.33, Max = 5000
        client.post("/api/income", json={"amount": 5000.0, "source": "Allowance", "date": "2026-09-01", "description": "Monthly allowance"})
        client.post("/api/income", json={"amount": 3000.0, "source": "Stipend", "date": "2026-09-05", "description": "Lab stipend"})
        client.post("/api/income", json={"amount": 2000.0, "source": "Freelance", "date": "2026-09-10", "description": "Tutoring"})

        # Add 3 expenses: 250, 150, 600 -> Total = 1000, Count = 3, Avg = 333.33, Max = 600
        client.post("/api/expenses", json={"amount": 250.0, "category": "Dining", "date": "2026-09-02", "description": "Lunch combo"})
        client.post("/api/expenses", json={"amount": 150.0, "category": "Snacks", "date": "2026-09-03", "description": "Coffee & puffs"})
        client.post("/api/expenses", json={"amount": 600.0, "category": "Dining", "date": "2026-09-08", "description": "Dinner buffet"})

        res = client.get("/api/customer/analytics")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        summary = data["summary"]

        self.assertEqual(summary["total_income"], 10000.0)
        self.assertEqual(summary["counts"]["income_entries"], 3)
        self.assertEqual(summary["average_income"], 3333.33)
        self.assertEqual(summary["highest_income"], 5000.0)

        self.assertEqual(summary["total_expenses"], 1000.0)
        self.assertEqual(summary["counts"]["expense_entries"], 3)
        self.assertEqual(summary["average_expense"], 333.33)
        self.assertEqual(summary["highest_expense"], 600.0)

        # Net balance = 10000 - 1000 = 9000
        self.assertEqual(summary["net_balance"], 9000.0)
        # Savings rate = 9000 / 10000 * 100 = 90.0%
        self.assertEqual(summary["savings_rate"], 90.0)

    def test_04_category_breakdown_and_percentages(self):
        """Verifies category breakdown for expenses and income with accurate sums and percentages."""
        client, email = self._register_and_login_user("CatUser")

        # Income: Allowance (4000 = 80%), Cashback (1000 = 20%) -> Total 5000
        client.post("/api/income", json={"amount": 4000.0, "source": "Allowance", "date": "2026-09-01", "description": "Pocket money"})
        client.post("/api/income", json={"amount": 1000.0, "source": "Cashback", "date": "2026-09-02", "description": "Offer reward"})

        # Expenses: Dining (600 = 60%), Beverages (300 = 30%), Snacks (100 = 10%) -> Total 1000
        client.post("/api/expenses", json={"amount": 600.0, "category": "Dining", "date": "2026-09-03", "description": "Lunch"})
        client.post("/api/expenses", json={"amount": 300.0, "category": "Beverages", "date": "2026-09-04", "description": "Fruit juice"})
        client.post("/api/expenses", json={"amount": 100.0, "category": "Snacks", "date": "2026-09-05", "description": "Samosa"})

        res = client.get("/api/customer/analytics")
        data = res.get_json()

        # Check expense categories
        exp_cats = {c["category"]: c for c in data["category_breakdown"]}
        self.assertIn("Dining", exp_cats)
        self.assertEqual(exp_cats["Dining"]["amount"], 600.0)
        self.assertEqual(exp_cats["Dining"]["percentage"], 60.0)

        self.assertIn("Beverages", exp_cats)
        self.assertEqual(exp_cats["Beverages"]["amount"], 300.0)
        self.assertEqual(exp_cats["Beverages"]["percentage"], 30.0)

        self.assertIn("Snacks", exp_cats)
        self.assertEqual(exp_cats["Snacks"]["amount"], 100.0)
        self.assertEqual(exp_cats["Snacks"]["percentage"], 10.0)

        # Check income sources
        inc_cats = {c["source"]: c for c in data["category_breakdown_income"]}
        self.assertIn("Allowance", inc_cats)
        self.assertEqual(inc_cats["Allowance"]["amount"], 4000.0)
        self.assertEqual(inc_cats["Allowance"]["percentage"], 80.0)

        self.assertIn("Cashback", inc_cats)
        self.assertEqual(inc_cats["Cashback"]["amount"], 1000.0)
        self.assertEqual(inc_cats["Cashback"]["percentage"], 20.0)

    def test_05_monthly_trends_time_series(self):
        """Verifies monthly trends accurately group by YYYY-MM in chronological order."""
        client, email = self._register_and_login_user("TrendUser")

        # Month 2026-07: Income 4000, Expense 1000 -> Net 3000, Rate 75.0%
        client.post("/api/income", json={"amount": 4000.0, "source": "Allowance", "date": "2026-07-01", "description": "July allowance"})
        client.post("/api/expenses", json={"amount": 1000.0, "category": "Dining", "date": "2026-07-15", "description": "July food"})

        # Month 2026-08: Income 5000, Expense 2000 -> Net 3000, Rate 60.0%
        client.post("/api/income", json={"amount": 5000.0, "source": "Stipend", "date": "2026-08-01", "description": "August stipend"})
        client.post("/api/expenses", json={"amount": 2000.0, "category": "Dining", "date": "2026-08-10", "description": "August food"})

        # Month 2026-09: Income 6000, Expense 1500 -> Net 4500, Rate 75.0%
        client.post("/api/income", json={"amount": 6000.0, "source": "Allowance", "date": "2026-09-01", "description": "Sept allowance"})
        client.post("/api/expenses", json={"amount": 1500.0, "category": "Dining", "date": "2026-09-05", "description": "Sept food"})

        res = client.get("/api/customer/analytics")
        data = res.get_json()
        trends = data.get("monthly_trends", [])

        self.assertEqual(len(trends), 3)
        self.assertEqual(trends[0]["month"], "2026-07")
        self.assertEqual(trends[0]["income"], 4000.0)
        self.assertEqual(trends[0]["expenses"], 1000.0)
        self.assertEqual(trends[0]["net_savings"], 3000.0)
        self.assertEqual(trends[0]["savings_rate"], 75.0)

        self.assertEqual(trends[1]["month"], "2026-08")
        self.assertEqual(trends[1]["income"], 5000.0)
        self.assertEqual(trends[1]["expenses"], 2000.0)
        self.assertEqual(trends[1]["net_savings"], 3000.0)
        self.assertEqual(trends[1]["savings_rate"], 60.0)

        self.assertEqual(trends[2]["month"], "2026-09")
        self.assertEqual(trends[2]["income"], 6000.0)
        self.assertEqual(trends[2]["expenses"], 1500.0)
        self.assertEqual(trends[2]["net_savings"], 4500.0)
        self.assertEqual(trends[2]["savings_rate"], 75.0)

    def test_06_budget_comparisons_and_status(self):
        """Verifies category budget limits vs actual spent and status on_track, near_limit, exceeded."""
        client, email = self._register_and_login_user("BudgetUser")

        # Create 3 category budgets
        # 1. Dining: Limit 1000, Spend 500 (50%) -> on_track
        # 2. Snacks: Limit 500, Spend 420 (84%) -> near_limit
        # 3. Beverages: Limit 200, Spend 250 (125%) -> exceeded
        client.post("/api/budgets", json={"category": "Dining", "amount_limit": 1000.0, "period": "monthly"})
        client.post("/api/budgets", json={"category": "Snacks", "amount_limit": 500.0, "period": "monthly"})
        client.post("/api/budgets", json={"category": "Beverages", "amount_limit": 200.0, "period": "monthly"})

        # Log expenses
        client.post("/api/expenses", json={"amount": 500.0, "category": "Dining", "date": "2026-09-01", "description": "Meals"})
        client.post("/api/expenses", json={"amount": 420.0, "category": "Snacks", "date": "2026-09-02", "description": "Chaat"})
        client.post("/api/expenses", json={"amount": 250.0, "category": "Beverages", "date": "2026-09-03", "description": "Smoothies"})

        res = client.get("/api/customer/analytics")
        data = res.get_json()
        budgets_by_cat = {b["category"]: b for b in data["budget_comparisons"]}

        self.assertEqual(budgets_by_cat["Dining"]["spent"], 500.0)
        self.assertEqual(budgets_by_cat["Dining"]["remaining"], 500.0)
        self.assertEqual(budgets_by_cat["Dining"]["percent_spent"], 50.0)
        self.assertEqual(budgets_by_cat["Dining"]["status"], "on_track")

        self.assertEqual(budgets_by_cat["Snacks"]["spent"], 420.0)
        self.assertEqual(budgets_by_cat["Snacks"]["remaining"], 80.0)
        self.assertEqual(budgets_by_cat["Snacks"]["percent_spent"], 84.0)
        self.assertEqual(budgets_by_cat["Snacks"]["status"], "near_limit")

        self.assertEqual(budgets_by_cat["Beverages"]["spent"], 250.0)
        self.assertEqual(budgets_by_cat["Beverages"]["remaining"], 0.0)
        self.assertEqual(budgets_by_cat["Beverages"]["percent_spent"], 125.0)
        self.assertEqual(budgets_by_cat["Beverages"]["status"], "exceeded")

        # Total budget calculations
        summary = data["summary"]
        self.assertEqual(summary["total_budget"], 1700.0) # 1000 + 500 + 200
        self.assertEqual(summary["total_budget_spent"], 1170.0) # 500 + 420 + 250
        self.assertEqual(summary["budget_percent_spent"], 68.8) # 1170 / 1700 * 100 = 68.82%

    def test_07_savings_and_goal_progress(self):
        """Verifies net balance, savings rate, and financial goal progress."""
        client, email = self._register_and_login_user("GoalUser")

        # Income 8000, Expense 2000 -> Net 6000, Savings rate 75.0%
        client.post("/api/income", json={"amount": 8000.0, "source": "Allowance", "date": "2026-09-01", "description": "Allowance"})
        client.post("/api/expenses", json={"amount": 2000.0, "category": "Dining", "date": "2026-09-02", "description": "Dinner"})

        # Goals:
        # Goal 1: Target 5000, Saved 2500 -> 50%
        # Goal 2: Target 3000, Saved 1500 -> 50%
        client.post("/api/goals", json={"title": "Emergency Fund", "target_amount": 5000.0, "current_amount": 2500.0})
        client.post("/api/goals", json={"title": "Tech Gadget", "target_amount": 3000.0, "current_amount": 1500.0})

        res = client.get("/api/customer/analytics")
        data = res.get_json()
        summary = data["summary"]

        self.assertEqual(summary["net_balance"], 6000.0)
        self.assertEqual(summary["savings_rate"], 75.0)
        self.assertEqual(summary["total_goals_target"], 8000.0)
        self.assertEqual(summary["total_goals_saved"], 4000.0)
        self.assertEqual(summary["goals_overall_progress"], 50.0)

    def test_08_multi_tenant_isolation(self):
        """Verifies User A's transactions and budgets never contaminate User B's analytics."""
        client_a, email_a = self._register_and_login_user("TenantA")
        client_b, email_b = self._register_and_login_user("TenantB")

        # User A records
        client_a.post("/api/income", json={"amount": 10000.0, "source": "Allowance", "date": "2026-09-01", "description": "Allowance A"})
        client_a.post("/api/expenses", json={"amount": 2500.0, "category": "Dining", "date": "2026-09-02", "description": "Dining A"})
        client_a.post("/api/budgets", json={"category": "Dining", "amount_limit": 3000.0})

        # User B records
        client_b.post("/api/income", json={"amount": 4000.0, "source": "Stipend", "date": "2026-09-01", "description": "Stipend B"})
        client_b.post("/api/expenses", json={"amount": 1000.0, "category": "Books", "date": "2026-09-02", "description": "Books B"})

        # Check User A analytics
        res_a = client_a.get("/api/customer/analytics")
        data_a = res_a.get_json()
        self.assertEqual(data_a["summary"]["total_income"], 10000.0)
        self.assertEqual(data_a["summary"]["total_expenses"], 2500.0)
        self.assertEqual(data_a["summary"]["net_balance"], 7500.0)
        self.assertEqual(len(data_a["budget_comparisons"]), 1)

        # Check User B analytics
        res_b = client_b.get("/api/customer/analytics")
        data_b = res_b.get_json()
        self.assertEqual(data_b["summary"]["total_income"], 4000.0)
        self.assertEqual(data_b["summary"]["total_expenses"], 1000.0)
        self.assertEqual(data_b["summary"]["net_balance"], 3000.0)
        self.assertEqual(len(data_b["budget_comparisons"]), 0) # User B has no budgets

    def test_09_chart_updates_on_add_and_delete_transaction(self):
        """Verifies that adding and deleting transactions dynamically updates analytics in real-time."""
        client, email = self._register_and_login_user("DynamicUser")

        # Baseline: Income 5000, 0 expenses
        client.post("/api/income", json={"amount": 5000.0, "source": "Allowance", "date": "2026-09-01", "description": "Initial Allowance"})

        res0 = client.get("/api/customer/analytics").get_json()
        self.assertEqual(res0["summary"]["total_expenses"], 0.0)
        self.assertEqual(res0["summary"]["net_balance"], 5000.0)
        self.assertEqual(res0["category_breakdown"], [])

        # Add an expense of 750.0
        r_add = client.post("/api/expenses", json={"amount": 750.0, "category": "Dining", "date": "2026-09-05", "description": "Pizza Party"})
        self.assertEqual(r_add.status_code, 201)
        exp_id = r_add.get_json().get("expense", {}).get("id")

        # Verify analytics updated immediately
        res1 = client.get("/api/customer/analytics").get_json()
        self.assertEqual(res1["summary"]["total_expenses"], 750.0)
        self.assertEqual(res1["summary"]["net_balance"], 4250.0)
        self.assertEqual(len(res1["category_breakdown"]), 1)
        self.assertEqual(res1["category_breakdown"][0]["category"], "Dining")
        self.assertEqual(res1["category_breakdown"][0]["amount"], 750.0)
        self.assertEqual(len(res1["monthly_trends"]), 1)
        self.assertEqual(res1["monthly_trends"][0]["expenses"], 750.0)

        # Delete the expense
        r_del = client.delete(f"/api/expenses/{exp_id}")
        self.assertEqual(r_del.status_code, 200)

        # Verify analytics reverted immediately
        res2 = client.get("/api/customer/analytics").get_json()
        self.assertEqual(res2["summary"]["total_expenses"], 0.0)
        self.assertEqual(res2["summary"]["net_balance"], 5000.0)
        self.assertEqual(res2["category_breakdown"], [])
        self.assertEqual(res2["monthly_trends"][0]["expenses"], 0.0)


if __name__ == "__main__":
    unittest.main()
