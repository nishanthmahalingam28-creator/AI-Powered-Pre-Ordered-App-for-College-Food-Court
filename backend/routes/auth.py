from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash
import re

from db import get_db_connection

auth_bp = Blueprint("auth", __name__)

KPRIET_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@kpriet\.ac\.in$")
GENERAL_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
ALLOWED_CUSTOMER_TYPES = {"student", "faculty", "guest"}


def _validate_login_payload(data):
    customer_type = str(data.get("customerType", "")).strip().lower()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if customer_type not in ALLOWED_CUSTOMER_TYPES:
        return None, None, "Invalid customer type."

    if not email:
        return None, None, "Email is required."

    if customer_type in {"student", "faculty"}:
        if not KPRIET_EMAIL_PATTERN.fullmatch(email):
            return None, None, "Enter a valid KPRIET email (@kpriet.ac.in)."
    elif not GENERAL_EMAIL_PATTERN.fullmatch(email):
        return None, None, "Enter a valid email address."

    if not password:
        return None, None, "Password is required."

    if len(password) < 8:
        return None, None, "Password must contain at least 8 characters."

    return customer_type, email, None


@auth_bp.post("/customer/login")
def customer_login():
    data = request.get_json(silent=True) or {}
    customer_type, email, validation_error = _validate_login_payload(data)

    if validation_error:
        return jsonify({"success": False, "message": validation_error}), 400

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                u.id,
                u.email,
                u.password_hash,
                u.role,
                cp.customer_type,
                cp.full_name,
                cp.identifier
            FROM users u
            INNER JOIN customer_profiles cp ON cp.user_id = u.id
            WHERE LOWER(u.email) = %s
              AND cp.customer_type = %s
              AND u.role = 'customer'
              AND u.is_active = 1
            LIMIT 1
            """,
            (email, customer_type),
        )
        user = cursor.fetchone()

        if not user or not check_password_hash(user[2], str(data.get("password", ""))):
            return jsonify({
                "success": False,
                "message": "Invalid email, password, or customer type."
            }), 401

        session.clear()
        session["user_id"] = user[0]
        session["role"] = user[3]
        session["customer_type"] = user[4]

        return jsonify({
            "success": True,
            "message": "Login successful.",
            "user": {
                "id": user[0],
                "email": user[1],
                "role": user[3],
                "customer_type": user[4],
                "full_name": user[5],
                "identifier": user[6],
            },
            "redirect": "/pages/customer/dashboard.html",
        }), 200

    except Exception:
        app_logger = __import__("logging").getLogger(__name__)
        app_logger.exception("Customer login failed")
        return jsonify({
            "success": False,
            "message": "Unable to authenticate right now. Check the API and database configuration."
        }), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@auth_bp.post("/logout")
def logout():
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully."})


@auth_bp.get("/me")
def current_user():
    user_id = session.get("user_id")

    if not user_id:
        return jsonify({"authenticated": False}), 401

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT u.id, u.email, u.role, cp.customer_type, cp.full_name, cp.identifier
            FROM users u
            INNER JOIN customer_profiles cp ON cp.user_id = u.id
            WHERE u.id = %s AND u.is_active = 1
            LIMIT 1
            """,
            (user_id,),
        )
        user = cursor.fetchone()

        if not user:
            session.clear()
            return jsonify({"authenticated": False}), 401

        return jsonify({
            "authenticated": True,
            "user": {
                "id": user[0],
                "email": user[1],
                "role": user[2],
                "customer_type": user[3],
                "full_name": user[4],
                "identifier": user[5],
            },
        })

    except Exception:
        return jsonify({"authenticated": False, "message": "Unable to verify session."}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
