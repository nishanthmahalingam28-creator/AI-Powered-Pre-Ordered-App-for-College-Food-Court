import logging
from datetime import datetime
from flask import Blueprint, jsonify, request, session
from werkzeug.security import generate_password_hash, check_password_hash

from db import DB
from routes.auth import login_required, role_required, normalize_mobile

logger = logging.getLogger("food_court.customer")
customer_bp = Blueprint("customer", __name__)


@customer_bp.get("/profile")
@login_required
@role_required(["customer"])
def get_profile():
    """Retrieves the authenticated customer's profile details."""
    user_id = session.get("user_id")

    profile = DB.get_one(
        """
        SELECT u.id, u.email, u.role, cp.customer_type, cp.full_name, cp.identifier, cp.mobile,
               cp.created_at, cp.updated_at
        FROM users u
        LEFT JOIN customer_profiles cp ON cp.user_id = u.id
        WHERE u.id = %s AND u.is_active = 1
        LIMIT 1
        """,
        (user_id,),
    )

    if not profile:
        return jsonify({"success": False, "message": "Customer profile not found."}), 404

    profile_data = {
        "id": profile["id"],
        "email": profile["email"],
        "role": profile.get("role", "customer"),
        "customer_type": profile.get("customer_type"),
        "full_name": profile.get("full_name") or "",
        "identifier": profile.get("identifier") or "",
        "mobile": profile.get("mobile") or "",
        "created_at": str(profile.get("created_at") or ""),
    }

    return jsonify({
        "success": True,
        "profile": profile_data,
        "user": profile_data,
    }), 200


@customer_bp.put("/profile")
@login_required
@role_required(["customer"])
def update_profile():
    """
    Updates editable fields for the authenticated customer.
    - full_name can be updated directly.
    - mobile requires OTP verification if changed.
    - email, role, and customer_type are strictly immutable through this endpoint.
    """
    user_id = session.get("user_id")
    data = request.get_json(silent=True) or {}

    new_full_name = str(data.get("full_name") or data.get("name", "")).strip()
    raw_mobile = data.get("mobile")

    current_profile = DB.get_one(
        "SELECT id, full_name, mobile FROM customer_profiles WHERE user_id = %s LIMIT 1",
        (user_id,),
    )

    if not current_profile:
        return jsonify({"success": False, "message": "Customer profile not found."}), 404

    full_name_to_save = new_full_name if new_full_name else current_profile.get("full_name")
    if not full_name_to_save:
        return jsonify({"success": False, "message": "Full name cannot be empty."}), 400

    mobile_to_save = current_profile.get("mobile")

    # If mobile is being changed, require valid OTP verification
    if raw_mobile is not None:
        normalized_new_mobile = normalize_mobile(str(raw_mobile).strip())
        if not normalized_new_mobile:
            return jsonify({
                "success": False,
                "message": "Enter a valid 10-digit Indian mobile number (starts with 6, 7, 8, or 9)."
            }), 400

        if normalized_new_mobile != current_profile.get("mobile"):
            # Check duplicate mobile on another active customer
            existing_mobile = DB.get_one(
                """
                SELECT cp.id FROM customer_profiles cp
                JOIN users u ON u.id = cp.user_id
                WHERE cp.mobile = %s AND cp.user_id != %s AND u.is_active = 1
                LIMIT 1
                """,
                (normalized_new_mobile, user_id),
            )
            if existing_mobile:
                return jsonify({
                    "success": False,
                    "message": "This mobile number is already linked to another active account."
                }), 409

            # Verify OTP record for mobile_update
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            verified_otp = DB.get_one(
                """
                SELECT id FROM otp_codes
                WHERE target = %s AND purpose = 'mobile_update' AND is_verified = 1 AND is_consumed = 0 AND expires_at >= %s
                ORDER BY id DESC LIMIT 1
                """,
                (normalized_new_mobile, now_str),
            )

            # If client provided an inline code, verify it now
            otp_code_in_body = str(data.get("otp") or "").strip()
            if not verified_otp and otp_code_in_body:
                otp_match = DB.get_one(
                    """
                    SELECT id FROM otp_codes
                    WHERE target = %s AND code = %s AND (purpose = 'mobile_update' OR purpose = 'profile')
                      AND is_verified = 0 AND expires_at >= %s
                    ORDER BY id DESC LIMIT 1
                    """,
                    (normalized_new_mobile, otp_code_in_body, now_str),
                )
                if otp_match:
                    DB.execute("UPDATE otp_codes SET is_verified = 1, verified_at = %s WHERE id = %s", (now_str, otp_match["id"]))
                    verified_otp = otp_match

            if not verified_otp:
                return jsonify({
                    "success": False,
                    "message": "Mobile number change requires successful OTP verification for the new number."
                }), 400

            # Consume verified OTP record
            DB.execute("UPDATE otp_codes SET is_consumed = 1 WHERE id = %s", (verified_otp["id"],))
            mobile_to_save = normalized_new_mobile

    # Persist profile changes
    DB.execute(
        """
        UPDATE customer_profiles
        SET full_name = %s, mobile = %s
        WHERE user_id = %s
        """,
        (full_name_to_save, mobile_to_save, user_id),
    )

    session["full_name"] = full_name_to_save
    session["mobile"] = mobile_to_save

    updated_data = {
        "id": user_id,
        "full_name": full_name_to_save,
        "mobile": mobile_to_save,
    }

    return jsonify({
        "success": True,
        "message": "Profile updated successfully.",
        "profile": updated_data,
        "user": updated_data,
    }), 200


@customer_bp.put("/password")
@login_required
@role_required(["customer"])
def change_password():
    """
    Updates the authenticated customer's password.
    Requires current password verification and new password confirmation.
    """
    user_id = session.get("user_id")
    data = request.get_json(silent=True) or {}

    current_password = str(data.get("current_password") or "").strip()
    new_password = str(data.get("new_password") or "").strip()
    confirm_password = str(data.get("confirm_password") or "").strip()

    if not current_password:
        return jsonify({"success": False, "message": "Current password is required."}), 400

    if not new_password:
        return jsonify({"success": False, "message": "New password is required."}), 400

    if confirm_password and new_password != confirm_password:
        return jsonify({"success": False, "message": "New passwords do not match."}), 400

    if len(new_password) < 8:
        return jsonify({"success": False, "message": "New password must contain at least 8 characters."}), 400

    user = DB.get_one("SELECT id, password_hash FROM users WHERE id = %s AND is_active = 1", (user_id,))
    if not user or not check_password_hash(user["password_hash"], current_password):
        return jsonify({"success": False, "message": "Current password is incorrect."}), 400

    new_hash = generate_password_hash(new_password)
    DB.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, user_id))

    logger.info("Customer password updated successfully for user_id=%s", user_id)
    return jsonify({
        "success": True,
        "message": "Password updated successfully."
    }), 200
