import os
import re
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import Blueprint, jsonify, request, session
from werkzeug.security import generate_password_hash, check_password_hash

from db import DB

auth_bp = Blueprint("auth", __name__)

KPRIET_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@kpriet\.ac\.in$")
GENERAL_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
ALLOWED_CUSTOMER_TYPES = {"student", "faculty", "guest"}


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"success": False, "message": "Authentication required."}), 401
        return f(*args, **kwargs)
    return decorated_function


def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get("user_id"):
                return jsonify({"success": False, "message": "Authentication required."}), 401
            user_role = session.get("role")
            if user_role not in allowed_roles:
                return jsonify({"success": False, "message": "Forbidden: Insufficient privileges."}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# Rate-limiting tracking for OTP abuse and brute-force protection
_otp_send_limits = {}
_otp_failed_verifications = {}


@auth_bp.post("/otp/send")
def send_otp():
    data = request.get_json(silent=True) or {}
    target = str(data.get("mobile") or data.get("email", "")).strip()

    if not target:
        return jsonify({"success": False, "message": "Mobile number or email is required."}), 400

    # Rate limit: max 5 OTP requests per target per 60 seconds
    now_ts = datetime.now().timestamp()
    send_history = [t for t in _otp_send_limits.get(target, []) if now_ts - t < 60]
    if len(send_history) >= 5:
        return jsonify({
            "success": False,
            "message": "Too many OTP requests. Please wait a minute before requesting again."
        }), 429
    send_history.append(now_ts)
    _otp_send_limits[target] = send_history

    # Generate 6-digit numeric OTP
    otp_code = str(secrets.randbelow(900000) + 100000)
    expires_at = (datetime.now() + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    purpose = str(data.get("purpose", "signup")).strip()

    DB.execute(
        "INSERT INTO otp_codes (target, code, purpose, expires_at, is_verified) VALUES (%s, %s, %s, %s, 0)",
        (target, otp_code, purpose, expires_at),
    )

    response_data = {
        "success": True,
        "message": f"OTP sent successfully to {target}.",
        "expires_in_minutes": 5,
    }

    # Only expose demo_otp in development testing mode
    if os.getenv("FLASK_ENV", "development").lower() == "development":
        response_data["demo_otp"] = otp_code
        response_data["debug_code"] = otp_code

    return jsonify(response_data), 200


@auth_bp.post("/otp/verify")
def verify_otp():
    data = request.get_json(silent=True) or {}
    target = str(data.get("mobile") or data.get("target") or data.get("email", "")).strip()
    code = str(data.get("code") or data.get("otp", "")).strip()

    if not target or not code:
        return jsonify({"success": False, "message": "Target and OTP code are required."}), 400

    # Brute-force protection: max 5 failed attempts per target per 5 minutes
    now_ts = datetime.now().timestamp()
    attempts, window_start = _otp_failed_verifications.get(target, (0, now_ts))
    if now_ts - window_start > 300:
        attempts, window_start = 0, now_ts

    if attempts >= 5:
        return jsonify({
            "success": False,
            "message": "Too many failed OTP attempts. Please wait 5 minutes before trying again."
        }), 429

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    otp_record = DB.get_one(
        """
        SELECT id FROM otp_codes
        WHERE target = %s AND code = %s AND is_verified = 0 AND expires_at >= %s
        ORDER BY id DESC LIMIT 1
        """,
        (target, code, now_str),
    )

    if not otp_record:
        _otp_failed_verifications[target] = (attempts + 1, window_start)
        return jsonify({"success": False, "message": "Invalid or expired OTP. Please try again."}), 400

    _otp_failed_verifications.pop(target, None)
    DB.execute("UPDATE otp_codes SET is_verified = 1 WHERE id = %s", (otp_record["id"],))

    return jsonify({"success": True, "verified": True, "message": "Mobile number verified successfully."}), 200


@auth_bp.post("/customer/signup")
def customer_signup():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    full_name = str(data.get("fullName") or data.get("name", "")).strip()
    customer_type = str(data.get("customerType") or data.get("user_type", "student")).strip().lower()
    identifier = str(data.get("identifier") or data.get("roll_number", "")).strip()
    mobile = str(data.get("mobile") or data.get("phone", "")).strip()

    if customer_type not in ALLOWED_CUSTOMER_TYPES:
        customer_type = "student"

    if not full_name:
        return jsonify({"success": False, "message": "Full name is required."}), 400

    if not email:
        return jsonify({"success": False, "message": "Email is required."}), 400

    if customer_type in {"student", "faculty"}:
        if not KPRIET_EMAIL_PATTERN.fullmatch(email):
            return jsonify({"success": False, "message": "Enter a valid KPRIET email (@kpriet.ac.in)."}), 400
    elif not GENERAL_EMAIL_PATTERN.fullmatch(email):
        return jsonify({"success": False, "message": "Enter a valid email address."}), 400

    if len(password) < 8:
        return jsonify({"success": False, "message": "Password must contain at least 8 characters."}), 400

    existing_user = DB.get_one("SELECT id FROM users WHERE LOWER(email) = %s", (email,))
    if existing_user:
        return jsonify({"success": False, "message": "An account with this email already exists."}), 409

    password_hash = generate_password_hash(password)
    user_id = DB.execute(
        "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
        (email, password_hash),
    )

    DB.execute(
        """
        INSERT INTO customer_profiles (user_id, customer_type, full_name, identifier, mobile)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (user_id, customer_type, full_name, identifier, mobile),
    )

    return jsonify({
        "success": True,
        "message": "Account created successfully! You can now log in.",
        "user_id": user_id,
        "redirect": "/pages/auth/login.html",
    }), 201


@auth_bp.post("/customer/login")
def customer_login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    customer_type = str(data.get("customerType", "")).strip().lower()

    if customer_type and customer_type not in ALLOWED_CUSTOMER_TYPES:
        return jsonify({"success": False, "message": "Invalid customer type."}), 400

    if not email or not password:
        return jsonify({"success": False, "message": "Email and password are required."}), 400

    user = DB.get_one(
        """
        SELECT u.id, u.email, u.password_hash, u.role, cp.customer_type, cp.full_name, cp.identifier
        FROM users u
        LEFT JOIN customer_profiles cp ON cp.user_id = u.id
        WHERE LOWER(u.email) = %s AND u.role = 'customer' AND u.is_active = 1
        LIMIT 1
        """,
        (email,),
    )

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"success": False, "message": "Invalid email, password, or customer type."}), 401

    if customer_type and user.get("customer_type") and user.get("customer_type") != customer_type:
        return jsonify({
            "success": False,
            "message": f"This account is registered as a {user.get('customer_type')}. Please sign in through the appropriate portal."
        }), 401

    session.clear()
    session["user_id"] = user["id"]
    session["role"] = user["role"]
    session["customer_type"] = user.get("customer_type") or "student"
    session["full_name"] = user.get("full_name") or "Customer"
    session["email"] = user["email"]

    return jsonify({
        "success": True,
        "message": "Login successful.",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "role": user["role"],
            "customer_type": user.get("customer_type"),
            "full_name": user.get("full_name"),
            "identifier": user.get("identifier"),
        },
        "redirect": "/pages/customer/dashboard.html",
    }), 200


@auth_bp.post("/vendor/login")
def vendor_login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    shop_hint = str(data.get("shop", "")).strip()

    if not email or not password:
        return jsonify({"success": False, "message": "Email and password are required."}), 400

    user = DB.get_one(
        """
        SELECT u.id, u.email, u.password_hash, u.role, s.id as shop_id, s.name as shop_name, s.slug as shop_slug
        FROM users u
        LEFT JOIN shops s ON s.owner_user_id = u.id
        WHERE LOWER(u.email) = %s AND u.role = 'vendor' AND u.is_active = 1
        LIMIT 1
        """,
        (email,),
    )

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"success": False, "message": "Invalid vendor credentials."}), 401

    session.clear()
    session["user_id"] = user["id"]
    session["role"] = "vendor"
    session["email"] = user["email"]
    session["shop_id"] = user.get("shop_id") or 1
    session["shop_name"] = user.get("shop_name") or "Food Court Stall"

    return jsonify({
        "success": True,
        "message": "Vendor authentication successful.",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "role": "vendor",
            "shop_id": user.get("shop_id"),
            "shop_name": user.get("shop_name"),
        },
        "redirect": f"/pages/vendor/dashboard.html?shop={user.get('shop_name', 'Stall')}",
    }), 200


@auth_bp.post("/admin/login")
def admin_login():
    data = request.get_json(silent=True) or {}
    identifier = str(data.get("username") or data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if not identifier or not password:
        return jsonify({"success": False, "message": "Security ID and passphrase are required."}), 400

    # Accept either username 'admin' or email 'admin@kpriet.ac.in'
    user = DB.get_one(
        """
        SELECT id, email, password_hash, role FROM users
        WHERE (LOWER(email) = %s OR LOWER(email) LIKE %s) AND role = 'admin' AND is_active = 1
        LIMIT 1
        """,
        (identifier, f"{identifier}@%"),
    )

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"success": False, "message": "Access Denied: Invalid root access identifiers."}), 401

    session.clear()
    session["user_id"] = user["id"]
    session["role"] = "admin"
    session["email"] = user["email"]

    return jsonify({
        "success": True,
        "message": "Admin authentication successful.",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "role": "admin",
        },
        "redirect": "/pages/admin/dashboard.html",
    }), 200


@auth_bp.post("/logout")
def logout():
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully."}), 200


@auth_bp.get("/me")
def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"authenticated": False}), 401

    user = DB.get_one(
        """
        SELECT u.id, u.email, u.role, cp.customer_type, cp.full_name, cp.identifier, cp.mobile,
               s.id as shop_id, s.name as shop_name
        FROM users u
        LEFT JOIN customer_profiles cp ON cp.user_id = u.id
        LEFT JOIN shops s ON s.owner_user_id = u.id
        WHERE u.id = %s AND u.is_active = 1
        LIMIT 1
        """,
        (user_id,),
    )

    if not user:
        session.clear()
        return jsonify({"authenticated": False}), 401

    return jsonify({
        "authenticated": True,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "role": user["role"],
            "customer_type": user.get("customer_type"),
            "full_name": user.get("full_name") or user.get("shop_name") or ("Administrator" if user["role"] == "admin" else "User"),
            "identifier": user.get("identifier"),
            "mobile": user.get("mobile"),
            "shop_id": user.get("shop_id"),
            "shop_name": user.get("shop_name"),
        },
    }), 200
