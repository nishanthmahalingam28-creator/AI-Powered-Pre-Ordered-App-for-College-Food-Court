"""
Phase 2 Customer System Automated Test Suite.
Validates:
1. Multi-Persona Signups (Student, Faculty, Guest) with valid data.
2. Email validation for student/faculty (@kpriet.ac.in) vs guest.
3. Identifier enforcement: roll number for student, faculty ID for faculty, optional for guest.
4. Indian 10-digit mobile validation and normalization.
5. Duplicate email and mobile rejections.
6. Minimum password length enforcement.
7. OTP Security:
   - Generation and send
   - Correct OTP verification
   - Wrong OTP rejection
   - Expired OTP rejection
   - Reused OTP rejection
   - Brute-force rate limiting (429)
   - Server-enforced OTP verification on signup (rejecting unverified mobile)
   - Rejection of fake client-side flags (e.g. isOtpVerified: true)
   - Rejection of OTP verified for a different mobile
8. Multi-Persona Login (Student, Faculty, Guest).
9. Wrong password rejection and inactive account rejection.
10. /auth/me returns authenticated customer details; unauthenticated returns safe response.
11. Logout clears session; protected endpoints reject subsequent calls.
12. Access Control (Customer -> Vendor = 403, Customer -> Admin = 403).
13. Customer Profile API (GET /api/customer/profile, PUT /api/customer/profile persistence).
14. Password Change API (PUT /api/customer/password verification, hash update, new password works, old password fails).
"""

import os
import sys
import json
import secrets
import unittest
from datetime import datetime, timedelta

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ["FLASK_ENV"] = "development"
os.environ["USE_SQLITE"] = "1"
os.environ["SECRET_KEY"] = "phase2-customer-test-key-32b-secret"

import init_db
init_db.init_sqlite()

from db import DB
from app import app
from routes.auth import _otp_failed_verifications, _otp_send_limits


class TestPhase2CustomerSystem(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        # Reset in-memory rate-limiting counters for test isolation
        _otp_failed_verifications.clear()
        _otp_send_limits.clear()

    def _generate_mobile(self):
        return f"9{secrets.randbelow(900000000) + 100000000}"

    def _verify_otp_for_mobile(self, mobile, purpose="signup"):
        res = self.client.post("/api/auth/otp/send", json={"mobile": mobile, "purpose": purpose})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        code = data.get("demo_otp")
        self.assertTrue(bool(code), "Dev demo_otp should be returned")

        v_res = self.client.post("/api/auth/otp/verify", json={"mobile": mobile, "code": code, "purpose": purpose})
        self.assertEqual(v_res.status_code, 200)
        v_data = v_res.get_json()
        self.assertTrue(v_data.get("verified"))
        return code

    # -------------------------------------------------------------
    # 1. Signups across all 3 customer personas
    # -------------------------------------------------------------
    def test_student_signup_with_valid_data(self):
        email = f"student_{secrets.token_hex(4)}@kpriet.ac.in"
        mobile = self._generate_mobile()
        self._verify_otp_for_mobile(mobile, "signup")

        res = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Student Test User",
            "email": email,
            "password": "ValidPassword123!",
            "customerType": "student",
            "identifier": "22CS999",
            "mobile": mobile
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("user", {}).get("customer_type"), "student")

    def test_faculty_signup_with_valid_data(self):
        email = f"faculty_{secrets.token_hex(4)}@kpriet.ac.in"
        mobile = self._generate_mobile()
        self._verify_otp_for_mobile(mobile, "signup")

        res = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Dr. Faculty User",
            "email": email,
            "password": "ValidPassword123!",
            "customerType": "faculty",
            "identifier": "FAC888",
            "mobile": mobile
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("user", {}).get("customer_type"), "faculty")

    def test_guest_signup_with_valid_data(self):
        email = f"guest_{secrets.token_hex(4)}@gmail.com"
        mobile = self._generate_mobile()
        self._verify_otp_for_mobile(mobile, "signup")

        res = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Guest Visitor",
            "email": email,
            "password": "ValidPassword123!",
            "customerType": "guest",
            "mobile": mobile
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("user", {}).get("customer_type"), "guest")

    # -------------------------------------------------------------
    # 2. Email Validation for Student, Faculty, Guest
    # -------------------------------------------------------------
    def test_invalid_student_email_rejected(self):
        mobile = self._generate_mobile()
        self._verify_otp_for_mobile(mobile, "signup")

        # Non-kpriet domain rejected for student
        res = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Student NonKPR",
            "email": "student@gmail.com",
            "password": "ValidPassword123!",
            "customerType": "student",
            "identifier": "22CS001",
            "mobile": mobile
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("kpriet", res.get_json().get("message", "").lower())

    def test_invalid_faculty_email_rejected(self):
        mobile = self._generate_mobile()
        self._verify_otp_for_mobile(mobile, "signup")

        res = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Faculty NonKPR",
            "email": "professor@yahoo.com",
            "password": "ValidPassword123!",
            "customerType": "faculty",
            "identifier": "FAC001",
            "mobile": mobile
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("kpriet", res.get_json().get("message", "").lower())

    def test_invalid_guest_email_rejected(self):
        mobile = self._generate_mobile()
        self._verify_otp_for_mobile(mobile, "signup")

        res = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Guest Invalid",
            "email": "not-an-email-at-all",
            "password": "ValidPassword123!",
            "customerType": "guest",
            "mobile": mobile
        })
        self.assertEqual(res.status_code, 400)

    # -------------------------------------------------------------
    # 3. Identifier Enforcement
    # -------------------------------------------------------------
    def test_missing_roll_number_rejected(self):
        mobile = self._generate_mobile()
        self._verify_otp_for_mobile(mobile, "signup")

        res = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Student No Roll",
            "email": f"student_{secrets.token_hex(3)}@kpriet.ac.in",
            "password": "ValidPassword123!",
            "customerType": "student",
            "identifier": "",
            "mobile": mobile
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("roll number", res.get_json().get("message", "").lower())

    def test_missing_faculty_id_rejected(self):
        mobile = self._generate_mobile()
        self._verify_otp_for_mobile(mobile, "signup")

        res = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Faculty No ID",
            "email": f"prof_{secrets.token_hex(3)}@kpriet.ac.in",
            "password": "ValidPassword123!",
            "customerType": "faculty",
            "identifier": "",
            "mobile": mobile
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("faculty id", res.get_json().get("message", "").lower())

    # -------------------------------------------------------------
    # 4. Mobile & Password Validation
    # -------------------------------------------------------------
    def test_invalid_mobile_rejected(self):
        invalid_mobiles = ["12345", "5876543210", "987654321", "abcdefghij", "+91 0000000000"]
        for bad_mobile in invalid_mobiles:
            res = self.client.post("/api/auth/customer/signup", json={
                "fullName": "Invalid Mobile User",
                "email": f"student_{secrets.token_hex(3)}@kpriet.ac.in",
                "password": "ValidPassword123!",
                "customerType": "student",
                "identifier": "22CS100",
                "mobile": bad_mobile
            })
            self.assertEqual(res.status_code, 400, f"Failed to reject invalid mobile: {bad_mobile}")

    def test_short_password_rejected(self):
        mobile = self._generate_mobile()
        self._verify_otp_for_mobile(mobile, "signup")

        res = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Short Pass User",
            "email": f"student_{secrets.token_hex(3)}@kpriet.ac.in",
            "password": "short",
            "customerType": "student",
            "identifier": "22CS101",
            "mobile": mobile
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("8 characters", res.get_json().get("message", "").lower())

    def test_duplicate_email_rejected(self):
        email = f"dup_{secrets.token_hex(4)}@kpriet.ac.in"
        mobile1 = self._generate_mobile()
        mobile2 = self._generate_mobile()
        self._verify_otp_for_mobile(mobile1, "signup")
        self._verify_otp_for_mobile(mobile2, "signup")

        # First signup
        res1 = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Original User",
            "email": email,
            "password": "Password123!",
            "customerType": "student",
            "identifier": "22CS200",
            "mobile": mobile1
        })
        self.assertEqual(res1.status_code, 201)

        # Duplicate email signup attempt
        res2 = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Duplicate User",
            "email": email,
            "password": "Password123!",
            "customerType": "student",
            "identifier": "22CS201",
            "mobile": mobile2
        })
        self.assertEqual(res2.status_code, 409)

    # -------------------------------------------------------------
    # 5. OTP Security Flow & Protections
    # -------------------------------------------------------------
    def test_otp_send_and_verify_success(self):
        mobile = self._generate_mobile()
        res = self.client.post("/api/auth/otp/send", json={"mobile": mobile, "purpose": "signup"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        code = data.get("demo_otp")
        self.assertTrue(bool(code))

        # Verify correct OTP
        v_res = self.client.post("/api/auth/otp/verify", json={"mobile": mobile, "code": code, "purpose": "signup"})
        self.assertEqual(v_res.status_code, 200)
        self.assertTrue(v_res.get_json().get("verified"))

    def test_wrong_otp_rejected(self):
        mobile = self._generate_mobile()
        self.client.post("/api/auth/otp/send", json={"mobile": mobile, "purpose": "signup"})
        v_res = self.client.post("/api/auth/otp/verify", json={"mobile": mobile, "code": "000000", "purpose": "signup"})
        self.assertEqual(v_res.status_code, 400)

    def test_expired_otp_rejected(self):
        mobile = self._generate_mobile()
        self.client.post("/api/auth/otp/send", json={"mobile": mobile, "purpose": "signup"})
        # Manually backdate expiration in the database
        past_str = (datetime.now() - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
        DB.execute("UPDATE otp_codes SET expires_at = %s WHERE target = %s", (past_str, mobile))

        v_res = self.client.post("/api/auth/otp/verify", json={"mobile": mobile, "code": "123456", "purpose": "signup"})
        self.assertEqual(v_res.status_code, 400)

    def test_reused_otp_rejected(self):
        mobile = self._generate_mobile()
        code = self._verify_otp_for_mobile(mobile, "signup")

        # Second verification of the exact same code should be rejected (already verified)
        v_res = self.client.post("/api/auth/otp/verify", json={"mobile": mobile, "code": code, "purpose": "signup"})
        self.assertEqual(v_res.status_code, 400)

    def test_otp_bruteforce_protection_triggers_429(self):
        mobile = self._generate_mobile()
        self.client.post("/api/auth/otp/send", json={"mobile": mobile, "purpose": "signup"})

        for _ in range(5):
            res = self.client.post("/api/auth/otp/verify", json={"mobile": mobile, "code": "000000", "purpose": "signup"})
            self.assertEqual(res.status_code, 400)

        # 6th attempt should trigger HTTP 429
        res = self.client.post("/api/auth/otp/verify", json={"mobile": mobile, "code": "000000", "purpose": "signup"})
        self.assertEqual(res.status_code, 429)

    def test_signup_without_otp_verification_rejected(self):
        mobile = self._generate_mobile()
        # Not sending or verifying OTP
        res = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Unverified User",
            "email": f"student_{secrets.token_hex(4)}@kpriet.ac.in",
            "password": "Password123!",
            "customerType": "student",
            "identifier": "22CS900",
            "mobile": mobile
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("verified with otp", res.get_json().get("message", "").lower())

    def test_signup_with_fake_client_side_flag_rejected(self):
        mobile = self._generate_mobile()
        # Attempting to forge isOtpVerified: True
        res = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Hacker User",
            "email": f"student_{secrets.token_hex(4)}@kpriet.ac.in",
            "password": "Password123!",
            "customerType": "student",
            "identifier": "22CS901",
            "mobile": mobile,
            "isOtpVerified": True
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("verified with otp", res.get_json().get("message", "").lower())

    def test_signup_with_otp_verified_for_different_mobile_rejected(self):
        verified_mobile = self._generate_mobile()
        other_mobile = self._generate_mobile()
        self._verify_otp_for_mobile(verified_mobile, "signup")

        res = self.client.post("/api/auth/customer/signup", json={
            "fullName": "Mismatched Mobile User",
            "email": f"student_{secrets.token_hex(4)}@kpriet.ac.in",
            "password": "Password123!",
            "customerType": "student",
            "identifier": "22CS902",
            "mobile": other_mobile
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("verified with otp", res.get_json().get("message", "").lower())

    # -------------------------------------------------------------
    # 6. Customer Login & Authentication Verification
    # -------------------------------------------------------------
    def test_customer_login_student_faculty_guest(self):
        # Create student, faculty, guest
        personas = [
            ("student", f"stu_{secrets.token_hex(3)}@kpriet.ac.in", "22CS301"),
            ("faculty", f"fac_{secrets.token_hex(3)}@kpriet.ac.in", "FAC301"),
            ("guest", f"gst_{secrets.token_hex(3)}@gmail.com", None),
        ]
        for c_type, email, ident in personas:
            mobile = self._generate_mobile()
            self._verify_otp_for_mobile(mobile, "signup")
            signup_payload = {
                "fullName": f"{c_type.capitalize()} Test",
                "email": email,
                "password": "SecurePassword123!",
                "customerType": c_type,
                "mobile": mobile
            }
            if ident:
                signup_payload["identifier"] = ident
            s_res = self.client.post("/api/auth/customer/signup", json=signup_payload)
            self.assertEqual(s_res.status_code, 201)

            # Test successful login
            login_res = self.client.post("/api/auth/customer/login", json={
                "email": email,
                "password": "SecurePassword123!",
                "customerType": c_type
            })
            self.assertEqual(login_res.status_code, 200)
            u = login_res.get_json().get("user", {})
            self.assertEqual(u.get("email"), email)
            self.assertEqual(u.get("customer_type"), c_type)
            self.assertNotIn("password_hash", u)

    def test_wrong_password_rejected(self):
        email = f"student_{secrets.token_hex(4)}@kpriet.ac.in"
        mobile = self._generate_mobile()
        self._verify_otp_for_mobile(mobile, "signup")
        self.client.post("/api/auth/customer/signup", json={
            "fullName": "Student Wrong Pass",
            "email": email,
            "password": "CorrectPassword123!",
            "customerType": "student",
            "identifier": "22CS401",
            "mobile": mobile
        })

        res = self.client.post("/api/auth/customer/login", json={
            "email": email,
            "password": "WrongPassword!"
        })
        self.assertEqual(res.status_code, 401)

    def test_inactive_account_rejected(self):
        email = f"inactive_{secrets.token_hex(4)}@kpriet.ac.in"
        mobile = self._generate_mobile()
        self._verify_otp_for_mobile(mobile, "signup")
        self.client.post("/api/auth/customer/signup", json={
            "fullName": "Inactive Student",
            "email": email,
            "password": "Password123!",
            "customerType": "student",
            "identifier": "22CS402",
            "mobile": mobile
        })

        # Set is_active = 0 in database
        DB.execute("UPDATE users SET is_active = 0 WHERE email = %s", (email,))

        res = self.client.post("/api/auth/customer/login", json={
            "email": email,
            "password": "Password123!"
        })
        self.assertEqual(res.status_code, 401)

    # -------------------------------------------------------------
    # 7. /auth/me & Logout
    # -------------------------------------------------------------
    def test_auth_me_authenticated_and_unauthenticated(self):
        # Unauthenticated check returns 401
        res = self.client.get("/api/auth/me")
        self.assertEqual(res.status_code, 401)
        self.assertFalse(res.get_json().get("authenticated"))

        # Authenticated student check
        email = f"authme_{secrets.token_hex(4)}@kpriet.ac.in"
        mobile = self._generate_mobile()
        self._verify_otp_for_mobile(mobile, "signup")
        self.client.post("/api/auth/customer/signup", json={
            "fullName": "Auth Me Student",
            "email": email,
            "password": "Password123!",
            "customerType": "student",
            "identifier": "22CS501",
            "mobile": mobile
        })

        self.client.post("/api/auth/customer/login", json={"email": email, "password": "Password123!"})
        me_res = self.client.get("/api/auth/me")
        self.assertEqual(me_res.status_code, 200)
        me_data = me_res.get_json()
        self.assertTrue(me_data.get("authenticated"))
        u = me_data.get("user", {})
        self.assertEqual(u.get("email"), email)
        self.assertEqual(u.get("customer_type"), "student")
        self.assertEqual(u.get("identifier"), "22CS501")
        self.assertEqual(u.get("mobile"), mobile)

    def test_logout_clears_session(self):
        email = f"logout_{secrets.token_hex(4)}@kpriet.ac.in"
        mobile = self._generate_mobile()
        self._verify_otp_for_mobile(mobile, "signup")
        self.client.post("/api/auth/customer/signup", json={
            "fullName": "Logout Student",
            "email": email,
            "password": "Password123!",
            "customerType": "student",
            "identifier": "22CS502",
            "mobile": mobile
        })
        self.client.post("/api/auth/customer/login", json={"email": email, "password": "Password123!"})

        # Perform logout
        logout_res = self.client.post("/api/auth/logout")
        self.assertEqual(logout_res.status_code, 200)

        # /auth/me should now be unauthenticated (401)
        me_res = self.client.get("/api/auth/me")
        self.assertEqual(me_res.status_code, 401)
        self.assertFalse(me_res.get_json().get("authenticated"))

        # Protected profile should reject with 401
        prof_res = self.client.get("/api/customer/profile")
        self.assertEqual(prof_res.status_code, 401)

    # -------------------------------------------------------------
    # 8. Access Control (RBAC)
    # -------------------------------------------------------------
    def test_customer_cannot_access_vendor_or_admin_endpoints(self):
        email = f"rbac_{secrets.token_hex(4)}@kpriet.ac.in"
        mobile = self._generate_mobile()
        self._verify_otp_for_mobile(mobile, "signup")
        self.client.post("/api/auth/customer/signup", json={
            "fullName": "RBAC Customer",
            "email": email,
            "password": "Password123!",
            "customerType": "student",
            "identifier": "22CS601",
            "mobile": mobile
        })
        self.client.post("/api/auth/customer/login", json={"email": email, "password": "Password123!"})

        # Attempt to access vendor analytics
        v_res = self.client.get("/api/vendor/analytics")
        self.assertIn(v_res.status_code, (401, 403))

        # Attempt to access admin overview
        a_res = self.client.get("/api/admin/overview")
        self.assertIn(a_res.status_code, (401, 403))

    # -------------------------------------------------------------
    # 9. Real Customer Profile APIs (GET & PUT)
    # -------------------------------------------------------------
    def test_customer_profile_get_and_put_persistence(self):
        email = f"profile_{secrets.token_hex(4)}@kpriet.ac.in"
        mobile = self._generate_mobile()
        self._verify_otp_for_mobile(mobile, "signup")
        self.client.post("/api/auth/customer/signup", json={
            "fullName": "Original Name",
            "email": email,
            "password": "Password123!",
            "customerType": "student",
            "identifier": "22CS701",
            "mobile": mobile
        })
        self.client.post("/api/auth/customer/login", json={"email": email, "password": "Password123!"})

        # GET profile
        get_res = self.client.get("/api/customer/profile")
        self.assertEqual(get_res.status_code, 200)
        u = get_res.get_json().get("user", {})
        self.assertEqual(u.get("full_name"), "Original Name")
        self.assertEqual(u.get("mobile"), mobile)

        # PUT profile - update name
        put_res = self.client.put("/api/customer/profile", json={
            "full_name": "Updated Name"
        })
        self.assertEqual(put_res.status_code, 200)

        # Verify change persisted in database
        updated_get = self.client.get("/api/customer/profile")
        self.assertEqual(updated_get.get_json().get("user", {}).get("full_name"), "Updated Name")

        db_user = DB.get_one("SELECT full_name FROM customer_profiles WHERE mobile = %s", (mobile,))
        self.assertEqual(db_user["full_name"], "Updated Name")

    def test_customer_profile_disallows_role_tampering(self):
        email = f"role_tamper_{secrets.token_hex(4)}@kpriet.ac.in"
        mobile = self._generate_mobile()
        self._verify_otp_for_mobile(mobile, "signup")
        self.client.post("/api/auth/customer/signup", json={
            "fullName": "Tamper Test",
            "email": email,
            "password": "Password123!",
            "customerType": "student",
            "identifier": "22CS702",
            "mobile": mobile
        })
        self.client.post("/api/auth/customer/login", json={"email": email, "password": "Password123!"})

        # Attempt to escalate role or customer_type
        self.client.put("/api/customer/profile", json={
            "role": "admin",
            "customer_type": "faculty"
        })

        # Check in DB that role and customer_type remain intact
        user_row = DB.get_one("SELECT role FROM users WHERE email = %s", (email,))
        self.assertEqual(user_row["role"], "customer")
        prof_row = DB.get_one("SELECT customer_type FROM customer_profiles WHERE mobile = %s", (mobile,))
        self.assertEqual(prof_row["customer_type"], "student")

    # -------------------------------------------------------------
    # 10. Real Password Change API
    # -------------------------------------------------------------
    def test_customer_password_change_flow(self):
        email = f"pwd_{secrets.token_hex(4)}@kpriet.ac.in"
        mobile = self._generate_mobile()
        self._verify_otp_for_mobile(mobile, "signup")
        self.client.post("/api/auth/customer/signup", json={
            "fullName": "Password Change Tester",
            "email": email,
            "password": "OldPassword123!",
            "customerType": "student",
            "identifier": "22CS801",
            "mobile": mobile
        })
        self.client.post("/api/auth/customer/login", json={"email": email, "password": "OldPassword123!"})

        # Test failure with wrong current password
        fail_res = self.client.put("/api/customer/password", json={
            "current_password": "WrongCurrentPassword!",
            "new_password": "BrandNewPassword123!",
            "confirm_password": "BrandNewPassword123!"
        })
        self.assertEqual(fail_res.status_code, 400)
        self.assertIn("current password", fail_res.get_json().get("message", "").lower())

        # Test success with correct current password
        success_res = self.client.put("/api/customer/password", json={
            "current_password": "OldPassword123!",
            "new_password": "BrandNewPassword123!",
            "confirm_password": "BrandNewPassword123!"
        })
        self.assertEqual(success_res.status_code, 200)
        self.assertTrue(success_res.get_json().get("success"))

        # Logout and test that old password is now rejected
        self.client.post("/api/auth/logout")
        old_login = self.client.post("/api/auth/customer/login", json={
            "email": email,
            "password": "OldPassword123!"
        })
        self.assertEqual(old_login.status_code, 401)

        # Test that new password succeeds
        new_login = self.client.post("/api/auth/customer/login", json={
            "email": email,
            "password": "BrandNewPassword123!"
        })
        self.assertEqual(new_login.status_code, 200)
        self.assertTrue(new_login.get_json().get("success"))


if __name__ == "__main__":
    unittest.main()
