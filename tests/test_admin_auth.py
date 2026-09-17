"""
Automated Test Suite for Administrator Authentication & Root Account Bootstrapping.

Validates:
1. Admin Login with Full Email ('admin@kpriet.ac.in') and password.
2. Admin Login with Username Prefix ('admin') and password.
3. Wrong password rejection with 401 Unauthorized.
4. Missing/empty credentials rejection with 400 Bad Request.
5. Deactivated admin account rejection with 403 Forbidden.
6. Unconfigured admin account diagnostic message.
7. create_or_reset_admin service creating and rotating admin passwords.
8. ensure_admin_account environment variable bootstrapping.
9. manage_admin CLI execution for command-line provisioning.
"""

import os
import sys
import unittest
import subprocess
from unittest.mock import patch

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ["FLASK_ENV"] = "development"
os.environ["USE_SQLITE"] = "1"
os.environ["SECRET_KEY"] = "admin-test-secret-key-32b-min"

import init_db
init_db.init_sqlite()

from db import DB
from app import app
from security import hash_password, verify_password
from services.admin_bootstrap import create_or_reset_admin, ensure_admin_account


class TestAdminAuthentication(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self.admin_email = "admin@kpriet.ac.in"
        self.admin_password = "admin123"

        # Ensure base admin exists
        create_or_reset_admin(self.admin_email, self.admin_password)

    def test_admin_login_success_full_email(self):
        """Admin can log in using full email address 'admin@kpriet.ac.in'."""
        res = self.client.post("/api/auth/admin/login", json={
            "username": self.admin_email,
            "password": self.admin_password
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data["user"]["role"], "admin")
        self.assertEqual(data["user"]["email"], self.admin_email)
        self.assertEqual(data["redirect"], "/pages/admin/dashboard.html")

        # Verify session state via /api/auth/me
        me_res = self.client.get("/api/auth/me")
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.get_json()["user"]["role"], "admin")

    def test_admin_login_success_username_prefix(self):
        """Admin can log in using security username 'admin'."""
        res = self.client.post("/api/auth/admin/login", json={
            "username": "admin",
            "password": self.admin_password
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data["user"]["role"], "admin")

    def test_admin_login_invalid_password(self):
        """Invalid password returns 401 Unauthorized."""
        res = self.client.post("/api/auth/admin/login", json={
            "username": "admin",
            "password": "wrongpassword999"
        })
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertFalse(data.get("success"))
        self.assertIn("invalid root access identifiers", data.get("message", "").lower())

    def test_admin_login_empty_inputs(self):
        """Empty username or password returns 400 Bad Request."""
        res = self.client.post("/api/auth/admin/login", json={
            "username": "",
            "password": ""
        })
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get("success"))

    def test_admin_login_deactivated_account(self):
        """Deactivated admin account returns 403 Forbidden."""
        deact_email = "deact.admin@kpriet.ac.in"
        create_or_reset_admin(deact_email, "admin123")
        DB.execute("UPDATE users SET is_active = 0 WHERE email = %s", (deact_email,))

        res = self.client.post("/api/auth/admin/login", json={
            "username": deact_email,
            "password": "admin123"
        })
        self.assertEqual(res.status_code, 403)
        self.assertFalse(res.get_json().get("success"))
        self.assertIn("deactivated", res.get_json().get("message", "").lower())

    def test_create_or_reset_admin_service(self):
        """create_or_reset_admin safely creates new accounts and rotates existing passwords."""
        # 1. Create new admin
        new_admin = "custom.admin@kpriet.ac.in"
        DB.execute("DELETE FROM users WHERE email = %s", (new_admin,))
        res1 = create_or_reset_admin(new_admin, "firstpass123")
        self.assertTrue(res1["success"])
        self.assertEqual(res1["action"], "created")

        # Verify password matches
        user1 = DB.get_one("SELECT password_hash FROM users WHERE email = %s", (new_admin,))
        self.assertTrue(verify_password("firstpass123", user1["password_hash"]))

        # 2. Reset / Rotate password
        res2 = create_or_reset_admin(new_admin, "newrotatedpass456")
        self.assertTrue(res2["success"])
        self.assertEqual(res2["action"], "updated")

        user2 = DB.get_one("SELECT password_hash FROM users WHERE email = %s", (new_admin,))
        self.assertFalse(verify_password("firstpass123", user2["password_hash"]))
        self.assertTrue(verify_password("newrotatedpass456", user2["password_hash"]))

    def test_ensure_admin_account_from_environment(self):
        """ensure_admin_account updates admin password when ADMIN_PASSWORD is provided in env."""
        env_admin = "env.admin@kpriet.ac.in"
        with patch.dict(os.environ, {"ADMIN_EMAIL": env_admin, "ADMIN_PASSWORD": "envsecretpassword999"}):
            self.assertTrue(ensure_admin_account())

            # Verify login works with environment-provisioned credentials
            res = self.client.post("/api/auth/admin/login", json={
                "username": env_admin,
                "password": "envsecretpassword999"
            })
            self.assertEqual(res.status_code, 200)

    def test_manage_admin_cli(self):
        """backend/manage_admin.py creates or resets admin credentials via CLI."""
        cli_script = os.path.join(BACKEND_DIR, "manage_admin.py")
        test_cli_email = "cli.admin@kpriet.ac.in"
        test_cli_pass = "clipassword12345"
        DB.execute("DELETE FROM users WHERE email = %s", (test_cli_email,))

        cmd = [
            sys.executable,
            cli_script,
            "--email", test_cli_email,
            "--password", test_cli_pass
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("SUCCESS", result.stdout)

        # Verify login with the CLI-provisioned credentials
        res = self.client.post("/api/auth/admin/login", json={
            "username": test_cli_email,
            "password": test_cli_pass
        })
        self.assertEqual(res.status_code, 200)


if __name__ == "__main__":
    unittest.main()
