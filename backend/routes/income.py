"""
Authenticated Income Management Routes for College Food Court Application.

Enforces:
1. Session-derived user ownership (user_id strictly extracted from session, ignoring client payload).
2. Complete CRUD operations:
   - POST /api/income (create)
   - GET /api/income (list current user's income records)
   - GET /api/income/<id> (retrieve single income record)
   - PUT /api/income/<id> (update income record)
   - DELETE /api/income/<id> (delete income record)
3. Strict validation on amount (> 0), date (YYYY-MM-DD format), source, and description.
4. Strict IDOR protection: prevents reading, updating, or deleting another user's income.
"""

import re
import logging
from datetime import datetime
from flask import Blueprint, jsonify, request, session
from db import DB
from routes.auth import login_required

logger = logging.getLogger("food_court.income")
income_bp = Blueprint("income", __name__)


def _validate_income_payload(data: dict, is_update: bool = False):
    """
    Validates input fields for creating or updating an income record.
    Returns (cleaned_data, error_message).
    """
    if not isinstance(data, dict):
        return None, "Request body must be a JSON object."

    cleaned = {}

    # Validate amount
    if "amount" not in data and not is_update:
        return None, "Amount is required."

    if "amount" in data:
        raw_amount = data.get("amount")
        try:
            amount = float(raw_amount)
            if amount <= 0:
                return None, "Amount must be a positive number greater than 0."
            if amount > 1000000:
                return None, "Amount exceeds maximum limit of 1,000,000."
            cleaned["amount"] = round(amount, 2)
        except (ValueError, TypeError):
            return None, "Amount must be a valid numeric value."

    # Validate date
    date_val = data.get("date") or data.get("income_date")
    if not date_val and not is_update:
        return None, "Date is required."

    if date_val is not None:
        date_str = str(date_val).strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            return None, "Date must be in YYYY-MM-DD format."
        try:
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            cleaned["income_date"] = parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            return None, "Date must be a valid calendar date."

    # Validate source (also accept category as alias)
    source_val = data.get("source") or data.get("category")
    if not source_val and not is_update:
        return None, "Income source is required."

    if source_val is not None:
        source = str(source_val).strip()
        if not source:
            return None, "Income source cannot be empty."
        if len(source) > 100:
            return None, "Income source must not exceed 100 characters."
        cleaned["source"] = source

    # Validate description
    if "description" not in data and not is_update:
        return None, "Description is required."

    if "description" in data:
        description = str(data.get("description") or "").strip()
        if not description:
            return None, "Description cannot be empty."
        if len(description) > 255:
            return None, "Description must not exceed 255 characters."
        cleaned["description"] = description

    return cleaned, None


@income_bp.post("")
@login_required
def create_income():
    """
    Creates a new income record.
    Owner user_id is strictly derived from the authenticated session.
    Any client-provided userId is strictly ignored.
    """
    user_id = session.get("user_id")

    payload = request.get_json(silent=True) or {}
    cleaned, err = _validate_income_payload(payload, is_update=False)
    if err:
        return jsonify({"success": False, "message": err}), 400

    try:
        new_id = DB.execute(
            """
            INSERT INTO income (user_id, amount, source, description, income_date)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                user_id,
                cleaned["amount"],
                cleaned["source"],
                cleaned["description"],
                cleaned["income_date"]
            )
        )

        record = DB.get_one(
            """
            SELECT id, user_id, amount, source, description, income_date, created_at, updated_at
            FROM income
            WHERE id = %s
            """,
            (new_id,)
        )

        if record:
            record["amount"] = float(record["amount"])
            record["income_date"] = str(record["income_date"])
            record["date"] = str(record["income_date"])
            record["created_at"] = str(record.get("created_at") or "")
            record["updated_at"] = str(record.get("updated_at") or "")

        return jsonify({
            "success": True,
            "message": "Income record created successfully.",
            "income": record
        }), 201

    except Exception as e:
        logger.exception("Failed to create income for user %s: %s", user_id, e)
        return jsonify({"success": False, "message": "Failed to create income record."}), 500


@income_bp.get("")
@login_required
def get_income_list():
    """
    Retrieves all income records belonging to the authenticated user.
    Never exposes other users' records.
    """
    user_id = session.get("user_id")

    try:
        rows = DB.get_all(
            """
            SELECT id, user_id, amount, source, description, income_date, created_at, updated_at
            FROM income
            WHERE user_id = %s
            ORDER BY income_date DESC, id DESC
            """,
            (user_id,)
        )

        income_records = []
        total_amount = 0.0
        for r in rows:
            amt = float(r.get("amount") or 0.0)
            total_amount += amt
            income_records.append({
                "id": r["id"],
                "user_id": r["user_id"],
                "amount": amt,
                "source": r["source"],
                "category": r["source"],
                "description": r["description"],
                "income_date": str(r["income_date"]),
                "date": str(r["income_date"]),
                "created_at": str(r.get("created_at") or ""),
                "updated_at": str(r.get("updated_at") or "")
            })

        return jsonify({
            "success": True,
            "income": income_records,
            "count": len(income_records),
            "total_amount": round(total_amount, 2)
        }), 200

    except Exception as e:
        logger.exception("Failed to fetch income for user %s: %s", user_id, e)
        return jsonify({"success": False, "message": "Failed to retrieve income records."}), 500


@income_bp.get("/<int:income_id>")
@login_required
def get_single_income(income_id: int):
    """
    Retrieves a single income record by ID.
    Strictly verifies ownership; returns 403/404 if not found or owned by someone else.
    """
    user_id = session.get("user_id")

    record = DB.get_one(
        """
        SELECT id, user_id, amount, source, description, income_date, created_at, updated_at
        FROM income
        WHERE id = %s
        """,
        (income_id,)
    )

    if not record:
        return jsonify({"success": False, "message": "Income record not found."}), 404

    # IDOR protection: if user is not the owner, reject
    if record["user_id"] != user_id:
        return jsonify({"success": False, "message": "Access denied. You do not own this income record."}), 403

    record["amount"] = float(record["amount"])
    record["income_date"] = str(record["income_date"])
    record["date"] = str(record["income_date"])
    record["category"] = record["source"]
    record["created_at"] = str(record.get("created_at") or "")
    record["updated_at"] = str(record.get("updated_at") or "")

    return jsonify({"success": True, "income": record}), 200


@income_bp.put("/<int:income_id>")
@login_required
def update_income(income_id: int):
    """
    Updates an existing income record.
    Strictly verifies ownership; rejects cross-user modification attempts.
    """
    user_id = session.get("user_id")

    existing = DB.get_one(
        "SELECT id, user_id, amount, source, description, income_date FROM income WHERE id = %s",
        (income_id,)
    )

    if not existing:
        return jsonify({"success": False, "message": "Income record not found."}), 404

    # IDOR protection: verify ownership
    if existing["user_id"] != user_id:
        return jsonify({"success": False, "message": "Access denied. You do not own this income record."}), 403

    payload = request.get_json(silent=True) or {}
    cleaned, err = _validate_income_payload(payload, is_update=True)
    if err:
        return jsonify({"success": False, "message": err}), 400

    new_amount = cleaned.get("amount", float(existing["amount"]))
    new_source = cleaned.get("source", existing["source"])
    new_description = cleaned.get("description", existing["description"])
    new_date = cleaned.get("income_date", str(existing["income_date"]))

    try:
        DB.execute(
            """
            UPDATE income
            SET amount = %s, source = %s, description = %s, income_date = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND user_id = %s
            """,
            (new_amount, new_source, new_description, new_date, income_id, user_id)
        )

        updated = DB.get_one(
            """
            SELECT id, user_id, amount, source, description, income_date, created_at, updated_at
            FROM income
            WHERE id = %s
            """,
            (income_id,)
        )

        if updated:
            updated["amount"] = float(updated["amount"])
            updated["income_date"] = str(updated["income_date"])
            updated["date"] = str(updated["income_date"])
            updated["category"] = updated["source"]
            updated["created_at"] = str(updated.get("created_at") or "")
            updated["updated_at"] = str(updated.get("updated_at") or "")

        return jsonify({
            "success": True,
            "message": "Income record updated successfully.",
            "income": updated
        }), 200

    except Exception as e:
        logger.exception("Failed to update income %s: %s", income_id, e)
        return jsonify({"success": False, "message": "Failed to update income record."}), 500


@income_bp.delete("/<int:income_id>")
@login_required
def delete_income(income_id: int):
    """
    Deletes an existing income record.
    Strictly verifies ownership; rejects cross-user deletion attempts.
    """
    user_id = session.get("user_id")

    existing = DB.get_one(
        "SELECT id, user_id FROM income WHERE id = %s",
        (income_id,)
    )

    if not existing:
        return jsonify({"success": False, "message": "Income record not found."}), 404

    # IDOR protection: verify ownership
    if existing["user_id"] != user_id:
        return jsonify({"success": False, "message": "Access denied. You do not own this income record."}), 403

    try:
        DB.execute(
            "DELETE FROM income WHERE id = %s AND user_id = %s",
            (income_id, user_id)
        )

        return jsonify({
            "success": True,
            "message": "Income record deleted successfully."
        }), 200

    except Exception as e:
        logger.exception("Failed to delete income %s: %s", income_id, e)
        return jsonify({"success": False, "message": "Failed to delete income record."}), 500
