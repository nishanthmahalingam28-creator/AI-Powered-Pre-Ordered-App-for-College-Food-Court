"""
Comprehensive Security & Authentication Test Suite.
Verifies all requirements for secure real authentication:
1. Valid registration creates real user in database with bcrypt hashed password.
2. Duplicate email registration is strictly rejected (409 Conflict).
3. Incorrect password login is rejected (401 Unauthorized).
4. Correct password login succeeds (200 OK, sets session cookie, verifies bcrypt hash).
5. Empty fields on registration and login are rejected (400 Bad Request).
6. Logout invalidates session and subsequent authenticated checks fail.
7. Accessing protected endpoints without authentication is rejected (401 Unauthorized).
8. Bcrypt password security: passwords never stored in plaintext, proper salt and cost factor.
"""

import os
import sys
import secrets
import unittest
import bcrypt

# Ensure backend directory is on sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ["FLASK_ENV"] = "development"
os.environ["USE_SQLITE"] = "1"
os.environ["SECRET_KEY"] = "secure-auth-test-key-32b-secret-min"

import init_db
init_db.init_sqlite()

from db import DB
from app import app
from security import hash_password, verify_password
from routes.auth import _otp_failed_verifications, _otp_send_limits


class TestSecureAuthentication(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        _otp_failed_verifications.clear()
        _otp_send_limits.clear()

    def _generate_mobile(self):
        return f"9{secrets.randbelow(900000000) + 100000000}"

    def _verify_otp_for_mobile(self, mobile, purpose="signup"):
        res = self.client.post("/api/auth/otp/send", json={"mobile": mobile, "purpose": purpose})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        code = data.get("demo_otp")
        self.assertTrue(bool(code), "Dev demo_otp should be returned for test setup")

        v_res = self.client.post("/api/auth/otp/verify", json={"mobile": mobile, "code": code, "purpose": purpose})
        self.assertEqual(v_res.status_code, 200)
        return code

    # =========================================================================
    # Requirement 4 & 3: Bcrypt security verification
    # =========================================================================
    def test_bcrypt_hashing_and_verification(self):
        """Verify hash_password produces valid bcrypt hash and verify_password behaves correctly."""
        raw_pw = "SecureP@ssw0rd!2026"
        hashed = hash_password(raw_pw)

        # 1. Must never equal raw plaintext
        self.assertNotEqual(raw_pw, hashed)
        # 2. Must start with standard bcrypt identifier $2b$ or $2a$
        self.assertTrue(hashed.startswith("$2b$") or hashed.startswith("$2a$"))
        # 3. Must be 60 characters long
        self.assertEqual(len(hashed), 60)
        # 4. Correct password must verify
        self.assertTrue(verify_password(raw_pw, hashed))
        # 5. Wrong password must fail
        self.assertFalse(verify_password("WrongPassword999", hashed))
        # 6. Direct bcrypt library checkpw must confirm valid hash
        self.assertTrue(bcrypt.checkpw(raw_pw.encode("utf-8"), hashed.encode("utf-8")))

    # =========================================================================
    # Test Case 1: Valid registration creates real user in database
    # =========================================================================
    def test_case_1_valid_registration(self):
        """Registration must create a real user in the database with bcrypt hash and unique id."""
        suffix = secrets.token_hex(4)
        email = f"auth_test_{suffix}@kpriet.ac.in"
        mobile = self._generate_mobile()
        password = "ValidPassword123!"

        self._verify_otp_for_mobile(mobile, "signup")

        payload = {
            "fullName": "Test User Alpha",
            "email": email,
            "password": password,
            "mobile": mobile,
            "customerType": "student",
            "identifier": f"21CS{secrets.randbelow(899) + 100}"
        }

        res = self.client.post("/api/auth/customer/signup", json=payload)
        self.assertEqual(res.status_code, 201, f"Signup failed: {res.get_json()}")
        data = res.get_json()
        self.assertTrue(data.get("success"))

        # Verify in real database: User record exists
        user_row = DB.get_one("SELECT id, email, password_hash, role, is_active FROM users WHERE email = %s", (email,))
        self.assertIsNotNone(user_row, "User must exist in the database users table")
        self.assertEqual(user_row["email"], email)
        self.assertEqual(user_row["role"], "customer")
        self.assertEqual(user_row["is_active"], 1)

        # Verify password is NEVER plaintext in DB
        db_hash = user_row["password_hash"]
        self.assertNotEqual(db_hash, password)
        self.assertTrue(db_hash.startswith("$2b$") or db_hash.startswith("$2a$"))
        self.assertTrue(bcrypt.checkpw(password.encode("utf-8"), db_hash.encode("utf-8")))

        # Verify customer profile record exists
        profile_row = DB.get_one("SELECT id, full_name, mobile, customer_type FROM customer_profiles WHERE user_id = %s", (user_row["id"],))
        self.assertIsNotNone(profile_row, "Customer profile must exist in database")
        self.assertEqual(profile_row["full_name"], payload["fullName"])
        self.assertEqual(profile_row["mobile"], mobile)

    # =========================================================================
    # Test Case 2: Duplicate email registration
    # =========================================================================
    def test_case_2_duplicate_email_rejection(self):
        """Registration must reject existing email addresses with 409 Conflict."""
        suffix = secrets.token_hex(4)
        email = f"dup_{suffix}@kpriet.ac.in"
        mobile1 = self._generate_mobile()
        password = "Password123!"

        self._verify_otp_for_mobile(mobile1, "signup")
        payload1 = {
            "fullName": "User One Primary",
            "email": email,
            "password": password,
            "mobile": mobile1,
            "customerType": "student",
            "identifier": f"21CS{secrets.randbelow(899) + 100}"
        }
        res1 = self.client.post("/api/auth/customer/signup", json=payload1)
        self.assertEqual(res1.status_code, 201)

        # Attempt to register second account with same email (even with different mobile)
        mobile2 = self._generate_mobile()
        self._verify_otp_for_mobile(mobile2, "signup")
        payload2 = {
            "fullName": "User Two Duplicate",
            "email": email,
            "password": "DifferentPassword123!",
            "mobile": mobile2,
            "customerType": "student",
            "identifier": f"21CS{secrets.randbelow(899) + 100}"
        }
        res2 = self.client.post("/api/auth/customer/signup", json=payload2)
        self.assertEqual(res2.status_code, 409, "Duplicate email must return 409 Conflict")
        data2 = res2.get_json()
        self.assertFalse(data2.get("success"))
        self.assertIn("already exists", data2.get("message", "").lower())

    # =========================================================================
    # Test Case 3: Incorrect password rejection
    # =========================================================================
    def test_case_3_incorrect_password(self):
        """Login must reject incorrect passwords with 401 Unauthorized."""
        suffix = secrets.token_hex(4)
        email = f"auth_wrong_{suffix}@kpriet.ac.in"
        mobile = self._generate_mobile()
        correct_pw = "CorrectP@ssword123"

        self._verify_otp_for_mobile(mobile, "signup")
        self.client.post("/api/auth/customer/signup", json={
            "fullName": "Wrong Password Test",
            "email": email,
            "password": correct_pw,
            "mobile": mobile,
            "customerType": "student",
            "identifier": f"21CS{secrets.randbelow(899) + 100}"
        })

        # Attempt login with incorrect password
        res = self.client.post("/api/auth/customer/login", json={
            "email": email,
            "password": "WrongPassword999!"
        })
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertFalse(data.get("success"))
        self.assertIn("invalid", data.get("message", "").lower())

        # Verify session was NOT created
        me_res = self.client.get("/api/auth/me")
        me_data = me_res.get_json()
        self.assertFalse(me_data.get("authenticated"))

    # =========================================================================
    # Test Case 4: Correct password login
    # =========================================================================
    def test_case_4_correct_password_login(self):
        """Login with correct credentials succeeds, sets session cookie, and authorizes user."""
        suffix = secrets.token_hex(4)
        email = f"auth_correct_{suffix}@kpriet.ac.in"
        mobile = self._generate_mobile()
        correct_pw = "RightPassword123!"

        self._verify_otp_for_mobile(mobile, "signup")
        self.client.post("/api/auth/customer/signup", json={
            "fullName": "Correct User",
            "email": email,
            "password": correct_pw,
            "mobile": mobile,
            "customerType": "student",
            "identifier": f"21CS{secrets.randbelow(899) + 100}"
        })

        # Login with correct password
        res = self.client.post("/api/auth/customer/login", json={
            "email": email,
            "password": correct_pw
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("user", {}).get("email"), email)

        # Verify session cookie was set in response
        cookie_header = res.headers.get("Set-Cookie")
        self.assertIsNotNone(cookie_header, "Set-Cookie header must be present")
        self.assertIn("session=", cookie_header)
        self.assertIn("HttpOnly", cookie_header)

        # Verify /auth/me returns authenticated state with user info
        me_res = self.client.get("/api/auth/me")
        self.assertEqual(me_res.status_code, 200)
        me_data = me_res.get_json()
        self.assertTrue(me_data.get("authenticated"))
        self.assertEqual(me_data.get("user", {}).get("email"), email)
        self.assertEqual(me_data.get("user", {}).get("role"), "customer")

    # =========================================================================
    # Test Case 5: Empty fields handling
    # =========================================================================
    def test_case_5_empty_fields(self):
        """Registration and login must reject empty fields and non-existent users with 400."""
        # 1. Registration with empty email
        res1 = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Empty Email",
            "email": "",
            "password": "Password123!",
            "mobile": "9876543210",
            "customerType": "student",
            "identifier": "21CS101"
        })
        self.assertEqual(res1.status_code, 400)

        # 2. Registration with empty password
        res2 = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Empty Password",
            "email": "valid@kpriet.ac.in",
            "password": "",
            "mobile": "9876543210",
            "customerType": "student",
            "identifier": "21CS101"
        })
        self.assertEqual(res2.status_code, 400)

        # 3. Registration with empty full name
        res3 = self.client.post("/api/auth/customer/signup", json={
            "fullName": "",
            "email": "valid@kpriet.ac.in",
            "password": "Password123!",
            "mobile": "9876543210",
            "customerType": "student",
            "identifier": "21CS101"
        })
        self.assertEqual(res3.status_code, 400)

        # 4. Login with empty email
        res4 = self.client.post("/api/auth/customer/login", json={
            "email": "",
            "password": "Password123!"
        })
        self.assertEqual(res4.status_code, 400)

        # 5. Login with empty password
        res5 = self.client.post("/api/auth/customer/login", json={
            "email": "student@kpriet.ac.in",
            "password": ""
        })
        self.assertEqual(res5.status_code, 400)

        # 6. Login with random non-existent email and non-empty password (must reject, not allow)
        res6 = self.client.post("/api/auth/customer/login", json={
            "email": "nonexistent_random_user_999@kpriet.ac.in",
            "password": "AnyRandomPassword123!"
        })
        self.assertEqual(res6.status_code, 401)
        self.assertFalse(res6.get_json().get("success"))

    # =========================================================================
    # Test Case 6: Logout invalidates session
    # =========================================================================
    def test_case_6_logout_invalidates_session(self):
        """Logout must clear session state and invalidate access to protected endpoints."""
        # Login first as standard student
        login_res = self.client.post("/api/auth/customer/login", json={
            "email": "student@kpriet.ac.in",
            "password": "password123"
        })
        self.assertEqual(login_res.status_code, 200)

        # Verify active session
        me1 = self.client.get("/api/auth/me")
        self.assertTrue(me1.get_json().get("authenticated"))

        # Logout
        logout_res = self.client.post("/api/auth/logout")
        self.assertEqual(logout_res.status_code, 200)
        self.assertTrue(logout_res.get_json().get("success"))

        # Invalidate check: /auth/me must report unauthenticated
        me2 = self.client.get("/api/auth/me")
        self.assertFalse(me2.get_json().get("authenticated"))

        # Invalidate check: accessing protected customer profile must return 401
        prof_res = self.client.get("/api/customer/profile")
        self.assertEqual(prof_res.status_code, 401)

    # =========================================================================
    # Test Case 7: Accessing protected pages/endpoints without authentication
    # =========================================================================
    def test_case_7_accessing_protected_endpoints_without_authentication(self):
        """Protected endpoints must reject unauthenticated requests with 401 Unauthorized."""
        unauthed_client = self.app.test_client()

        # 1. Customer Profile
        res = unauthed_client.get("/api/customer/profile")
        self.assertEqual(res.status_code, 401)

        # 2. Customer Password Change
        res = unauthed_client.put("/api/customer/password", json={"old_password": "a", "new_password": "b"})
        self.assertEqual(res.status_code, 401)

        # 3. Customer Orders (Expenses & Bills)
        res = unauthed_client.get("/api/orders/my-orders")
        self.assertEqual(res.status_code, 401)

        # 4. Shopping Cart
        res = unauthed_client.get("/api/cart")
        self.assertEqual(res.status_code, 401)

        # 5. Vendor Stall Dashboard
        res = unauthed_client.get("/api/vendor/shop")
        self.assertEqual(res.status_code, 401)

        # 6. Admin Analytics / Overview
        res = unauthed_client.get("/api/admin/overview")
        self.assertEqual(res.status_code, 401)

        # 7. AI Assistant / Personalized Recommendations
        res = unauthed_client.get("/api/ai/recommendations")
        self.assertEqual(res.status_code, 401)


if __name__ == "__main__":
    unittest.main()
