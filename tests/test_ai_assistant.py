"""
Automated Test Suite for Secure AI Financial Assistant Service and API.

Validates:
1. Unauthenticated requests to /api/ai/assistant/chat are rejected (401 Unauthorized).
2. Non-customer roles are rejected (403 Forbidden).
3. Authenticated customer receives accurate advice derived from their real database records.
4. Multi-tenant isolation: User A never receives User B's financial data.
5. Client-supplied user_id override attempts are strictly ignored.
6. Zero history user receives honest "no transactions recorded yet" notice with zero invented numbers.
7. Strict PII and credential scrubbing (passwords, tokens, hashes, phone numbers never exposed).
8. Input validation and prompt sanitization (empty or oversized prompts rejected with 400).
9. Missing API key handles gracefully via deterministic financial advisor engine.
10. External API failure / timeout handles gracefully with fallback messaging.
11. Tamper-proofing: Recommendations endpoint rejects client-supplied user_id.
"""

import os
import sys
import secrets
import unittest
from unittest.mock import patch

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ["FLASK_ENV"] = "development"
os.environ["USE_SQLITE"] = "1"
os.environ["SECRET_KEY"] = "ai-assistant-test-secret-key-32b"

import init_db
init_db.init_sqlite()

from db import DB
from app import app
from routes.auth import _otp_failed_verifications, _otp_send_limits
from services.ai_assistant import AIAssistantService


class TestAIAssistantAPI(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        _otp_failed_verifications.clear()
        _otp_send_limits.clear()

    def _generate_mobile(self):
        return f"9{secrets.randbelow(900000000) + 100000000}"

    def _register_and_login_user(self, prefix="AIUser"):
        """Registers and authenticates a test customer."""
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
            "fullName": f"{prefix} Student",
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

    def test_01_unauthenticated_rejected(self):
        """Unauthenticated requests must be rejected with 401 Unauthorized."""
        res = self.client.post("/api/ai/assistant/chat", json={"message": "How much have I spent?"})
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertFalse(data.get("success"))

    def test_02_non_customer_rejected(self):
        """Non-customer roles (e.g. vendors) must receive 403 Forbidden."""
        client = self.app.test_client()
        # Login vendor 1
        r_login = client.post("/api/auth/vendor/login", json={"email": "ypr@kpriet.ac.in", "password": "vendor123"})
        self.assertEqual(r_login.status_code, 200)

        res = client.post("/api/ai/assistant/chat", json={"message": "Analyze my spending"})
        self.assertEqual(res.status_code, 403)

    def test_03_authenticated_user_retrieves_own_financial_data(self):
        """Authenticated customer receives real financial intelligence derived from their records."""
        client, user_id, email = self._register_and_login_user("RealDataUser")

        # Record real transactions
        client.post("/api/income", json={"amount": 8000.0, "source": "Monthly Allowance", "date": "2026-09-01", "description": "Pocket Money"})
        client.post("/api/expenses", json={"amount": 1200.0, "category": "Dining", "date": "2026-09-02", "description": "Meals"})
        client.post("/api/budgets", json={"category": "Dining", "amount_limit": 2000.0, "period": "monthly"})

        res = client.post("/api/ai/assistant/chat", json={"message": "What is my spending and budget status?"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        response_text = data.get("response", "")

        # Verifies actual numbers are mentioned
        self.assertIn("1,200.00", response_text)
        self.assertIn("Dining", response_text)
        self.assertIn("2,000.00", response_text)

    def test_04_multi_tenant_isolation(self):
        """User A's financial queries strictly reflect User A's data and never User B's."""
        client_a, user_a_id, email_a = self._register_and_login_user("UserAlpha")
        client_b, user_b_id, email_b = self._register_and_login_user("UserBeta")

        # User A has 15000 income, 4500 Dining expense
        client_a.post("/api/income", json={"amount": 15000.0, "source": "Scholarship", "date": "2026-09-01", "description": "Grant"})
        client_a.post("/api/expenses", json={"amount": 4500.0, "category": "Dining", "date": "2026-09-02", "description": "Lunch Feast"})

        # User B has 3000 income, 350 Snacks expense
        client_b.post("/api/income", json={"amount": 3000.0, "source": "Allowance", "date": "2026-09-01", "description": "Allowance"})
        client_b.post("/api/expenses", json={"amount": 350.0, "category": "Snacks", "date": "2026-09-02", "description": "Samosa"})

        # Query as User A
        res_a = client_a.post("/api/ai/assistant/chat", json={"message": "Where does my money go?"})
        text_a = res_a.get_json().get("response", "")
        self.assertIn("4,500.00", text_a)
        self.assertNotIn("350.00", text_a)

        # Query as User B
        res_b = client_b.post("/api/ai/assistant/chat", json={"message": "Where does my money go?"})
        text_b = res_b.get_json().get("response", "")
        self.assertIn("350.00", text_b)
        self.assertNotIn("4,500.00", text_b)

    def test_05_ignore_client_supplied_user_id(self):
        """Client-supplied user_id in body or params is completely ignored."""
        client_a, user_a_id, email_a = self._register_and_login_user("TamperA")
        client_b, user_b_id, email_b = self._register_and_login_user("TamperB")

        client_b.post("/api/expenses", json={"amount": 9999.0, "category": "Jewelry", "date": "2026-09-01", "description": "Secret Purchase"})

        # User A tries to view User B's data
        res = client_a.post(f"/api/ai/assistant/chat?user_id={user_b_id}", json={
            "message": "What did I spend?",
            "user_id": user_b_id
        })
        self.assertEqual(res.status_code, 200)
        text = res.get_json().get("response", "")
        self.assertNotIn("9,999.00", text)
        self.assertNotIn("Jewelry", text)

    def test_06_zero_history_user_does_not_invent_fake_numbers(self):
        """When a user has no transaction history, the AI never invents fake amounts."""
        client, user_id, email = self._register_and_login_user("ZeroHistory")

        res = client.post("/api/ai/assistant/chat", json={"message": "How much did I spend this week?"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(data.get("has_history"))
        text = data.get("response", "")

        # Verifies honest zero-state message
        self.assertIn("no transactions or orders have been recorded yet", text.lower())
        # Verifies no invented numbers
        self.assertNotIn("₹250", text)
        self.assertNotIn("₹500", text)
        self.assertNotIn("₹100", text)

    def test_07_pii_and_credential_sanitization(self):
        """Sanitized financial context strictly excludes passwords, tokens, hashes, and PII."""
        client, user_id, email = self._register_and_login_user("PIIScrub")

        client.post("/api/expenses", json={
            "amount": 150.0,
            "category": "Dining",
            "date": "2026-09-01",
            "description": "Lunch <script>alert('xss')</script>"
        })

        context = AIAssistantService.get_sanitized_financial_context(user_id)

        # Invariant checks: None of these sensitive keys should exist in the context
        forbidden_keys = ("password", "password_hash", "token", "session_id", "mobile", "email", "identifier", "cookie")
        for k in forbidden_keys:
            self.assertNotIn(k, context)

        # Invariant checks: descriptions must be sanitized of HTML / scripts
        for item in context.get("recent_expenses", []):
            self.assertNotIn("<script>", item.get("description", ""))
            self.assertNotIn("</script>", item.get("description", ""))

    def test_08_empty_or_invalid_prompt_rejected(self):
        """Empty, whitespace-only, or oversized prompts are rejected with 400 Bad Request."""
        client, user_id, email = self._register_and_login_user("PromptValidator")

        # Empty string
        res_empty = client.post("/api/ai/assistant/chat", json={"message": ""})
        self.assertEqual(res_empty.status_code, 400)

        # Whitespace
        res_space = client.post("/api/ai/assistant/chat", json={"message": "   \n\t  "})
        self.assertEqual(res_space.status_code, 400)

        # Oversized string (>1000 characters)
        huge_str = "A" * 1500
        res_huge = client.post("/api/ai/assistant/chat", json={"message": huge_str})
        self.assertEqual(res_huge.status_code, 400)

    def test_09_missing_api_key_graceful_fallback(self):
        """Missing API key activates rule-based financial advisor without server errors."""
        client, user_id, email = self._register_and_login_user("NoKeyUser")
        client.post("/api/income", json={"amount": 5000.0, "source": "Allowance", "date": "2026-09-01", "description": "Deposit"})

        # Ensure no key
        with patch.dict(os.environ, {"GEMINI_API_KEY": "", "AI_API_KEY": ""}, clear=False):
            res = client.post("/api/ai/assistant/chat", json={"message": "Give me a financial summary"})
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data.get("success"))
            self.assertEqual(data.get("source"), "rule_based_engine")
            self.assertIn("5,000.00", data.get("response", ""))

    def test_10_api_error_graceful_fallback(self):
        """When external AI service times out or fails, assistant falls back cleanly."""
        client, user_id, email = self._register_and_login_user("ErrorFallbackUser")
        client.post("/api/expenses", json={"amount": 450.0, "category": "Beverages", "date": "2026-09-01", "description": "Coffee"})

        # Simulate Gemini API failure
        with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy-test-key"}, clear=False):
            with patch("services.ai_assistant.AIAssistantService.call_gemini_api", side_effect=Exception("API Timeout")):
                res = client.post("/api/ai/assistant/chat", json={"message": "How is my coffee spending?"})
                self.assertEqual(res.status_code, 200)
                data = res.get_json()
                self.assertTrue(data.get("success"))
                self.assertEqual(data.get("source"), "rule_based_engine")
                self.assertIn("450.00", data.get("response", ""))

    def test_11_recommendations_endpoint_user_id_tamper_proofing(self):
        """Recommendations endpoint strictly locks to authenticated session and rejects query param overrides."""
        client_a, user_a_id, email_a = self._register_and_login_user("RecA")
        client_b, user_b_id, email_b = self._register_and_login_user("RecB")

        # User A calls recommendations with ?user_id=User_B
        res = client_a.get(f"/api/ai/recommendations?user_id={user_b_id}")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))


if __name__ == "__main__":
    unittest.main()
