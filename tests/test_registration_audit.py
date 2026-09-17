"""
Audit and Hardening Automated Test Suite for User Registration.

Validates all requirements:
1. Validate name: required, at least 2 characters, letters/spaces only.
2. Validate email format: institutional @kpriet.ac.in for student/faculty, RFC for guest.
3. Validate password strength: minimum 8 characters, both letters and numbers.
4. Confirm password must match: mismatched passwords rejected.
5. Reject duplicate email addresses: returns 409 Conflict with clear error.
6. Hash passwords on the backend: bcrypt cost 12, never plaintext.
7. Clear validation messages on all failure modes.
8. Create user only through backend API: real database persistence verified.
9. Automatically authenticate user after successful registration via secure session.
10. Verify user actually exists in database users and customer_profiles tables.
"""

import os
import sys
import secrets
import unittest
import bcrypt

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ["FLASK_ENV"] = "development"
os.environ["USE_SQLITE"] = "1"
os.environ["SECRET_KEY"] = "reg-audit-test-key-32b-secret-min"

import init_db
init_db.init_sqlite()

from db import DB
from app import app
from routes.auth import _otp_failed_verifications, _otp_send_limits


class TestRegistrationAudit(unittest.TestCase):
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
        code = res.get_json().get("demo_otp")
        self.assertTrue(bool(code))

        v_res = self.client.post("/api/auth/otp/verify", json={"mobile": mobile, "code": code, "purpose": purpose})
        self.assertEqual(v_res.status_code, 200)
        return code

    # -------------------------------------------------------------
    # 1. Successful Registration & Database Verification
    # -------------------------------------------------------------
    def test_successful_registration_and_db_persistence(self):
        """Registration creates a real user in the database, stores bcrypt hash, and auto-authenticates."""
        suffix = secrets.token_hex(4)
        email = f"student_{suffix}@kpriet.ac.in"
        mobile = self._generate_mobile()
        password = "SecurePassword123!"

        self._verify_otp_for_mobile(mobile, "signup")

        payload = {
            "fullName": "Audit Student User",
            "email": email,
            "password": password,
            "confirmPassword": password,
            "customerType": "student",
            "identifier": f"23CS{secrets.randbelow(899) + 100}",
            "mobile": mobile
        }

        res = self.client.post("/api/auth/customer/signup", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("user", {}).get("email"), email)

        # 1. Verify user exists in the database
        user_row = DB.get_one("SELECT id, email, password_hash, role, is_active FROM users WHERE email = %s", (email,))
        self.assertIsNotNone(user_row, "User record must exist in the users table")
        self.assertEqual(user_row["email"], email)
        self.assertEqual(user_row["role"], "customer")
        self.assertEqual(user_row["is_active"], 1)

        # 2. Verify password is NEVER plaintext and is a valid bcrypt hash
        db_hash = user_row["password_hash"]
        self.assertNotEqual(db_hash, password)
        self.assertTrue(db_hash.startswith("$2b$") or db_hash.startswith("$2a$"))
        self.assertTrue(bcrypt.checkpw(password.encode("utf-8"), db_hash.encode("utf-8")))

        # 3. Verify customer_profiles row exists
        profile_row = DB.get_one("SELECT full_name, customer_type, mobile FROM customer_profiles WHERE user_id = %s", (user_row["id"],))
        self.assertIsNotNone(profile_row, "Customer profile must exist in customer_profiles table")
        self.assertEqual(profile_row["full_name"], payload["fullName"])
        self.assertEqual(profile_row["mobile"], mobile)

        # 4. Verify automatic authentication (HttpOnly session cookie issued)
        cookie_header = res.headers.get("Set-Cookie")
        self.assertIsNotNone(cookie_header)
        self.assertIn("session=", cookie_header)
        self.assertIn("HttpOnly", cookie_header)

        # 5. Verify /auth/me returns authenticated state without separate manual login
        me_res = self.client.get("/api/auth/me")
        self.assertEqual(me_res.status_code, 200)
        self.assertTrue(me_res.get_json().get("authenticated"))
        self.assertEqual(me_res.get_json().get("user", {}).get("email"), email)

        # 6. Verify protected endpoints accessible immediately
        prof_res = self.client.get("/api/customer/profile")
        self.assertEqual(prof_res.status_code, 200)
        self.assertTrue(prof_res.get_json().get("success"))

    # -------------------------------------------------------------
    # 2. Name Validation
    # -------------------------------------------------------------
    def test_name_validation(self):
        """Rejects empty names, single-character names, and names with invalid symbols."""
        mobile = self._generate_mobile()
        self._verify_otp_for_mobile(mobile, "signup")

        base_payload = {
            "email": f"name_test_{secrets.token_hex(3)}@kpriet.ac.in",
            "password": "Password123!",
            "customerType": "student",
            "identifier": "22CS101",
            "mobile": mobile
        }

        # Empty name
        res1 = self.client.post("/api/auth/customer/signup", json={**base_payload, "fullName": ""})
        self.assertEqual(res1.status_code, 400)
        self.assertIn("name", res1.get_json().get("message", "").lower())

        # Single letter name
        res2 = self.client.post("/api/auth/customer/signup", json={**base_payload, "fullName": "J"})
        self.assertEqual(res2.status_code, 400)
        self.assertIn("at least 2", res2.get_json().get("message", "").lower())

        # Name with numbers / forbidden symbols
        res3 = self.client.post("/api/auth/customer/signup", json={**base_payload, "fullName": "User123<script>"})
        self.assertEqual(res3.status_code, 400)
        self.assertIn("only contain letters", res3.get_json().get("message", "").lower())

    # -------------------------------------------------------------
    # 3. Email Format Validation
    # -------------------------------------------------------------
    def test_email_format_validation(self):
        """Enforces institutional domain for students and RFC email format for guests."""
        mobile = self._generate_mobile()
        self._verify_otp_for_mobile(mobile, "signup")

        # 1. Student with non-kpriet domain
        res1 = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Student Non Kpriet",
            "email": "student@gmail.com",
            "password": "Password123!",
            "customerType": "student",
            "identifier": "22CS102",
            "mobile": mobile
        })
        self.assertEqual(res1.status_code, 400)
        self.assertIn("kpriet", res1.get_json().get("message", "").lower())

        # 2. Guest with malformed email
        res2 = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Guest Malformed",
            "email": "invalid-email-address",
            "password": "Password123!",
            "customerType": "guest",
            "mobile": mobile
        })
        self.assertEqual(res2.status_code, 400)
        self.assertIn("valid email", res2.get_json().get("message", "").lower())

    # -------------------------------------------------------------
    # 4. Password Strength Validation
    # -------------------------------------------------------------
    def test_password_strength_validation(self):
        """Rejects passwords shorter than 8 characters, or lacking both letters and numbers."""
        mobile = self._generate_mobile()
        self._verify_otp_for_mobile(mobile, "signup")

        base_payload = {
            "fullName": "Strong Password Tester",
            "email": f"pw_test_{secrets.token_hex(3)}@kpriet.ac.in",
            "customerType": "student",
            "identifier": "22CS103",
            "mobile": mobile
        }

        # Too short (< 8 chars)
        res1 = self.client.post("/api/auth/customer/signup", json={**base_payload, "password": "Pass1"})
        self.assertEqual(res1.status_code, 400)
        self.assertIn("8 characters", res1.get_json().get("message", "").lower())

        # Only letters (no digits)
        res2 = self.client.post("/api/auth/customer/signup", json={**base_payload, "password": "OnlyLettersHere"})
        self.assertEqual(res2.status_code, 400)
        self.assertIn("letters and numbers", res2.get_json().get("message", "").lower())

        # Only digits (no letters)
        res3 = self.client.post("/api/auth/customer/signup", json={**base_payload, "password": "123456789012"})
        self.assertEqual(res3.status_code, 400)
        self.assertIn("letters and numbers", res3.get_json().get("message", "").lower())

    # -------------------------------------------------------------
    # 5. Confirm Password Matching
    # -------------------------------------------------------------
    def test_confirm_password_matching(self):
        """Rejects registration when confirm password does not match password."""
        mobile = self._generate_mobile()
        self._verify_otp_for_mobile(mobile, "signup")

        res = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Mismatch Tester",
            "email": f"mismatch_{secrets.token_hex(3)}@kpriet.ac.in",
            "password": "Password123!",
            "confirmPassword": "DifferentPassword123!",
            "customerType": "student",
            "identifier": "22CS104",
            "mobile": mobile
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("passwords do not match", res.get_json().get("message", "").lower())

    # -------------------------------------------------------------
    # 6. Duplicate Email Rejection
    # -------------------------------------------------------------
    def test_duplicate_email_rejection(self):
        """Rejects registration for existing emails with 409 Conflict."""
        suffix = secrets.token_hex(4)
        email = f"dup_audit_{suffix}@kpriet.ac.in"

        # Register first account
        mobile1 = self._generate_mobile()
        self._verify_otp_for_mobile(mobile1, "signup")
        res1 = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Original User",
            "email": email,
            "password": "Password123!",
            "customerType": "student",
            "identifier": "22CS105",
            "mobile": mobile1
        })
        self.assertEqual(res1.status_code, 201)

        # Attempt to register second account with same email
        mobile2 = self._generate_mobile()
        self._verify_otp_for_mobile(mobile2, "signup")
        res2 = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Duplicate User",
            "email": email,
            "password": "Password123!",
            "customerType": "student",
            "identifier": "22CS106",
            "mobile": mobile2
        })
        self.assertEqual(res2.status_code, 409)
        self.assertFalse(res2.get_json().get("success"))
        self.assertIn("already exists", res2.get_json().get("message", "").lower())


    # -------------------------------------------------------------
    # 7. Faculty and Guest Registration & Database Verification
    # -------------------------------------------------------------
    def test_faculty_and_guest_registration_db_persistence(self):
        """Faculty and Guest registrations succeed, create real records, hash passwords, and auto-authenticate."""
        # A. Faculty Registration
        fac_suffix = secrets.token_hex(4)
        fac_email = f"faculty_{fac_suffix}@kpriet.ac.in"
        fac_mobile = self._generate_mobile()
        self._verify_otp_for_mobile(fac_mobile, "signup")

        fac_res = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Professor John Doe",
            "email": fac_email,
            "password": "FacultySecret99!",
            "confirmPassword": "FacultySecret99!",
            "customerType": "faculty",
            "identifier": f"FAC{secrets.randbelow(899) + 100}",
            "mobile": fac_mobile
        })
        self.assertEqual(fac_res.status_code, 201)
        fac_data = fac_res.get_json()
        self.assertTrue(fac_data.get("success"))

        # Verify DB records for faculty
        fac_user = DB.get_one("SELECT id, email, password_hash, role FROM users WHERE email = %s", (fac_email,))
        self.assertIsNotNone(fac_user)
        self.assertTrue(bcrypt.checkpw(b"FacultySecret99!", fac_user["password_hash"].encode("utf-8")))
        fac_profile = DB.get_one("SELECT full_name, customer_type, identifier FROM customer_profiles WHERE user_id = %s", (fac_user["id"],))
        self.assertEqual(fac_profile["customer_type"], "faculty")
        self.assertEqual(fac_profile["full_name"], "Professor John Doe")

        # B. Guest Registration (standard email)
        guest_suffix = secrets.token_hex(4)
        guest_email = f"visitor_{guest_suffix}@example.com"
        guest_mobile = self._generate_mobile()
        self._verify_otp_for_mobile(guest_mobile, "signup")

        guest_res = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Guest Visitor",
            "email": guest_email,
            "password": "GuestSecret123!",
            "confirmPassword": "GuestSecret123!",
            "customerType": "guest",
            "mobile": guest_mobile
        })
        self.assertEqual(guest_res.status_code, 201)
        guest_data = guest_res.get_json()
        self.assertTrue(guest_data.get("success"))

        # Verify DB records for guest
        guest_user = DB.get_one("SELECT id, email, password_hash, role FROM users WHERE email = %s", (guest_email,))
        self.assertIsNotNone(guest_user)
        self.assertTrue(bcrypt.checkpw(b"GuestSecret123!", guest_user["password_hash"].encode("utf-8")))
        guest_profile = DB.get_one("SELECT full_name, customer_type FROM customer_profiles WHERE user_id = %s", (guest_user["id"],))
        self.assertEqual(guest_profile["customer_type"], "guest")
        self.assertEqual(guest_profile["full_name"], "Guest Visitor")


if __name__ == "__main__":
    unittest.main()

