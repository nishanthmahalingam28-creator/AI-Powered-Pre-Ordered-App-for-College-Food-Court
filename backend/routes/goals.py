"""
Authenticated Financial Goals Management Routes for College Food Court Application.

Enforces:
1. Session-derived user ownership (user_id strictly extracted from session).
2. Complete CRUD operations:
   - POST /api/goals (create)
   - GET /api/goals (list user's goals)
   - GET /api/goals/<id> (retrieve single goal)
   - PUT /api/goals/<id> (update goal)
   - DELETE /api/goals/<id> (delete goal)
3. Validation on target amounts (> 0), current amounts (>= 0), titles, and dates.
4. Multi-tenant IDOR protection: prevents reading, updating, or deleting another user's goals.
"""

import re
import logging
from datetime import datetime
from flask import Blueprint, jsonify, request, session
from db import DB
from routes.auth import login_required

logger = logging.getLogger("food_court.goals")
goals_bp = Blueprint("goals", __name__)


def _validate_goal_payload(data: dict, is_update: bool = False):
    """
    Validates input fields for creating or updating a financial goal.
    Returns (cleaned_data, error_message).
    """
    if not isinstance(data, dict):
        return None, "Request body must be a JSON object."

    cleaned = {}

    # Validate title / name
    title_val = data.get("title") or data.get("name")
    if not title_val and not is_update:
        return None, "Goal title is required."

    if title_val is not None:
        title = str(title_val).strip()
        if not title:
            return None, "Goal title cannot be empty."
        if len(title) > 150:
            return None, "Goal title must not exceed 150 characters."
        cleaned["title"] = title

    # Validate target amount
    raw_target = None
    for k in ("target_amount", "target"):
        if k in data and data[k] is not None:
            raw_target = data[k]
            break

    if raw_target is None and not is_update:
        return None, "Target amount is required."

    if raw_target is not None:
        try:
            target = float(raw_target)
            if target <= 0:
                return None, "Target amount must be a positive number greater than 0."
            if target > 10000000:
                return None, "Target amount exceeds maximum limit of 10,000,000."
            cleaned["target_amount"] = round(target, 2)
        except (ValueError, TypeError):
            return None, "Target amount must be a valid numeric value."

    # Validate current amount
    raw_current = data.get("current_amount")
    if raw_current is None:
        raw_current = data.get("saved")
    if raw_current is None and not is_update:
        cleaned["current_amount"] = 0.00
    elif raw_current is not None:
        try:
            current = float(raw_current)
            if current < 0:
                return None, "Current amount cannot be negative."
            cleaned["current_amount"] = round(current, 2)
        except (ValueError, TypeError):
            return None, "Current amount must be a valid numeric value."

    # Validate target date (optional)
    raw_date = data.get("target_date") or data.get("date")
    if raw_date is not None and str(raw_date).strip():
        date_str = str(raw_date).strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            return None, "Target date must be in YYYY-MM-DD format."
        try:
            datetime.strptime(date_str, "%Y-%m-%d").date()
            cleaned["target_date"] = date_str
        except ValueError:
            return None, "Target date must be a valid calendar date."
    else:
        cleaned["target_date"] = None

    # Validate category (optional)
    if "category" in data:
        cat = str(data.get("category") or "").strip()
        cleaned["category"] = cat if cat else "Dining"

    # Validate status (optional)
    if "status" in data:
        st = str(data.get("status") or "").strip().lower()
        if st in ("in_progress", "achieved", "cancelled"):
            cleaned["status"] = st
        else:
            cleaned["status"] = "in_progress"

    return cleaned, None


@goals_bp.post("")
@login_required
def create_goal():
    """
    Creates a new financial goal.
    Owner user_id is strictly derived from the authenticated session.
    Any client-supplied userId is ignored.
    """
    user_id = session.get("user_id")

    payload = request.get_json(silent=True) or {}
    cleaned, err = _validate_goal_payload(payload, is_update=False)
    if err:
        return jsonify({"success": False, "message": err}), 400

    try:
        new_id = DB.execute(
            """
            INSERT INTO financial_goals (user_id, title, target_amount, current_amount, target_date, category, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                cleaned["title"],
                cleaned["target_amount"],
                cleaned.get("current_amount", 0.00),
                cleaned.get("target_date"),
                cleaned.get("category", "Dining"),
                cleaned.get("status", "in_progress")
            )
        )

        record = DB.get_one(
            """
            SELECT id, user_id, title, target_amount, current_amount, target_date, category, status, created_at, updated_at
            FROM financial_goals
            WHERE id = %s
            """,
            (new_id,)
        )

        if record:
            record["target_amount"] = float(record["target_amount"])
            record["current_amount"] = float(record["current_amount"])
            record["progress_percent"] = round((record["current_amount"] / record["target_amount"] * 100), 1) if record["target_amount"] > 0 else 0
            record["created_at"] = str(record.get("created_at") or "")
            record["updated_at"] = str(record.get("updated_at") or "")

        return jsonify({
            "success": True,
            "message": "Financial goal created successfully.",
            "goal": record
        }), 201

    except Exception as e:
        logger.exception("Failed to create goal for user %s: %s", user_id, e)
        return jsonify({"success": False, "message": "Failed to create financial goal."}), 500


@goals_bp.get("")
@login_required
def get_goals():
    """
    Retrieves all financial goals belonging to the authenticated user.
    Never exposes other users' records.
    """
    user_id = session.get("user_id")

    try:
        rows = DB.get_all(
            """
            SELECT id, user_id, title, target_amount, current_amount, target_date, category, status, created_at, updated_at
            FROM financial_goals
            WHERE user_id = %s
            ORDER BY id DESC
            """,
            (user_id,)
        )

        goals = []
        total_target = 0.0
        total_saved = 0.0
        for r in rows:
            target = float(r.get("target_amount") or 0.0)
            saved = float(r.get("current_amount") or 0.0)
            total_target += target
            total_saved += saved
            pct = round((saved / target * 100), 1) if target > 0 else 0
            goals.append({
                "id": r["id"],
                "user_id": r["user_id"],
                "title": r["title"],
                "name": r["title"],
                "target_amount": target,
                "current_amount": saved,
                "progress_percent": pct,
                "target_date": str(r["target_date"]) if r["target_date"] else None,
                "category": r["category"],
                "status": r["status"],
                "created_at": str(r.get("created_at") or ""),
                "updated_at": str(r.get("updated_at") or "")
            })

        return jsonify({
            "success": True,
            "goals": goals,
            "count": len(goals),
            "total_target": round(total_target, 2),
            "total_saved": round(total_saved, 2)
        }), 200

    except Exception as e:
        logger.exception("Failed to fetch goals for user %s: %s", user_id, e)
        return jsonify({"success": False, "message": "Failed to retrieve goals."}), 500


@goals_bp.get("/<int:goal_id>")
@login_required
def get_single_goal(goal_id: int):
    """
    Retrieves a single financial goal by ID.
    Strictly verifies ownership; returns 403/404 if not found or owned by someone else.
    """
    user_id = session.get("user_id")

    record = DB.get_one(
        """
        SELECT id, user_id, title, target_amount, current_amount, target_date, category, status, created_at, updated_at
        FROM financial_goals
        WHERE id = %s
        """,
        (goal_id,)
    )

    if not record:
        return jsonify({"success": False, "message": "Goal not found."}), 404

    if record["user_id"] != user_id:
        return jsonify({"success": False, "message": "Access denied. You do not own this financial goal."}), 403

    record["target_amount"] = float(record["target_amount"])
    record["current_amount"] = float(record["current_amount"])
    record["progress_percent"] = round((record["current_amount"] / record["target_amount"] * 100), 1) if record["target_amount"] > 0 else 0
    record["created_at"] = str(record.get("created_at") or "")
    record["updated_at"] = str(record.get("updated_at") or "")

    return jsonify({"success": True, "goal": record}), 200


@goals_bp.put("/<int:goal_id>")
@login_required
def update_goal(goal_id: int):
    """
    Updates an existing financial goal.
    Strictly verifies ownership; rejects cross-user modification attempts.
    """
    user_id = session.get("user_id")

    existing = DB.get_one(
        "SELECT id, user_id, title, target_amount, current_amount, target_date, category, status FROM financial_goals WHERE id = %s",
        (goal_id,)
    )

    if not existing:
        return jsonify({"success": False, "message": "Goal not found."}), 404

    if existing["user_id"] != user_id:
        return jsonify({"success": False, "message": "Access denied. You do not own this financial goal."}), 403

    payload = request.get_json(silent=True) or {}
    cleaned, err = _validate_goal_payload(payload, is_update=True)
    if err:
        return jsonify({"success": False, "message": err}), 400

    new_title = cleaned.get("title", existing["title"])
    new_target = cleaned.get("target_amount", float(existing["target_amount"]))
    new_current = cleaned.get("current_amount", float(existing["current_amount"]))
    new_date = cleaned.get("target_date", existing["target_date"])
    new_category = cleaned.get("category", existing["category"])
    new_status = cleaned.get("status", existing["status"])

    # Auto-update status to achieved if current >= target
    if new_current >= new_target and new_status == "in_progress":
        new_status = "achieved"

    try:
        DB.execute(
            """
            UPDATE financial_goals
            SET title = %s, target_amount = %s, current_amount = %s, target_date = %s,
                category = %s, status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND user_id = %s
            """,
            (new_title, new_target, new_current, new_date, new_category, new_status, goal_id, user_id)
        )

        updated = DB.get_one(
            """
            SELECT id, user_id, title, target_amount, current_amount, target_date, category, status, created_at, updated_at
            FROM financial_goals
            WHERE id = %s
            """,
            (goal_id,)
        )

        if updated:
            updated["target_amount"] = float(updated["target_amount"])
            updated["current_amount"] = float(updated["current_amount"])
            updated["progress_percent"] = round((updated["current_amount"] / updated["target_amount"] * 100), 1) if updated["target_amount"] > 0 else 0
            updated["created_at"] = str(updated.get("created_at") or "")
            updated["updated_at"] = str(updated.get("updated_at") or "")

        return jsonify({
            "success": True,
            "message": "Goal updated successfully.",
            "goal": updated
        }), 200

    except Exception as e:
        logger.exception("Failed to update goal %s: %s", goal_id, e)
        return jsonify({"success": False, "message": "Failed to update financial goal."}), 500


@goals_bp.delete("/<int:goal_id>")
@login_required
def delete_goal(goal_id: int):
    """
    Deletes an existing financial goal.
    Strictly verifies ownership; rejects cross-user deletion attempts.
    """
    user_id = session.get("user_id")

    existing = DB.get_one(
        "SELECT id, user_id FROM financial_goals WHERE id = %s",
        (goal_id,)
    )

    if not existing:
        return jsonify({"success": False, "message": "Goal not found."}), 404

    if existing["user_id"] != user_id:
        return jsonify({"success": False, "message": "Access denied. You do not own this financial goal."}), 403

    try:
        DB.execute(
            "DELETE FROM financial_goals WHERE id = %s AND user_id = %s",
            (goal_id, user_id)
        )

        return jsonify({
            "success": True,
            "message": "Goal deleted successfully."
        }), 200

    except Exception as e:
        logger.exception("Failed to delete goal %s: %s", goal_id, e)
        return jsonify({"success": False, "message": "Failed to delete financial goal."}), 500
