"""
Automated Test Suite for Database-Backed Authenticated Income Persistence.

Covers all requirements:
1. Authenticated users only (rejects unauthenticated requests with 401).
2. Ownership determined strictly by backend session (ignores client-supplied userId).
3. Full CRUD operations:
   - POST /api/income (create)
   - GET /api/income (list current user's income records)
   - GET /api/income/<id> (retrieve single income record)
   - PUT /api/income/<id> (update income record)
   - DELETE /api/income/<id> (delete income record)
4. Input validation (amount, date, source, description).
5. Database persistence verified in SQLite/MySQL.
6. Multi-tenant IDOR protection:
   - User B cannot read, modify, or delete User A's income records.
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
os.environ["SECRET_KEY"] = "income-test-key-32b-secret-min-key"

import init_db
init_db.init_sqlite()

from db import DB
from app import app
from routes.auth import _otp_failed_verifications, _otp_send_limits


class TestIncomeAPI(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        _otp_failed_verifications.clear()
        _otp_send_limits.clear()

    def _generate_mobile(self):
        return f"9{secrets.randbelow(900000000) + 100000000}"

    def _register_and_login_user(self, name_prefix="Income Tester"):
        """Helper to create and log in a fresh user, returning client, user_id, email."""
        client = self.app.test_client()
        suffix = secrets.token_hex(4)
        email = f"earner_{suffix}@kpriet.ac.in"
        mobile = self._generate_mobile()
        password = "SecurePassword123!"

        # OTP
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
    # 1. Create Income & DB Persistence
    # -------------------------------------------------------------
    def test_create_income_success(self):
        """Authenticated user creates income; verified in database."""
        client, user_id, email = self._register_and_login_user("Earner")

        payload = {
            "amount": 2500.00,
            "source": "Campus Stipend",
            "description": "Monthly Department Research Fellowship Allowance",
            "date": "2026-09-17"
        }

        res = client.post("/api/income", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        record = data.get("income", {})
        self.assertEqual(record.get("amount"), 2500.00)
        self.assertEqual(record.get("source"), payload["source"])
        self.assertEqual(record.get("description"), payload["description"])
        self.assertEqual(record.get("income_date"), payload["date"])
        self.assertEqual(record.get("user_id"), user_id)

        # Verify in database
        db_row = DB.get_one("SELECT * FROM income WHERE id = %s", (record["id"],))
        self.assertIsNotNone(db_row)
        self.assertEqual(db_row["user_id"], user_id)
        self.assertEqual(float(db_row["amount"]), 2500.00)
        self.assertEqual(db_row["source"], payload["source"])
        self.assertEqual(db_row["description"], payload["description"])
        self.assertEqual(str(db_row["income_date"]), payload["date"])

    # -------------------------------------------------------------
    # 2. Session-Derived Ownership (Ignore Client-Supplied userId)
    # -------------------------------------------------------------
    def test_user_id_derived_from_session_only(self):
        """Client-supplied userId or user_id in payload is strictly ignored."""
        client, user_id, email = self._register_and_login_user("SpoofAttempt")

        payload = {
            "amount": 1000.00,
            "source": "Pocket Money",
            "description": "Monthly allowance from parents",
            "date": "2026-09-17",
            "userId": 99999,
            "user_id": 88888
        }

        res = client.post("/api/income", json=payload)
        self.assertEqual(res.status_code, 201)
        record = res.get_json().get("income", {})

        self.assertEqual(record.get("user_id"), user_id)
        db_row = DB.get_one("SELECT user_id FROM income WHERE id = %s", (record["id"],))
        self.assertEqual(db_row["user_id"], user_id)
        self.assertNotEqual(db_row["user_id"], 99999)
        self.assertNotEqual(db_row["user_id"], 88888)

    # -------------------------------------------------------------
    # 3. Get Current User's Income Records
    # -------------------------------------------------------------
    def test_get_current_user_income(self):
        """Retrieves only the authenticated user's income records."""
        client, user_id, email = self._register_and_login_user("Lister")

        client.post("/api/income", json={
            "amount": 500.00,
            "source": "Tutoring",
            "description": "Peer Math Tutoring",
            "date": "2026-09-15"
        })
        client.post("/api/income", json={
            "amount": 1500.00,
            "source": "Hackathon Prize",
            "description": "2nd Place Campus AI Hackathon",
            "date": "2026-09-16"
        })

        res = client.get("/api/income")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("count"), 2)
        self.assertEqual(data.get("total_amount"), 2000.00)
        records = data.get("income", [])
        self.assertEqual(len(records), 2)
        for r in records:
            self.assertEqual(r.get("user_id"), user_id)

    # -------------------------------------------------------------
    # 4. Update Income Record
    # -------------------------------------------------------------
    def test_update_income_success(self):
        """Owner can update their income record."""
        client, user_id, email = self._register_and_login_user("Updater")

        create_res = client.post("/api/income", json={
            "amount": 400.00,
            "source": "Part-Time Job",
            "description": "Library Assistant Shift",
            "date": "2026-09-14"
        })
        self.assertEqual(create_res.status_code, 201)
        inc_id = create_res.get_json()["income"]["id"]

        update_payload = {
            "amount": 450.00,
            "source": "Part-Time Job",
            "description": "Library Assistant Shift with Overtime",
            "date": "2026-09-14"
        }
        put_res = client.put(f"/api/income/{inc_id}", json=update_payload)
        self.assertEqual(put_res.status_code, 200)
        updated = put_res.get_json().get("income", {})
        self.assertEqual(updated.get("amount"), 450.00)
        self.assertEqual(updated.get("description"), "Library Assistant Shift with Overtime")

        # Verify in DB
        db_row = DB.get_one("SELECT amount, description FROM income WHERE id = %s", (inc_id,))
        self.assertEqual(float(db_row["amount"]), 450.00)
        self.assertEqual(db_row["description"], "Library Assistant Shift with Overtime")

    # -------------------------------------------------------------
    # 5. Delete Income Record
    # -------------------------------------------------------------
    def test_delete_income_success(self):
        """Owner can delete their income record."""
        client, user_id, email = self._register_and_login_user("Deleter")

        create_res = client.post("/api/income", json={
            "amount": 300.00,
            "source": "Gift",
            "description": "Birthday Gift",
            "date": "2026-09-12"
        })
        self.assertEqual(create_res.status_code, 201)
        inc_id = create_res.get_json()["income"]["id"]

        del_res = client.delete(f"/api/income/{inc_id}")
        self.assertEqual(del_res.status_code, 200)
        self.assertTrue(del_res.get_json().get("success"))

        # Verify removed from DB
        db_row = DB.get_one("SELECT id FROM income WHERE id = %s", (inc_id,))
        self.assertIsNone(db_row)

    # -------------------------------------------------------------
    # 6. Validation Rules
    # -------------------------------------------------------------
    def test_validation_rules(self):
        """Validates amount, date, source, and description."""
        client, user_id, email = self._register_and_login_user("Validator")

        base_valid = {
            "amount": 800.00,
            "source": "Scholarship",
            "description": "Merit Scholarship",
            "date": "2026-09-17"
        }

        # Negative / Zero Amount
        res1 = client.post("/api/income", json={**base_valid, "amount": 0})
        self.assertEqual(res1.status_code, 400)
        self.assertIn("positive number", res1.get_json().get("message", "").lower())

        res2 = client.post("/api/income", json={**base_valid, "amount": -100})
        self.assertEqual(res2.status_code, 400)
        self.assertIn("positive number", res2.get_json().get("message", "").lower())

        # Non-numeric Amount
        res3 = client.post("/api/income", json={**base_valid, "amount": "invalid"})
        self.assertEqual(res3.status_code, 400)
        self.assertIn("valid numeric", res3.get_json().get("message", "").lower())

        # Invalid Date Format
        res4 = client.post("/api/income", json={**base_valid, "date": "17/09/2026"})
        self.assertEqual(res4.status_code, 400)
        self.assertIn("yyyy-mm-dd", res4.get_json().get("message", "").lower())

        # Non-existent Date (e.g. Feb 30)
        res5 = client.post("/api/income", json={**base_valid, "date": "2026-02-30"})
        self.assertEqual(res5.status_code, 400)
        self.assertIn("valid calendar date", res5.get_json().get("message", "").lower())

        # Empty Source
        res6 = client.post("/api/income", json={**base_valid, "source": "   "})
        self.assertEqual(res6.status_code, 400)
        self.assertIn("source", res6.get_json().get("message", "").lower())

        # Empty Description
        res7 = client.post("/api/income", json={**base_valid, "description": ""})
        self.assertEqual(res7.status_code, 400)
        self.assertIn("description", res7.get_json().get("message", "").lower())

    # -------------------------------------------------------------
    # 7. Multi-Tenant IDOR Security Test
    # -------------------------------------------------------------
    def test_idor_cross_user_isolation(self):
        """
        Security requirement:
        User A creates an income record. User B cannot access, modify, or delete
        User A's record by changing IDs in the request.
        """
        client_a, user_a_id, email_a = self._register_and_login_user("UserAlpha")
        client_b, user_b_id, email_b = self._register_and_login_user("UserBeta")

        # User A creates income
        res_a = client_a.post("/api/income", json={
            "amount": 5000.00,
            "source": "Research Grant",
            "description": "User A Private Grant Funds",
            "date": "2026-09-17"
        })
        self.assertEqual(res_a.status_code, 201)
        inc_a_id = res_a.get_json()["income"]["id"]

        # 1. User B lists income -> Must NOT include User A's record
        list_b = client_b.get("/api/income")
        self.assertEqual(list_b.status_code, 200)
        b_records = list_b.get_json().get("income", [])
        self.assertEqual(len(b_records), 0, "User B's list must not contain User A's income")

        # 2. User B tries to GET User A's income by ID -> Must be rejected (403 or 404)
        get_b = client_b.get(f"/api/income/{inc_a_id}")
        self.assertIn(get_b.status_code, [403, 404], "User B must not be able to read User A's income")
        self.assertFalse(get_b.get_json().get("success"))

        # 3. User B tries to UPDATE User A's income by ID -> Must be rejected (403 or 404)
        put_b = client_b.put(f"/api/income/{inc_a_id}", json={
            "amount": 10.00,
            "source": "Tampered",
            "description": "Hacked by User B",
            "date": "2026-09-17"
        })
        self.assertIn(put_b.status_code, [403, 404], "User B must not be able to update User A's income")

        # Verify in DB: User A's income record is COMPLETELY UNTOUCHED
        db_a = DB.get_one("SELECT amount, description FROM income WHERE id = %s", (inc_a_id,))
        self.assertEqual(float(db_a["amount"]), 5000.00)
        self.assertEqual(db_a["description"], "User A Private Grant Funds")

        # 4. User B tries to DELETE User A's income by ID -> Must be rejected (403 or 404)
        del_b = client_b.delete(f"/api/income/{inc_a_id}")
        self.assertIn(del_b.status_code, [403, 404], "User B must not be able to delete User A's income")

        # Verify in DB: User A's record STILL EXISTS
        db_a_still_exists = DB.get_one("SELECT id FROM income WHERE id = %s", (inc_a_id,))
        self.assertIsNotNone(db_a_still_exists, "User A's income record must still exist")

    # -------------------------------------------------------------
    # 8. Unauthenticated Requests Rejected
    # -------------------------------------------------------------
    def test_unauthenticated_requests_rejected(self):
        """Unauthenticated requests return 401 Unauthorized across all endpoints."""
        unauth = self.app.test_client()

        r_post = unauth.post("/api/income", json={
            "amount": 100.00,
            "source": "Stipend",
            "description": "Unauth Attempt",
            "date": "2026-09-17"
        })
        self.assertEqual(r_post.status_code, 401)

        r_get = unauth.get("/api/income")
        self.assertEqual(r_get.status_code, 401)

        r_put = unauth.put("/api/income/1", json={"amount": 50.00})
        self.assertEqual(r_put.status_code, 401)

        r_del = unauth.delete("/api/income/1")
        self.assertEqual(r_del.status_code, 401)


if __name__ == "__main__":
    unittest.main()
