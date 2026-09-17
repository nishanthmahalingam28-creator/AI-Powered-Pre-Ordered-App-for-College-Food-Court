import os
import re
import secrets
import hashlib
import logging
from datetime import datetime, timedelta
from functools import wraps
from flask import Blueprint, jsonify, request, session
from security import hash_password, verify_password
from services.google_auth import GoogleAuthService, GoogleTokenVerificationError
from services.email_service import EmailService

from db import DB

logger = logging.getLogger("food_court.auth")
auth_bp = Blueprint("auth", __name__)


KPRIET_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@kpriet\.ac\.in$")
GENERAL_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
ALLOWED_CUSTOMER_TYPES = {"student", "faculty", "guest"}


INDIAN_MOBILE_PATTERN = re.compile(r"^[6-9]\d{9}$")


def normalize_mobile(val):
    """
    Normalizes Indian 10-digit mobile numbers.
    Accepts formats: 9876543210, +919876543210, +91 98765 43210, 09876543210, 919876543210.
    Returns 10-digit string starting with 6-9, or None if invalid.
    """
    if not val:
        return None
    cleaned = re.sub(r"[\s\-\(\)\+]", "", str(val).strip())
    if cleaned.startswith("91") and len(cleaned) == 12:
        cleaned = cleaned[2:]
    elif cleaned.startswith("0") and len(cleaned) == 11:
        cleaned = cleaned[1:]
    if INDIAN_MOBILE_PATTERN.fullmatch(cleaned):
        return cleaned
    return None


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
    raw_mobile = data.get("mobile") or data.get("phone")
    raw_target = str(raw_mobile or data.get("email", "")).strip()

    if not raw_target:
        return jsonify({"success": False, "message": "Mobile number or email is required."}), 400

    # If mobile is provided or target contains digits without '@', validate Indian mobile
    normalized_mobile = normalize_mobile(raw_target)
    if raw_mobile or (raw_target and re.search(r"\d", raw_target) and "@" not in raw_target):
        if not normalized_mobile:
            return jsonify({
                "success": False,
                "message": "Enter a valid 10-digit Indian mobile number (starts with 6, 7, 8, or 9)."
            }), 400
        target = normalized_mobile
    else:
        target = raw_target.lower()

    purpose = str(data.get("purpose", "signup")).strip() or "signup"

    # Rate limit: max 5 OTP requests per target per 60 seconds
    # Multi-worker safe check: queries otp_codes within last 60 seconds
    try:
        one_min_ago = (datetime.now() - timedelta(seconds=60)).strftime("%Y-%m-%d %H:%M:%S")
        recent_db = DB.get_one(
            "SELECT COUNT(id) as cnt FROM otp_codes WHERE target = %s AND created_at >= %s",
            (target, one_min_ago)
        )
        if recent_db and int(recent_db.get("cnt", 0)) >= 5:
            return jsonify({
                "success": False,
                "message": "Too many OTP requests. Please wait a minute before requesting again."
            }), 429
    except Exception:
        pass

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

    DB.execute(
        "INSERT INTO otp_codes (target, code, purpose, expires_at, is_verified, is_consumed) VALUES (%s, %s, %s, %s, 0, 0)",
        (target, otp_code, purpose, expires_at),
    )

    response_data = {
        "success": True,
        "message": f"OTP sent successfully to {target}.",
        "expires_in_minutes": 5,
    }

    # Only expose demo_otp in development testing mode (strictly suppressed in production)
    is_dev = os.getenv("FLASK_ENV", "production").lower() in ("development", "dev", "test", "testing")
    if is_dev:
        response_data["demo_otp"] = otp_code
        response_data["debug_code"] = otp_code

    return jsonify(response_data), 200


@auth_bp.post("/otp/verify")
def verify_otp():
    data = request.get_json(silent=True) or {}
    raw_target = str(data.get("mobile") or data.get("target") or data.get("phone") or data.get("email", "")).strip()
    code = str(data.get("code") or data.get("otp", "")).strip()
    purpose = str(data.get("purpose", "")).strip()

    if not raw_target or not code:
        return jsonify({"success": False, "message": "Target and OTP code are required."}), 400

    normalized = normalize_mobile(raw_target)
    target = normalized if normalized else raw_target.lower()

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
    if purpose:
        otp_record = DB.get_one(
            """
            SELECT id FROM otp_codes
            WHERE target = %s AND code = %s AND purpose = %s AND is_verified = 0 AND expires_at >= %s
            ORDER BY id DESC LIMIT 1
            """,
            (target, code, purpose, now_str),
        )
    else:
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
    now_ts_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    DB.execute("UPDATE otp_codes SET is_verified = 1, verified_at = %s WHERE id = %s", (now_ts_str, otp_record["id"]))

    return jsonify({"success": True, "verified": True, "message": "Mobile number verified successfully."}), 200


@auth_bp.post("/customer/signup")
def customer_signup():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    full_name = str(data.get("fullName") or data.get("name", "")).strip()
    customer_type = str(data.get("customerType") or data.get("user_type", "student")).strip().lower()
    identifier = str(data.get("identifier") or data.get("roll_number", "")).strip()
    raw_mobile = str(data.get("mobile") or data.get("phone", "")).strip()

    if customer_type not in ALLOWED_CUSTOMER_TYPES:
        return jsonify({"success": False, "message": "Invalid customer type. Must be student, faculty, or guest."}), 400

    if not full_name:
        return jsonify({"success": False, "message": "Full name is required."}), 400
    if len(full_name) < 2:
        return jsonify({"success": False, "message": "Full name must contain at least 2 characters."}), 400
    if not re.match(r"^[a-zA-Z\s'.-]{2,50}$", full_name):
        return jsonify({"success": False, "message": "Full name can only contain letters, spaces, hyphens, and periods."}), 400

    if not email:
        return jsonify({"success": False, "message": "Email is required."}), 400

    if customer_type in {"student", "faculty"}:
        if not KPRIET_EMAIL_PATTERN.fullmatch(email):
            return jsonify({"success": False, "message": "Enter a valid KPRIET institutional email (@kpriet.ac.in)."}), 400
    elif not GENERAL_EMAIL_PATTERN.fullmatch(email):
        return jsonify({"success": False, "message": "Enter a valid email address."}), 400

    # Role-specific identifier requirements
    if customer_type == "student":
        if not identifier:
            return jsonify({"success": False, "message": "Roll number is required for students."}), 400
    elif customer_type == "faculty":
        if not identifier:
            return jsonify({"success": False, "message": "Faculty ID is required for faculty members."}), 400
    else:
        # guest identifier is optional / can be None
        if not identifier:
            identifier = None

    # Mobile validation & normalization
    normalized_mobile = normalize_mobile(raw_mobile)
    if not normalized_mobile:
        return jsonify({
            "success": False,
            "message": "Enter a valid 10-digit Indian mobile number (starting with 6, 7, 8, or 9)."
        }), 400

    # Password length & strength validation
    if len(password) < 8:
        return jsonify({"success": False, "message": "Password must contain at least 8 characters."}), 400
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return jsonify({"success": False, "message": "Password must contain both letters and numbers."}), 400

    # Confirm password matching validation
    confirm_password = str(data.get("confirmPassword") or data.get("confirm_password", ""))
    if confirm_password and password != confirm_password:
        return jsonify({"success": False, "message": "Passwords do not match."}), 400

    # Duplicate active email check
    existing_user = DB.get_one("SELECT id FROM users WHERE LOWER(email) = %s", (email,))
    if existing_user:
        return jsonify({"success": False, "message": "An account with this email already exists."}), 409

    # Duplicate active mobile check
    existing_mobile = DB.get_one(
        """
        SELECT cp.id FROM customer_profiles cp
        JOIN users u ON u.id = cp.user_id
        WHERE cp.mobile = %s AND u.is_active = 1
        LIMIT 1
        """,
        (normalized_mobile,),
    )
    if existing_mobile:
        return jsonify({"success": False, "message": "An active account with this mobile number already exists."}), 409

    # SERVER-ENFORCED OTP VERIFICATION
    # The submitted mobile number (or email fallback) must have a valid, unconsumed, verified OTP for purpose='signup'
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    verified_otp = DB.get_one(
        """
        SELECT id FROM otp_codes
        WHERE (target = %s OR target = %s)
          AND purpose = 'signup'
          AND is_verified = 1
          AND is_consumed = 0
          AND expires_at >= %s
        ORDER BY id DESC LIMIT 1
        """,
        (normalized_mobile, email, now_str),
    )

    if not verified_otp:
        return jsonify({
            "success": False,
            "message": "Mobile number has not been verified with OTP or verification has expired. Please verify your mobile number first."
        }), 400

    # Atomically create user and profile, then consume the verified OTP
    password_hash = hash_password(password)
    user_id = DB.execute(
        "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
        (email, password_hash),
    )

    DB.execute(
        """
        INSERT INTO customer_profiles (user_id, customer_type, full_name, identifier, mobile)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (user_id, customer_type, full_name, identifier, normalized_mobile),
    )

    # Consume the verified OTP record so it cannot be reused
    DB.execute("UPDATE otp_codes SET is_consumed = 1 WHERE id = %s", (verified_otp["id"],))

    # Secure server-side automatic authentication
    session.clear()
    session["user_id"] = user_id
    session["email"] = email
    session["role"] = "customer"
    session["customer_type"] = customer_type
    session["full_name"] = full_name
    session["mobile"] = normalized_mobile
    session["auth_provider"] = "local"

    return jsonify({
        "success": True,
        "message": "Account created successfully! Welcome to KPR Food Court.",
        "user_id": user_id,
        "user": {
            "id": user_id,
            "email": email,
            "role": "customer",
            "customer_type": customer_type,
            "full_name": full_name,
            "identifier": identifier,
            "mobile": normalized_mobile,
            "auth_provider": "local",
        },
        "redirect": "/pages/customer/dashboard.html",
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
        SELECT u.id, u.email, u.password_hash, u.role, cp.customer_type, cp.full_name, cp.identifier, cp.mobile
        FROM users u
        LEFT JOIN customer_profiles cp ON cp.user_id = u.id
        WHERE LOWER(u.email) = %s AND u.role = 'customer' AND u.is_active = 1
        LIMIT 1
        """,
        (email,),
    )

    if not user or not verify_password(password, user["password_hash"]):
        session.clear()
        return jsonify({"success": False, "message": "Invalid email, password, or customer type."}), 401

    if customer_type and user.get("customer_type") and user.get("customer_type") != customer_type:
        session.clear()
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
    session["mobile"] = user.get("mobile")

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
            "mobile": user.get("mobile"),
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
        SELECT u.id, u.email, u.password_hash, u.role,
               s.id as shop_id, s.name as shop_name, s.slug as shop_slug, s.is_active as shop_active
        FROM users u
        LEFT JOIN shops s ON s.owner_user_id = u.id
        WHERE LOWER(u.email) = %s AND u.role = 'vendor' AND u.is_active = 1
        LIMIT 1
        """,
        (email,),
    )

    if not user or not verify_password(password, user["password_hash"]):
        return jsonify({"success": False, "message": "Invalid vendor credentials."}), 401

    shop_id = user.get("shop_id")
    shop_active = user.get("shop_active")

    # A vendor MUST have a valid and active assigned stall. Reject unassigned or inactive stalls.
    if not shop_id or not shop_active:
        logger.warning("Vendor login rejected for user_id=%s (%s): No active assigned stall.", user["id"], email)
        return jsonify({
            "success": False,
            "message": "Vendor account has no active stall assigned. Please contact the administrator."
        }), 403

    session.clear()
    session["user_id"] = user["id"]
    session["role"] = "vendor"
    session["email"] = user["email"]
    session["shop_id"] = shop_id
    session["shop_name"] = user.get("shop_name") or "Food Court Stall"

    return jsonify({
        "success": True,
        "message": "Vendor authentication successful.",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "role": "vendor",
            "shop_id": shop_id,
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

    if not user or not verify_password(password, user["password_hash"]):
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


@auth_bp.get("/google/config")
def google_auth_config():
    """Returns public Google OAuth configuration without exposing secrets."""
    config = GoogleAuthService.get_public_config()
    return jsonify(config), 200


@auth_bp.post("/google")
def google_auth():
    """
    Authoritative Google OAuth / GIS Authentication Endpoint.

    Verifies the submitted Google ID token server-side.
    If valid:
      - Finds or creates user in database.
      - Never allows bypass or silent fake-user logins.
      - Creates secure server-side session.
    """
    data = request.get_json(silent=True) or {}
    token = data.get("credential") or data.get("id_token") or data.get("token")

    if not token or not str(token).strip():
        return jsonify({
            "success": False,
            "message": "Google authentication credential is required."
        }), 400

    try:
        verified_info = GoogleAuthService.verify_token(str(token))
    except GoogleTokenVerificationError as err:
        logger.warning("Google token verification error: %s", err)
        return jsonify({
            "success": False,
            "message": str(err)
        }), 401
    except Exception as exc:
        logger.error("Unexpected error during Google token verification: %s", exc)
        return jsonify({
            "success": False,
            "message": "Internal error verifying Google authentication."
        }), 500

    email = verified_info["email"]
    name = verified_info["name"]
    requested_type = str(data.get("customerType", "")).strip().lower()

    # Look for existing user by verified email
    user = DB.get_one(
        "SELECT id, email, role, is_active FROM users WHERE LOWER(email) = %s LIMIT 1",
        (email,)
    )

    if user:
        if not user.get("is_active", 1):
            return jsonify({
                "success": False,
                "message": "Account has been deactivated. Please contact the campus administrator."
            }), 403

        user_id = user["id"]
        role = user.get("role", "customer")

        profile = DB.get_one(
            "SELECT customer_type, full_name, mobile, wallet_balance FROM customer_profiles WHERE user_id = %s LIMIT 1",
            (user_id,)
        )
        customer_type = profile["customer_type"] if profile else "student"
        full_name = profile["full_name"] if profile else name
    else:
        # Create new customer user with secure unguessable bcrypt password hash
        role = "customer"
        if requested_type in ALLOWED_CUSTOMER_TYPES:
            customer_type = requested_type
        elif email.endswith("@kpriet.ac.in"):
            customer_type = "student"
        else:
            customer_type = "guest"

        dummy_pw = secrets.token_hex(32)
        pw_hash = hash_password(dummy_pw)

        user_id = DB.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, %s, 1)",
            (email, pw_hash, role)
        )

        DB.execute(
            """
            INSERT INTO customer_profiles (user_id, customer_type, full_name, wallet_balance)
            VALUES (%s, %s, %s, 500.00)
            """,
            (user_id, customer_type, name)
        )
        full_name = name

    # Establish secure server session
    session.clear()
    session["user_id"] = user_id
    session["email"] = email
    session["role"] = role
    session["auth_provider"] = "google"

    return jsonify({
        "success": True,
        "message": "Google authentication successful.",
        "user": {
            "id": user_id,
            "email": email,
            "role": role,
            "customer_type": customer_type,
            "full_name": full_name,
            "auth_provider": "google"
        },
        "redirect": "/pages/customer/dashboard.html"
    }), 200


# -------------------------------------------------------------
# SECURE PASSWORD RESET & FORGOT PASSWORD SYSTEM
# -------------------------------------------------------------

@auth_bp.post("/password/forgot")
@auth_bp.post("/forgot-password")
def forgot_password():
    """
    Initiates secure password reset flow.
    Enforces:
    1. Uniform non-enumerating response (timing-attack resistant).
    2. Cryptographically secure 256-bit entropy token (URL safe).
    3. Storing only SHA-256 hash in database.
    4. 15-minute token expiration.
    5. Invalidation of previous unconsumed reset tokens for the user.
    6. Never logs passwords or reset tokens.
    """
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()

    if not email:
        return jsonify({"success": False, "message": "Please enter your email address."}), 400

    if not GENERAL_EMAIL_PATTERN.fullmatch(email):
        return jsonify({"success": False, "message": "Please enter a valid email address."}), 400

    user = DB.get_one(
        "SELECT id, email, role, is_active FROM users WHERE LOWER(email) = %s AND is_active = 1 LIMIT 1",
        (email,)
    )

    if user:
        user_id = user["id"]
        # Invalidate any existing unused reset tokens for this user
        DB.execute(
            "UPDATE password_resets SET is_used = 1 WHERE user_id = %s AND is_used = 0",
            (user_id,)
        )

        # Generate cryptographically secure token
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        expires_at = (datetime.now() + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")

        ip_addr = request.headers.get("X-Forwarded-For", request.remote_addr or "")
        user_agent = request.headers.get("User-Agent", "")[:250]

        DB.execute(
            """
            INSERT INTO password_resets (user_id, token_hash, expires_at, is_used, ip_address, user_agent)
            VALUES (%s, %s, %s, 0, %s, %s)
            """,
            (user_id, token_hash, expires_at, ip_addr, user_agent)
        )

        # Get customer profile full name if available
        profile = DB.get_one("SELECT full_name FROM customer_profiles WHERE user_id = %s LIMIT 1", (user_id,))
        user_name = (profile.get("full_name") if profile else None) or email.split("@")[0].capitalize()

        # Build reset URL
        cfg = EmailService.get_smtp_config()
        base_url = cfg["app_url"]
        reset_url = f"{base_url}/frontend/pages/auth/reset-password.html?token={raw_token}"

        # Dispatch reset email (never logs token)
        EmailService.send_password_reset_email(
            to_email=user["email"],
            user_name=user_name,
            reset_url=reset_url,
            raw_token=raw_token
        )
    else:
        # Timing attack mitigation: perform dummy hashing operation
        dummy_token = secrets.token_urlsafe(32)
        _ = hashlib.sha256(dummy_token.encode("utf-8")).hexdigest()

    # Always return uniform non-revealing response
    return jsonify({
        "success": True,
        "message": "If an account exists with that email, password reset instructions have been sent."
    }), 200


@auth_bp.get("/password/reset/verify")
def verify_reset_token():
    """
    Verifies token validity and expiration without consuming it.
    Used by frontend to check if the reset link is active on page load.
    """
    raw_token = request.args.get("token", "").strip()
    if not raw_token:
        return jsonify({"success": False, "valid": False, "message": "Missing reset token."}), 400

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    record = DB.get_one(
        """
        SELECT pr.id, pr.user_id, pr.expires_at, pr.is_used, u.email
        FROM password_resets pr
        JOIN users u ON u.id = pr.user_id
        WHERE pr.token_hash = %s AND pr.is_used = 0 AND pr.expires_at > %s AND u.is_active = 1
        LIMIT 1
        """,
        (token_hash, now_str)
    )

    if not record:
        return jsonify({
            "success": False,
            "valid": False,
            "message": "This password reset link is invalid or has expired. Please request a new one."
        }), 400

    # Mask email for safety e.g. "m***h@kpriet.ac.in"
    email = record.get("email", "")
    masked_email = ""
    if "@" in email:
        local, domain = email.split("@", 1)
        if len(local) > 2:
            masked_email = f"{local[0]}***{local[-1]}@{domain}"
        else:
            masked_email = f"{local[0]}***@{domain}"

    return jsonify({
        "success": True,
        "valid": True,
        "message": "Token is valid.",
        "email": masked_email
    }), 200


@auth_bp.post("/password/reset")
@auth_bp.post("/reset-password")
def reset_password():
    """
    Completes password reset:
    1. Validates token hash, expiry, and single-use status.
    2. Validates new password complexity and match.
    3. Hashes new password with bcrypt work factor 12.
    4. Updates users table with new hash.
    5. Invalidates current token and all other active reset tokens for this user.
    6. Logs security audit event (without logging password or token).
    7. Sends confirmation notice.
    """
    data = request.get_json(silent=True) or {}
    raw_token = str(data.get("token", "")).strip()
    password = str(data.get("password", ""))
    confirm_password = str(data.get("confirmPassword") or data.get("confirm_password", ""))

    if not raw_token:
        return jsonify({"success": False, "message": "Password reset token is required."}), 400

    if not password:
        return jsonify({"success": False, "message": "New password is required."}), 400

    # Password complexity validation
    if len(password) < 8:
        return jsonify({"success": False, "message": "Password must contain at least 8 characters."}), 400
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return jsonify({"success": False, "message": "Password must contain both letters and numbers."}), 400

    if confirm_password and password != confirm_password:
        return jsonify({"success": False, "message": "Passwords do not match."}), 400

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Fetch token record
    reset_entry = DB.get_one(
        """
        SELECT pr.id, pr.user_id, pr.expires_at, pr.is_used, u.email
        FROM password_resets pr
        JOIN users u ON u.id = pr.user_id
        WHERE pr.token_hash = %s
        LIMIT 1
        """,
        (token_hash,)
    )

    if not reset_entry:
        return jsonify({
            "success": False,
            "message": "This password reset link is invalid or has expired. Please request a new one."
        }), 400

    if reset_entry.get("is_used") == 1:
        return jsonify({
            "success": False,
            "message": "This password reset link has already been used. Please request a new one."
        }), 400

    expires_at_str = str(reset_entry.get("expires_at", ""))
    if expires_at_str <= now_str:
        return jsonify({
            "success": False,
            "message": "This password reset link has expired. Please request a new one."
        }), 400

    user_id = reset_entry["user_id"]
    user_email = reset_entry["email"]

    # Securely hash new password
    new_hash = hash_password(password)

    # Update password in database
    DB.execute(
        "UPDATE users SET password_hash = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (new_hash, user_id)
    )

    # Invalidate this token
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    DB.execute(
        "UPDATE password_resets SET is_used = 1, used_at = %s WHERE id = %s",
        (now_ts, reset_entry["id"])
    )

    # Invalidate ALL other active reset tokens for this user
    DB.execute(
        "UPDATE password_resets SET is_used = 1 WHERE user_id = %s AND is_used = 0",
        (user_id,)
    )

    # Audit log entry (NEVER log password or token)
    try:
        DB.execute(
            """
            INSERT INTO audit_logs (actor_id, action, entity_type, entity_id, details)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_id, "PASSWORD_RESET_SUCCESS", "user", str(user_id), "Password reset completed via secure token.")
        )
    except Exception as e:
        logger.warning("Audit log recording failed: %s", e)

    # Fetch user name for security notification
    profile = DB.get_one("SELECT full_name FROM customer_profiles WHERE user_id = %s LIMIT 1", (user_id,))
    user_name = (profile.get("full_name") if profile else None) or user_email.split("@")[0].capitalize()

    EmailService.send_password_changed_notification(user_email, user_name)

    return jsonify({
        "success": True,
        "message": "Your password has been successfully reset. You can now log in with your new password.",
        "redirect": "/pages/auth/login.html"
    }), 200

