"""
Authoritative Administrator Bootstrapping & Credential Management Service.

Responsibilities:
1. Production Cloud Bootstrapping: Automatically provisions or resets the root administrator
   account on startup when ADMIN_EMAIL and ADMIN_PASSWORD environment variables are set.
2. Zero-Downtime Credential Rotation: Allows administrators to securely rotate passwords
   simply by updating the ADMIN_PASSWORD environment variable in the Render Dashboard.
3. Development Default Fallback: Automatically provisions default admin credentials in
   local development mode if no administrator exists.
4. Security Enforcement: Strictly hashes passwords using high-work-factor bcrypt and never
   logs passwords or secret keys.
"""

import os
import re
import logging
from typing import Optional, Dict, Any

from db import DB, DatabaseConnectionError, DatabaseError
from security import hash_password

logger = logging.getLogger("food_court.admin_bootstrap")


def validate_admin_email(email: str) -> bool:
    """Validates basic email formatting."""
    if not email or not isinstance(email, str):
        return False
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))


def create_or_reset_admin(email: str, password: str) -> Dict[str, Any]:
    """
    Authoritatively creates or updates an administrator account.
    Returns a status dict: {"success": bool, "action": "created"|"updated", "email": str, "message": str}.
    """
    clean_email = (email or "").strip().lower()
    clean_password = (password or "").strip()

    if not validate_admin_email(clean_email):
        raise ValueError(f"Invalid administrator email format: '{clean_email}'")

    if len(clean_password) < 6:
        raise ValueError("Administrator password must be at least 6 characters long.")

    pw_hash = hash_password(clean_password)

    existing = DB.get_one(
        "SELECT id, email, role, is_active FROM users WHERE LOWER(email) = %s LIMIT 1",
        (clean_email,)
    )

    if existing:
        user_id = existing["id"]
        DB.execute(
            """
            UPDATE users
            SET password_hash = %s, role = 'admin', is_active = 1
            WHERE id = %s
            """,
            (pw_hash, user_id)
        )
        logger.info("Administrator account password successfully reset for: %s (ID: %s)", clean_email, user_id)
        return {
            "success": True,
            "action": "updated",
            "user_id": user_id,
            "email": clean_email,
            "message": f"Administrator account updated for {clean_email}."
        }
    else:
        user_id = DB.execute(
            """
            INSERT INTO users (email, password_hash, role, is_active)
            VALUES (%s, %s, 'admin', 1)
            """,
            (clean_email, pw_hash)
        )
        logger.info("New administrator account created for: %s (ID: %s)", clean_email, user_id)
        return {
            "success": True,
            "action": "created",
            "user_id": user_id,
            "email": clean_email,
            "message": f"Administrator account created for {clean_email}."
        }


def ensure_admin_account() -> bool:
    """
    Bootstraps the administrator account on application startup.
    - If ADMIN_EMAIL and ADMIN_PASSWORD are in environment: ensures that admin exists with that password.
    - If in development and no admin exists: seeds default development admin.
    - If in production and no admin exists: logs clear actionable warning.
    """
    flask_env = os.getenv("FLASK_ENV", "production").lower()
    is_dev = flask_env in ("development", "dev", "test", "testing")

    env_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    env_password = os.getenv("ADMIN_PASSWORD", "").strip()

    # 1. Environment-driven bootstrap (Render production & custom dev setups)
    if env_password:
        target_email = env_email if env_email else "admin@kpriet.ac.in"
        try:
            res = create_or_reset_admin(target_email, env_password)
            logger.info("Admin bootstrap complete: %s (%s)", res["email"], res["action"])
            return True
        except Exception as err:
            logger.error("Failed to bootstrap admin account from environment: %s", err)
            return False

    # 2. Check if any active admin currently exists in the database
    try:
        row = DB.get_one("SELECT id, email FROM users WHERE role = 'admin' AND is_active = 1 LIMIT 1")
        if row:
            logger.debug("Active administrator account verified in database (%s).", row["email"])
            return True
    except (DatabaseConnectionError, DatabaseError) as db_err:
        logger.warning("Database unavailable during admin account verification check: %s", db_err)
        return False
    except Exception as e:
        logger.warning("Unexpected error checking existing admin accounts: %s", e)
        return False

    # 3. No admin exists in database and no ADMIN_PASSWORD was provided
    if is_dev:
        logger.info("Development mode: Bootstrapping default administrator (admin@kpriet.ac.in).")
        try:
            create_or_reset_admin("admin@kpriet.ac.in", "admin123")
            return True
        except Exception as e:
            logger.error("Failed to seed default development admin: %s", e)
            return False
    else:
        logger.warning(
            "PRODUCTION CONFIGURATION NOTICE: No active admin account exists in database. "
            "Please configure ADMIN_EMAIL and ADMIN_PASSWORD in your Render Environment Variables."
        )
        return False
