"""
Authenticated Budget Management Routes for College Food Court Application.

Enforces:
1. Session-derived user ownership (user_id strictly extracted from session).
2. Complete CRUD operations:
   - POST /api/budgets (create)
   - GET /api/budgets (list user's budgets)
   - GET /api/budgets/<id> (retrieve single budget)
   - PUT /api/budgets/<id> (update budget)
   - DELETE /api/budgets/<id> (delete budget)
3. Validation on limit amounts (> 0), categories, and dates.
4. Multi-tenant IDOR protection: prevents reading, updating, or deleting another user's budgets.
"""

import re
import logging
from datetime import datetime
from flask import Blueprint, jsonify, request, session
from db import DB
from routes.auth import login_required

logger = logging.getLogger("food_court.budgets")
budgets_bp = Blueprint("budgets", __name__)


def _validate_budget_payload(data: dict, is_update: bool = False):
    """
    Validates input fields for creating or updating a budget.
    Returns (cleaned_data, error_message).
    """
    if not isinstance(data, dict):
        return None, "Request body must be a JSON object."

    cleaned = {}

    # Validate amount limit
    raw_amount = None
    for k in ("amount_limit", "amount", "limit"):
        if k in data and data[k] is not None:
            raw_amount = data[k]
            break

    if raw_amount is None and not is_update:
        return None, "Budget limit amount is required."

    if raw_amount is not None:
        try:
            amount = float(raw_amount)
            if amount <= 0:
                return None, "Budget limit must be a positive number greater than 0."
            if amount > 1000000:
                return None, "Budget limit exceeds maximum limit of 1,000,000."
            cleaned["amount_limit"] = round(amount, 2)
        except (ValueError, TypeError):
            return None, "Budget limit must be a valid numeric value."

    # Validate category
    if "category" not in data and not is_update:
        return None, "Budget category is required."

    if "category" in data:
        cat = str(data.get("category") or "").strip()
        if not cat:
            return None, "Budget category cannot be empty."
        if len(cat) > 100:
            return None, "Category must not exceed 100 characters."
        cleaned["category"] = cat

    # Validate period
    period = data.get("period", "monthly")
    if period is not None:
        period_str = str(period).strip()
        if not period_str:
            period_str = "monthly"
        allowed_periods = {"weekly", "monthly", "yearly"}
        if period_str.lower() not in allowed_periods:
            return None, "Food budget period must be weekly, monthly, or yearly."
        cleaned["period"] = period_str.lower()

    # Optional start_date and end_date
    for field in ["start_date", "end_date"]:
        val = data.get(field)
        if val is not None and str(val).strip():
            date_str = str(val).strip()
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
                return None, f"{field.replace('_', ' ').capitalize()} must be in YYYY-MM-DD format."
            try:
                datetime.strptime(date_str, "%Y-%m-%d").date()
                cleaned[field] = date_str
            except ValueError:
                return None, f"{field.replace('_', ' ').capitalize()} must be a valid calendar date."
        else:
            cleaned[field] = None

    return cleaned, None


@budgets_bp.post("")
@login_required
def create_budget():
    """
    Creates a new budget record.
    Owner user_id is strictly derived from the authenticated session.
    Any client-supplied userId is ignored.
    """
    user_id = session.get("user_id")

    payload = request.get_json(silent=True) or {}
    cleaned, err = _validate_budget_payload(payload, is_update=False)
    if err:
        return jsonify({"success": False, "message": err}), 400

    try:
        new_id = DB.execute(
            """
            INSERT INTO budgets (user_id, category, amount_limit, period, start_date, end_date)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                cleaned["category"],
                cleaned["amount_limit"],
                cleaned.get("period", "monthly"),
                cleaned.get("start_date"),
                cleaned.get("end_date")
            )
        )

        record = DB.get_one(
            """
            SELECT id, user_id, category, amount_limit, period, start_date, end_date, created_at, updated_at
            FROM budgets
            WHERE id = %s
            """,
            (new_id,)
        )

        if record:
            record["amount_limit"] = float(record["amount_limit"])
            record["amount"] = record["amount_limit"]
            record["created_at"] = str(record.get("created_at") or "")
            record["updated_at"] = str(record.get("updated_at") or "")

        return jsonify({
            "success": True,
            "message": "Budget created successfully.",
            "budget": record
        }), 201

    except Exception as e:
        logger.exception("Failed to create budget for user %s: %s", user_id, e)
        return jsonify({"success": False, "message": "Failed to create budget."}), 500


@budgets_bp.get("")
@login_required
def get_budgets():
    """
    Retrieves all budgets belonging to the authenticated user.
    Never exposes other users' records.
    """
    user_id = session.get("user_id")

    try:
        rows = DB.get_all(
            """
            SELECT id, user_id, category, amount_limit, period, start_date, end_date, created_at, updated_at
            FROM budgets
            WHERE user_id = %s
            ORDER BY id DESC
            """,
            (user_id,)
        )

        budgets = []
        total_limit = 0.0
        for r in rows:
            limit = float(r.get("amount_limit") or 0.0)
            total_limit += limit
            budgets.append({
                "id": r["id"],
                "user_id": r["user_id"],
                "category": r["category"],
                "amount_limit": limit,
                "amount": limit,
                "period": r["period"],
                "start_date": str(r["start_date"]) if r["start_date"] else None,
                "end_date": str(r["end_date"]) if r["end_date"] else None,
                "created_at": str(r.get("created_at") or ""),
                "updated_at": str(r.get("updated_at") or "")
            })

        return jsonify({
            "success": True,
            "budgets": budgets,
            "count": len(budgets),
            "total_limit": round(total_limit, 2)
        }), 200

    except Exception as e:
        logger.exception("Failed to fetch budgets for user %s: %s", user_id, e)
        return jsonify({"success": False, "message": "Failed to retrieve budgets."}), 500


@budgets_bp.get("/<int:budget_id>")
@login_required
def get_single_budget(budget_id: int):
    """
    Retrieves a single budget by ID.
    Strictly verifies ownership; returns 403/404 if not found or owned by someone else.
    """
    user_id = session.get("user_id")

    record = DB.get_one(
        """
        SELECT id, user_id, category, amount_limit, period, start_date, end_date, created_at, updated_at
        FROM budgets
        WHERE id = %s
        """,
        (budget_id,)
    )

    if not record:
        return jsonify({"success": False, "message": "Budget not found."}), 404

    if record["user_id"] != user_id:
        return jsonify({"success": False, "message": "Access denied. You do not own this budget."}), 403

    record["amount_limit"] = float(record["amount_limit"])
    record["amount"] = record["amount_limit"]
    record["created_at"] = str(record.get("created_at") or "")
    record["updated_at"] = str(record.get("updated_at") or "")

    return jsonify({"success": True, "budget": record}), 200


@budgets_bp.put("/<int:budget_id>")
@login_required
def update_budget(budget_id: int):
    """
    Updates an existing budget record.
    Strictly verifies ownership; rejects cross-user modification attempts.
    """
    user_id = session.get("user_id")

    existing = DB.get_one(
        "SELECT id, user_id, category, amount_limit, period, start_date, end_date FROM budgets WHERE id = %s",
        (budget_id,)
    )

    if not existing:
        return jsonify({"success": False, "message": "Budget not found."}), 404

    if existing["user_id"] != user_id:
        return jsonify({"success": False, "message": "Access denied. You do not own this budget."}), 403

    payload = request.get_json(silent=True) or {}
    cleaned, err = _validate_budget_payload(payload, is_update=True)
    if err:
        return jsonify({"success": False, "message": err}), 400

    new_limit = cleaned.get("amount_limit", float(existing["amount_limit"]))
    new_cat = cleaned.get("category", existing["category"])
    new_period = cleaned.get("period", existing["period"])
    new_start = cleaned.get("start_date", existing["start_date"])
    new_end = cleaned.get("end_date", existing["end_date"])

    try:
        DB.execute(
            """
            UPDATE budgets
            SET category = %s, amount_limit = %s, period = %s, start_date = %s, end_date = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND user_id = %s
            """,
            (new_cat, new_limit, new_period, new_start, new_end, budget_id, user_id)
        )

        updated = DB.get_one(
            """
            SELECT id, user_id, category, amount_limit, period, start_date, end_date, created_at, updated_at
            FROM budgets
            WHERE id = %s
            """,
            (budget_id,)
        )

        if updated:
            updated["amount_limit"] = float(updated["amount_limit"])
            updated["amount"] = updated["amount_limit"]
            updated["created_at"] = str(updated.get("created_at") or "")
            updated["updated_at"] = str(updated.get("updated_at") or "")

        return jsonify({
            "success": True,
            "message": "Budget updated successfully.",
            "budget": updated
        }), 200

    except Exception as e:
        logger.exception("Failed to update budget %s: %s", budget_id, e)
        return jsonify({"success": False, "message": "Failed to update budget."}), 500


@budgets_bp.delete("/<int:budget_id>")
@login_required
def delete_budget(budget_id: int):
    """
    Deletes an existing budget record.
    Strictly verifies ownership; rejects cross-user deletion attempts.
    """
    user_id = session.get("user_id")

    existing = DB.get_one(
        "SELECT id, user_id FROM budgets WHERE id = %s",
        (budget_id,)
    )

    if not existing:
        return jsonify({"success": False, "message": "Budget not found."}), 404

    if existing["user_id"] != user_id:
        return jsonify({"success": False, "message": "Access denied. You do not own this budget."}), 403

    try:
        DB.execute(
            "DELETE FROM budgets WHERE id = %s AND user_id = %s",
            (budget_id, user_id)
        )

        return jsonify({
            "success": True,
            "message": "Budget deleted successfully."
        }), 200

    except Exception as e:
        logger.exception("Failed to delete budget %s: %s", budget_id, e)
        return jsonify({"success": False, "message": "Failed to delete budget."}), 500
