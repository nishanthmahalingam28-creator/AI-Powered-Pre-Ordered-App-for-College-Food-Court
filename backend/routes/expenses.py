"""
Authenticated Expense Management Routes for College Food Court Application.

Enforces:
1. Session-derived user ownership (user_id strictly extracted from session, ignoring client payload).
2. Complete CRUD operations:
   - POST /api/expenses (create)
   - GET /api/expenses (list current user's expenses)
   - GET /api/expenses/<id> (retrieve single expense)
   - PUT /api/expenses/<id> (update expense)
   - DELETE /api/expenses/<id> (delete expense)
3. Strict validation on amount (> 0), date (YYYY-MM-DD format), category, and description.
4. Strict IDOR protection: prevents reading, updating, or deleting another user's expenses.
"""

import re
import logging
from datetime import datetime
from flask import Blueprint, jsonify, request, session
from db import DB
from routes.auth import login_required

logger = logging.getLogger("food_court.expenses")
expenses_bp = Blueprint("expenses", __name__)


def _validate_expense_payload(data: dict, is_update: bool = False):
    """
    Validates input fields for creating or updating an expense.
    Returns (cleaned_data, error_message).
    """
    if not isinstance(data, dict):
        return None, "Request body must be a JSON object."

    # Validate amount
    if "amount" not in data and not is_update:
        return None, "Amount is required."
    
    cleaned = {}

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
    date_val = data.get("date") or data.get("expense_date")
    if not date_val and not is_update:
        return None, "Date is required."
    
    if date_val is not None:
        date_str = str(date_val).strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            return None, "Date must be in YYYY-MM-DD format."
        try:
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            cleaned["expense_date"] = parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            return None, "Date must be a valid calendar date."

    # Validate category
    if "category" not in data and not is_update:
        return None, "Category is required."

    if "category" in data:
        category = str(data.get("category") or "").strip()
        if not category:
            return None, "Category cannot be empty."
        if len(category) > 100:
            return None, "Category must not exceed 100 characters."
        cleaned["category"] = category

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


@expenses_bp.post("")
@login_required
def create_expense():
    """
    Creates a new expense record.
    Owner user_id is strictly derived from the authenticated session.
    Any client-provided userId is strictly ignored.
    """
    # 1. Derive user_id strictly from session
    user_id = session.get("user_id")

    payload = request.get_json(silent=True) or {}
    
    # 2. Validate payload
    cleaned, err = _validate_expense_payload(payload, is_update=False)
    if err:
        return jsonify({"success": False, "message": err}), 400

    # 3. Insert into database
    try:
        new_id = DB.execute(
            """
            INSERT INTO expenses (user_id, amount, category, description, expense_date)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                user_id,
                cleaned["amount"],
                cleaned["category"],
                cleaned["description"],
                cleaned["expense_date"]
            )
        )

        expense = DB.get_one(
            """
            SELECT id, user_id, amount, category, description, expense_date, created_at, updated_at
            FROM expenses
            WHERE id = %s
            """,
            (new_id,)
        )

        if expense:
            expense["amount"] = float(expense["amount"])
            expense["expense_date"] = str(expense["expense_date"])
            expense["date"] = str(expense["expense_date"])
            expense["created_at"] = str(expense.get("created_at") or "")
            expense["updated_at"] = str(expense.get("updated_at") or "")

        return jsonify({
            "success": True,
            "message": "Expense recorded successfully.",
            "expense": expense
        }), 201

    except Exception as e:
        logger.exception("Failed to create expense for user %s: %s", user_id, e)
        return jsonify({"success": False, "message": "Failed to record expense. Please try again."}), 500


@expenses_bp.get("")
@login_required
def get_expenses():
    """
    Retrieves all expenses belonging to the authenticated user.
    Never exposes other users' records.
    """
    user_id = session.get("user_id")

    try:
        rows = DB.get_all(
            """
            SELECT id, user_id, amount, category, description, expense_date, created_at, updated_at
            FROM expenses
            WHERE user_id = %s
            ORDER BY expense_date DESC, id DESC
            """,
            (user_id,)
        )

        expenses = []
        total_amount = 0.0
        for r in rows:
            amt = float(r.get("amount") or 0.0)
            total_amount += amt
            expenses.append({
                "id": r["id"],
                "user_id": r["user_id"],
                "amount": amt,
                "category": r["category"],
                "description": r["description"],
                "expense_date": str(r["expense_date"]),
                "date": str(r["expense_date"]),
                "created_at": str(r.get("created_at") or ""),
                "updated_at": str(r.get("updated_at") or "")
            })

        return jsonify({
            "success": True,
            "expenses": expenses,
            "count": len(expenses),
            "total_amount": round(total_amount, 2)
        }), 200

    except Exception as e:
        logger.exception("Failed to fetch expenses for user %s: %s", user_id, e)
        return jsonify({"success": False, "message": "Failed to retrieve expenses."}), 500


@expenses_bp.get("/<int:expense_id>")
@login_required
def get_single_expense(expense_id: int):
    """
    Retrieves a single expense by ID.
    Strictly verifies ownership; returns 404 if not found or owned by someone else.
    """
    user_id = session.get("user_id")

    expense = DB.get_one(
        """
        SELECT id, user_id, amount, category, description, expense_date, created_at, updated_at
        FROM expenses
        WHERE id = %s
        """,
        (expense_id,)
    )

    if not expense:
        return jsonify({"success": False, "message": "Expense not found."}), 404

    # IDOR protection: if user is not the owner, return 403 Forbidden
    if expense["user_id"] != user_id:
        return jsonify({"success": False, "message": "Access denied. You do not own this expense."}), 403

    expense["amount"] = float(expense["amount"])
    expense["expense_date"] = str(expense["expense_date"])
    expense["date"] = str(expense["expense_date"])
    expense["created_at"] = str(expense.get("created_at") or "")
    expense["updated_at"] = str(expense.get("updated_at") or "")

    return jsonify({"success": True, "expense": expense}), 200


@expenses_bp.put("/<int:expense_id>")
@login_required
def update_expense(expense_id: int):
    """
    Updates an existing expense record.
    Strictly verifies ownership; rejects cross-user modification attempts.
    """
    user_id = session.get("user_id")

    existing = DB.get_one(
        "SELECT id, user_id, amount, category, description, expense_date FROM expenses WHERE id = %s",
        (expense_id,)
    )

    if not existing:
        return jsonify({"success": False, "message": "Expense not found."}), 404

    # IDOR protection: verify ownership
    if existing["user_id"] != user_id:
        return jsonify({"success": False, "message": "Access denied. You do not own this expense."}), 403

    payload = request.get_json(silent=True) or {}
    cleaned, err = _validate_expense_payload(payload, is_update=True)
    if err:
        return jsonify({"success": False, "message": err}), 400

    new_amount = cleaned.get("amount", float(existing["amount"]))
    new_category = cleaned.get("category", existing["category"])
    new_description = cleaned.get("description", existing["description"])
    new_date = cleaned.get("expense_date", str(existing["expense_date"]))

    try:
        DB.execute(
            """
            UPDATE expenses
            SET amount = %s, category = %s, description = %s, expense_date = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND user_id = %s
            """,
            (new_amount, new_category, new_description, new_date, expense_id, user_id)
        )

        updated = DB.get_one(
            """
            SELECT id, user_id, amount, category, description, expense_date, created_at, updated_at
            FROM expenses
            WHERE id = %s
            """,
            (expense_id,)
        )

        if updated:
            updated["amount"] = float(updated["amount"])
            updated["expense_date"] = str(updated["expense_date"])
            updated["date"] = str(updated["expense_date"])
            updated["created_at"] = str(updated.get("created_at") or "")
            updated["updated_at"] = str(updated.get("updated_at") or "")

        return jsonify({
            "success": True,
            "message": "Expense updated successfully.",
            "expense": updated
        }), 200

    except Exception as e:
        logger.exception("Failed to update expense %s: %s", expense_id, e)
        return jsonify({"success": False, "message": "Failed to update expense."}), 500


@expenses_bp.delete("/<int:expense_id>")
@login_required
def delete_expense(expense_id: int):
    """
    Deletes an existing expense record.
    Strictly verifies ownership; rejects cross-user deletion attempts.
    """
    user_id = session.get("user_id")

    existing = DB.get_one(
        "SELECT id, user_id FROM expenses WHERE id = %s",
        (expense_id,)
    )

    if not existing:
        return jsonify({"success": False, "message": "Expense not found."}), 404

    # IDOR protection: verify ownership
    if existing["user_id"] != user_id:
        return jsonify({"success": False, "message": "Access denied. You do not own this expense."}), 403

    try:
        DB.execute(
            "DELETE FROM expenses WHERE id = %s AND user_id = %s",
            (expense_id, user_id)
        )

        return jsonify({
            "success": True,
            "message": "Expense deleted successfully."
        }), 200

    except Exception as e:
        logger.exception("Failed to delete expense %s: %s", expense_id, e)
        return jsonify({"success": False, "message": "Failed to delete expense."}), 500
