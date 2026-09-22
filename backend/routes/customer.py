import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo
from flask import Blueprint, jsonify, request, session
from security import hash_password, verify_password
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
        "roll_number": profile.get("identifier") or "",
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
    if not user or not verify_password(current_password, user["password_hash"]):
        return jsonify({"success": False, "message": "Current password is incorrect."}), 400
    new_hash = hash_password(new_password)
    DB.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, user_id))
    logger.info("Customer password updated successfully for user_id=%s", user_id)
    return jsonify({
        "success": True,
        "message": "Password updated successfully."
    }), 200
def _compute_customer_analytics_payload(user_id: int, tx_limit: int = 10):
    """
    Core aggregator for customer financial intelligence and visual analytics.
    Calculates income, expenses, categories, monthly trends, budget comparisons,
    and savings progress strictly for the authenticated user from the database.
    """
    # 1. Total Income & Statistical aggregates
    inc_stats = DB.get_one(
        """
        SELECT COALESCE(SUM(amount), 0) AS total,
               COUNT(id) AS count,
               COALESCE(AVG(amount), 0) AS avg_amount,
               COALESCE(MAX(amount), 0) AS max_amount
        FROM income
        WHERE user_id = %s
        """,
        (user_id,)
    ) or {}
    total_income = float(inc_stats.get("total") or 0.0)
    income_count = int(inc_stats.get("count") or 0)
    avg_income = float(inc_stats.get("avg_amount") or 0.0)
    max_income = float(inc_stats.get("max_amount") or 0.0)
    # 2. Total Expenses & Statistical aggregates
    exp_stats = DB.get_one(
        """
        SELECT COALESCE(SUM(amount), 0) AS total,
               COUNT(id) AS count,
               COALESCE(AVG(amount), 0) AS avg_amount,
               COALESCE(MAX(amount), 0) AS max_amount
        FROM expenses
        WHERE user_id = %s
        """,
        (user_id,)
    ) or {}
    total_expenses = float(exp_stats.get("total") or 0.0)
    expense_count = int(exp_stats.get("count") or 0)
    avg_expense = float(exp_stats.get("avg_amount") or 0.0)
    max_expense = float(exp_stats.get("max_amount") or 0.0)
    # Net balance & Savings Rate
    net_balance = round(total_income - total_expenses, 2)
    savings_rate = round((net_balance / total_income * 100), 1) if total_income > 0 else 0.0
    # 3. Wallet Balance
    prof_row = DB.get_one(
        "SELECT wallet_balance FROM customer_profiles WHERE user_id = %s LIMIT 1",
        (user_id,)
    )
    wallet_balance = float(prof_row.get("wallet_balance") or 0.0) if prof_row else 0.0
    # 4. Category Expense Breakdown
    cat_rows = DB.get_all(
        """
        SELECT category, COALESCE(SUM(amount), 0) AS total, COUNT(id) AS count
        FROM expenses
        WHERE user_id = %s
        GROUP BY category
        ORDER BY total DESC
        """,
        (user_id,)
    )
    category_breakdown_expenses = []
    for cr in cat_rows:
        cat_tot = round(float(cr["total"] or 0.0), 2)
        pct = round((cat_tot / total_expenses * 100), 1) if total_expenses > 0 else 0.0
        category_breakdown_expenses.append({
            "category": cr["category"] or "Other",
            "amount": cat_tot,
            "count": int(cr.get("count") or 0),
            "percentage": pct
        })
    # 5. Income Sources Breakdown
    inc_cat_rows = DB.get_all(
        """
        SELECT source, COALESCE(SUM(amount), 0) AS total, COUNT(id) AS count
        FROM income
        WHERE user_id = %s
        GROUP BY source
        ORDER BY total DESC
        """,
        (user_id,)
    )
    category_breakdown_income = []
    for ir in inc_cat_rows:
        src_tot = round(float(ir["total"] or 0.0), 2)
        pct = round((src_tot / total_income * 100), 1) if total_income > 0 else 0.0
        category_breakdown_income.append({
            "source": ir["source"] or "Other",
            "category": ir["source"] or "Other",
            "amount": src_tot,
            "count": int(ir.get("count") or 0),
            "percentage": pct
        })
    # 6. Monthly Trends (SQLite & MySQL compatible via SUBSTR)
    exp_monthly_rows = DB.get_all(
        """
        SELECT SUBSTR(expense_date, 1, 7) AS ym, COALESCE(SUM(amount), 0) AS total, COUNT(id) AS count
        FROM expenses
        WHERE user_id = %s AND expense_date IS NOT NULL
        GROUP BY SUBSTR(expense_date, 1, 7)
        ORDER BY ym ASC
        """,
        (user_id,)
    )
    monthly_exp_map = {
        r["ym"]: {"total": round(float(r["total"] or 0.0), 2), "count": int(r.get("count") or 0)}
        for r in exp_monthly_rows if r.get("ym")
    }
    inc_monthly_rows = DB.get_all(
        """
        SELECT SUBSTR(income_date, 1, 7) AS ym, COALESCE(SUM(amount), 0) AS total, COUNT(id) AS count
        FROM income
        WHERE user_id = %s AND income_date IS NOT NULL
        GROUP BY SUBSTR(income_date, 1, 7)
        ORDER BY ym ASC
        """,
        (user_id,)
    )
    monthly_inc_map = {
        r["ym"]: {"total": round(float(r["total"] or 0.0), 2), "count": int(r.get("count") or 0)}
        for r in inc_monthly_rows if r.get("ym")
    }
    all_months = sorted(set(list(monthly_exp_map.keys()) + list(monthly_inc_map.keys())))
    monthly_trends = []
    month_names = {
        "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr", "05": "May", "06": "Jun",
        "07": "Jul", "08": "Aug", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec"
    }
    for ym in all_months:
        m_inc = monthly_inc_map.get(ym, {}).get("total", 0.0)
        m_exp = monthly_exp_map.get(ym, {}).get("total", 0.0)
        m_net = round(m_inc - m_exp, 2)
        m_rate = round((m_net / m_inc * 100), 1) if m_inc > 0 else 0.0
        parts = ym.split("-")
        label = ym
        if len(parts) == 2 and parts[1] in month_names:
            label = f"{month_names[parts[1]]} {parts[0]}"
        monthly_trends.append({
            "month": ym,
            "label": label,
            "income": m_inc,
            "expenses": m_exp,
            "net_savings": m_net,
            "savings_rate": m_rate,
            "income_count": monthly_inc_map.get(ym, {}).get("count", 0),
            "expense_count": monthly_exp_map.get(ym, {}).get("count", 0)
        })
    # 7. Budgets and per-category spending
    budget_rows = DB.get_all(
        """
        SELECT id, category, amount_limit, period, start_date, end_date
        FROM budgets
        WHERE user_id = %s
        ORDER BY id DESC
        """,
        (user_id,)
    )
    total_budget_limit = 0.0
    budgets_data = []

    # Food Spent on the student dashboard must represent actual completed
    # food-order expenses, even when the student has not created a Food budget
    # row. Previously this value was only accumulated inside the budget loop,
    # which made Food Spent incorrectly show ₹0.00 when no matching budget
    # category existed.
    food_spent_row = DB.get_one(
        """
        SELECT COALESCE(SUM(amount), 0) AS food_spent
        FROM expenses
        WHERE user_id = %s
          AND LOWER(category) = 'food'
        """,
        (user_id,)
    ) or {}
    total_budget_spent = float(food_spent_row.get("food_spent") or 0.0)

    for b in budget_rows:
        limit_val = float(b.get("amount_limit") or 0.0)
        total_budget_limit += limit_val
        cat_name = b.get("category") or ""
        spent_row = DB.get_one(
            "SELECT COALESCE(SUM(amount), 0) AS cat_spent FROM expenses WHERE user_id = %s AND LOWER(category) = LOWER(%s)",
            (user_id, cat_name)
        )
        cat_spent = float(spent_row.get("cat_spent") or 0.0) if spent_row else 0.0
        pct_spent = round((cat_spent / limit_val * 100), 1) if limit_val > 0 else 0.0
        if pct_spent > 100:
            status = "exceeded"
        elif pct_spent >= 80:
            status = "near_limit"
        else:
            status = "on_track"
        budgets_data.append({
            "id": b["id"],
            "category": cat_name,
            "amount_limit": round(limit_val, 2),
            "spent": round(cat_spent, 2),
            "remaining": round(max(0.0, limit_val - cat_spent), 2),
            "percent_spent": pct_spent,
            "period": b.get("period", "monthly"),
            "start_date": str(b["start_date"]) if b.get("start_date") else None,
            "end_date": str(b["end_date"]) if b.get("end_date") else None,
            "status": status
        })
    budget_percent_spent = round((total_budget_spent / total_budget_limit * 100), 1) if total_budget_limit > 0 else 0.0
    # 8. Financial Goals & Savings Progress
    goal_rows = DB.get_all(
        """
        SELECT id, title, target_amount, current_amount, target_date, category, status
        FROM financial_goals
        WHERE user_id = %s
        ORDER BY id DESC
        """,
        (user_id,)
    )
    total_goals_target = 0.0
    total_goals_saved = 0.0
    goals_data = []
    for g in goal_rows:
        target_val = float(g.get("target_amount") or 0.0)
        saved_val = float(g.get("current_amount") or 0.0)
        total_goals_target += target_val
        total_goals_saved += saved_val
        pct = round((saved_val / target_val * 100), 1) if target_val > 0 else 0.0
        goals_data.append({
            "id": g["id"],
            "title": g.get("title") or "Savings Goal",
            "target_amount": round(target_val, 2),
            "current_amount": round(saved_val, 2),
            "remaining": round(max(0.0, target_val - saved_val), 2),
            "progress_percent": pct,
            "target_date": str(g["target_date"]) if g.get("target_date") else None,
            "category": g.get("category", "Dining"),
            "status": g.get("status", "in_progress")
        })
    goals_overall_progress = round((total_goals_saved / total_goals_target * 100), 1) if total_goals_target > 0 else 0.0
    # 9. Recent Transactions (Top 20)
    recent_expenses = DB.get_all(
        """
        SELECT id, amount, category, description, expense_date AS tx_date, created_at
        FROM expenses
        WHERE user_id = %s
        ORDER BY expense_date DESC, id DESC
        LIMIT 20
        """,
        (user_id,)
    )
    recent_income = DB.get_all(
        """
        SELECT id, amount, source AS category, description, income_date AS tx_date, created_at
        FROM income
        WHERE user_id = %s
        ORDER BY income_date DESC, id DESC
        LIMIT 20
        """,
        (user_id,)
    )
    unified_transactions = []
    for e in recent_expenses:
        unified_transactions.append({
            "id": e["id"],
            "type": "expense",
            "amount": round(float(e["amount"]), 2),
            "category": e.get("category") or "Dining",
            "description": e.get("description") or "Food Court Expense",
            "date": str(e.get("tx_date") or ""),
            "created_at": str(e.get("created_at") or "")
        })
    for i in recent_income:
        unified_transactions.append({
            "id": i["id"],
            "type": "income",
            "amount": round(float(i["amount"]), 2),
            "category": i.get("category") or "Stipend",
            "description": i.get("description") or "Received Income",
            "date": str(i.get("tx_date") or ""),
            "created_at": str(i.get("created_at") or "")
        })
    unified_transactions.sort(
        key=lambda x: (x["date"] or "", x["created_at"] or ""),
        reverse=True
    )
    capped_transactions = unified_transactions[:tx_limit]
    return {
        "success": True,
        "summary": {
            "total_income": round(total_income, 2),
            "total_expenses": round(total_expenses, 2),
            "net_balance": net_balance,
            "savings_rate": savings_rate,
            "wallet_balance": round(wallet_balance, 2),
            "average_income": round(avg_income, 2),
            "highest_income": round(max_income, 2),
            "average_expense": round(avg_expense, 2),
            "highest_expense": round(max_expense, 2),
            "total_budget": round(total_budget_limit, 2),
            "total_budget_spent": round(total_budget_spent, 2),
            "budget_percent_spent": budget_percent_spent,
            "total_goals_target": round(total_goals_target, 2),
            "total_goals_saved": round(total_goals_saved, 2),
            "goals_overall_progress": goals_overall_progress,
            "counts": {
                "income_entries": income_count,
                "expense_entries": expense_count,
                "active_budgets": len(budgets_data),
                "active_goals": len(goals_data)
            }
        },
        "category_breakdown": category_breakdown_expenses,
        "category_breakdown_income": category_breakdown_income,
        "monthly_trends": monthly_trends,
        "budget_comparisons": budgets_data,
        "budgets": budgets_data,
        "goals": goals_data,
        "recent_transactions": capped_transactions,
        "charts": {
            "cash_flow": {
                "income": round(total_income, 2),
                "expenses": round(total_expenses, 2),
                "net_balance": net_balance,
                "savings_rate": savings_rate
            },
            "category_distribution": category_breakdown_expenses,
            "income_distribution": category_breakdown_income,
            "monthly_trends": monthly_trends,
            "budget_comparison": budgets_data
        }
    }
@customer_bp.get("/financial-summary")
@login_required
@role_required(["customer"])
def get_financial_summary():
    """
    Computes aggregated real-time financial statistics for the customer dashboard.
    Enforces session ownership, zero cross-user leakage, and graceful 0-record defaults.
    """
    user_id = session.get("user_id")
    try:
        payload = _compute_customer_analytics_payload(user_id, tx_limit=10)
        return jsonify(payload), 200
    except Exception as err:
        logger.exception("Failed to generate financial summary for user %s: %s", user_id, err)
        return jsonify({
            "success": False,
            "message": "Failed to calculate financial statistics."
        }), 500
@customer_bp.get("/analytics")
@login_required
@role_required(["customer"])
def get_customer_analytics():
    """
    Provides comprehensive financial intelligence and visual analytics data
    for the authenticated customer's analytics dashboard.
    Enforces strict tenant isolation, zero mock data, and handles empty datasets.
    """
    user_id = session.get("user_id")
    limit = request.args.get("limit", 20, type=int)
    try:
        payload = _compute_customer_analytics_payload(user_id, tx_limit=limit)
        return jsonify(payload), 200
    except Exception as err:
        logger.exception("Failed to generate customer analytics for user %s: %s", user_id, err)
        return jsonify({
            "success": False,
            "message": "Failed to calculate analytics."
        }), 500
# ====================================================================
# STUDENT MORNING SURVEY ENDPOINTS (Phase 10)
# ====================================================================
@customer_bp.get("/survey/today")
@login_required
@role_required(["customer"])
def get_today_morning_survey():
    """
    Retrieves the authenticated student's morning survey for today.
    Enforces tenant isolation and session authorization.
    """
    user_id = session.get("user_id")
    today_str = datetime.now().strftime("%Y-%m-%d")
    survey = DB.get_one(
        """
        SELECT id, user_id, survey_date, plans_to_eat, meal_preference, hunger_level,
               dietary_preference, meal_type, mood_energy, food_restrictions,
               notes, created_at, updated_at
        FROM morning_surveys
        WHERE user_id = %s AND survey_date = %s
        LIMIT 1
        """,
        (user_id, today_str),
    )
    if not survey:
        return jsonify({
            "success": True,
            "completed": False,
            "survey": None,
            "date": today_str
        }), 200
    survey_data = {
        "id": survey["id"],
        "user_id": survey["user_id"],
        "survey_date": str(survey["survey_date"]),
        "plans_to_eat": bool(survey.get("plans_to_eat", 1)),
        "meal_preference": survey["meal_preference"],
        "hunger_level": survey["hunger_level"],
        "dietary_preference": survey["dietary_preference"],
        "meal_type": survey["meal_type"],
        "mood_energy": survey.get("mood_energy") or "",
        "food_restrictions": survey.get("food_restrictions") or "",
        "notes": survey.get("notes") or "",
        "created_at": str(survey["created_at"]),
    }
    return jsonify({
        "success": True,
        "completed": True,
        "survey": survey_data,
        "date": today_str
    }), 200
@customer_bp.post("/survey")
@login_required
@role_required(["customer"])
def submit_morning_survey():
    """
    Submits a student's daily morning food and dining preferences survey.
    Enforces:
    1. Authenticated customer session ownership.
    2. Prevention of duplicate submissions for the same student on the same date.
    3. Input validation and sanitization.
    """
    user_id = session.get("user_id")
    data = request.get_json(silent=True) or {}
    today_str = datetime.now().strftime("%Y-%m-%d")
    # Check for existing survey today to prevent duplicates
    existing = DB.get_one(
        "SELECT id FROM morning_surveys WHERE user_id = %s AND survey_date = %s LIMIT 1",
        (user_id, today_str),
    )
    if existing:
        return jsonify({
            "success": False,
            "message": "You have already completed today's morning survey. Each student may submit once per day.",
            "survey_id": existing["id"]
        }), 409
    plans_to_eat = bool(data.get("plans_to_eat", True))
    meal_preference = str(data.get("meal_preference") or "").strip()
    if not meal_preference:
        return jsonify({"success": False, "message": "Meal preference is required."}), 400
    allowed_hunger = {"light", "moderate", "ravenous", "low", "normal", "high"}
    hunger_mapping = {"low": "light", "normal": "moderate", "high": "ravenous"}
    raw_hunger = str(data.get("hunger_level") or "moderate").strip().lower()
    if "hunger_level" in data and raw_hunger not in allowed_hunger:
        return jsonify({"success": False, "message": f"Invalid hunger_level. Allowed: light, moderate, ravenous"}), 400
    hunger_level = hunger_mapping.get(raw_hunger, raw_hunger if raw_hunger in allowed_hunger else "moderate")
    allowed_diet = {"veg", "non-veg", "vegan", "eggitarian", "any"}
    raw_diet = str(data.get("dietary_preference") or "any").strip().lower()
    if "dietary_preference" in data and raw_diet not in allowed_diet:
        return jsonify({"success": False, "message": f"Invalid dietary_preference. Allowed: {', '.join(sorted(allowed_diet))}"}), 400
    dietary_preference = raw_diet if raw_diet in allowed_diet else "any"
    allowed_meal_types = {"breakfast", "lunch", "evening_snack", "snack", "snacks", "dinner"}
    meal_type_mapping = {"snack": "evening_snack", "snacks": "evening_snack"}
    raw_meal_type = str(data.get("meal_type") or "breakfast").strip().lower()
    if "meal_type" in data and raw_meal_type not in allowed_meal_types:
        return jsonify({"success": False, "message": f"Invalid meal_type. Allowed: breakfast, lunch, evening_snack, dinner"}), 400
    meal_type = meal_type_mapping.get(raw_meal_type, raw_meal_type if raw_meal_type in allowed_meal_types else "breakfast")
    mood_energy = str(data.get("mood_energy") or "").strip()[:50]
    food_restrictions = str(data.get("food_restrictions") or "").strip()[:255]
    notes = str(data.get("notes") or "").strip()[:500]
    try:
        survey_id = DB.execute(
            """
            INSERT INTO morning_surveys (
                user_id, survey_date, plans_to_eat, meal_preference, hunger_level,
                dietary_preference, meal_type, mood_energy, food_restrictions, notes
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                today_str,
                1 if plans_to_eat else 0,
                meal_preference,
                hunger_level,
                dietary_preference,
                meal_type,
                mood_energy,
                food_restrictions,
                notes,
            ),
        )
        logger.info("Morning survey created: id=%s user_id=%s date=%s", survey_id, user_id, today_str)
        return jsonify({
            "success": True,
            "message": "Morning survey submitted successfully!",
            "survey_id": survey_id,
            "survey": {
                "id": survey_id,
                "user_id": user_id,
                "survey_date": today_str,
                "plans_to_eat": plans_to_eat,
                "meal_preference": meal_preference,
                "hunger_level": hunger_level,
                "dietary_preference": dietary_preference,
                "meal_type": meal_type,
                "mood_energy": mood_energy,
                "food_restrictions": food_restrictions,
                "notes": notes,
            }
        }), 201
    except Exception as e:
        logger.exception("Failed to insert morning survey for user %s: %s", user_id, e)
        # Check if error was due to race-condition duplicate key
        if "UNIQUE" in str(e).upper() or "uq_user_survey_date" in str(e).lower():
            return jsonify({
                "success": False,
                "message": "You have already completed today's morning survey."
            }), 409
        return jsonify({
            "success": False,
            "message": "Failed to save morning survey. Please try again."
        }), 500
@customer_bp.get("/survey/history")
@login_required
@role_required(["customer"])
def get_survey_history():
    """Retrieves recent morning surveys for the authenticated student."""
    user_id = session.get("user_id")
    limit = request.args.get("limit", 14, type=int)
    surveys = DB.get_all(
        """
        SELECT id, survey_date, plans_to_eat, meal_preference, hunger_level, dietary_preference,
               meal_type, mood_energy, food_restrictions, created_at
        FROM morning_surveys
        WHERE user_id = %s
        ORDER BY survey_date DESC, id DESC
        LIMIT %s
        """,
        (user_id, limit),
    )
    clean_surveys = []
    for s in surveys:
        clean_surveys.append({
            "id": s["id"],
            "survey_date": str(s["survey_date"]),
            "plans_to_eat": bool(s.get("plans_to_eat", 1)),
            "meal_preference": s["meal_preference"],
            "hunger_level": s["hunger_level"],
            "dietary_preference": s["dietary_preference"],
            "meal_type": s["meal_type"],
            "mood_energy": s.get("mood_energy") or "",
            "food_restrictions": s.get("food_restrictions") or "",
            "created_at": str(s["created_at"]),
        })
    return jsonify({"success": True, "surveys": clean_surveys}), 200
@customer_bp.put("/survey")
@login_required
@role_required(["customer"])
def update_morning_survey():
    """
    Updates the authenticated student's morning survey for today.
    Allows students to change their daily cravings or dietary preference.
    """
    user_id = session.get("user_id")
    data = request.get_json(silent=True) or {}
    today_str = datetime.now().strftime("%Y-%m-%d")
    existing = DB.get_one(
        "SELECT id FROM morning_surveys WHERE user_id = %s AND survey_date = %s LIMIT 1",
        (user_id, today_str),
    )
    if not existing:
        return jsonify({
            "success": False,
            "message": "No survey found for today to update. Please submit a new survey."
        }), 404
    plans_to_eat = bool(data.get("plans_to_eat", True))
    meal_preference = str(data.get("meal_preference") or "").strip()
    if not meal_preference:
        return jsonify({"success": False, "message": "Meal preference is required."}), 400
    allowed_hunger = {"light", "moderate", "ravenous", "low", "normal", "high"}
    hunger_mapping = {"low": "light", "normal": "moderate", "high": "ravenous"}
    raw_hunger = str(data.get("hunger_level") or "moderate").strip().lower()
    if "hunger_level" in data and raw_hunger not in allowed_hunger:
        return jsonify({"success": False, "message": "Invalid hunger_level. Allowed: light, moderate, ravenous"}), 400
    hunger_level = hunger_mapping.get(raw_hunger, raw_hunger if raw_hunger in allowed_hunger else "moderate")
    allowed_diet = {"veg", "non-veg", "vegan", "eggitarian", "any"}
    raw_diet = str(data.get("dietary_preference") or "any").strip().lower()
    if "dietary_preference" in data and raw_diet not in allowed_diet:
        return jsonify({"success": False, "message": f"Invalid dietary_preference. Allowed: {', '.join(sorted(allowed_diet))}"}), 400
    dietary_preference = raw_diet if raw_diet in allowed_diet else "any"
    allowed_meal_types = {"breakfast", "lunch", "evening_snack", "snack", "snacks", "dinner"}
    meal_type_mapping = {"snack": "evening_snack", "snacks": "evening_snack"}
    raw_meal_type = str(data.get("meal_type") or "breakfast").strip().lower()
    if "meal_type" in data and raw_meal_type not in allowed_meal_types:
        return jsonify({"success": False, "message": f"Invalid meal_type. Allowed: breakfast, lunch, evening_snack, dinner"}), 400
    meal_type = meal_type_mapping.get(raw_meal_type, raw_meal_type if raw_meal_type in allowed_meal_types else "breakfast")
    mood_energy = str(data.get("mood_energy") or "").strip()[:50]
    food_restrictions = str(data.get("food_restrictions") or "").strip()[:255]
    notes = str(data.get("notes") or "").strip()[:500]
    try:
        DB.execute(
            """
            UPDATE morning_surveys
            SET plans_to_eat = %s, meal_preference = %s, hunger_level = %s, dietary_preference = %s,
                meal_type = %s, mood_energy = %s, food_restrictions = %s, notes = %s
            WHERE id = %s AND user_id = %s
            """,
            (
                1 if plans_to_eat else 0,
                meal_preference,
                hunger_level,
                dietary_preference,
                meal_type,
                mood_energy,
                food_restrictions,
                notes,
                existing["id"],
                user_id,
            ),
        )
        return jsonify({
            "success": True,
            "message": "Morning survey updated successfully!",
            "survey_id": existing["id"],
            "survey": {
                "id": existing["id"],
                "user_id": user_id,
                "survey_date": today_str,
                "plans_to_eat": plans_to_eat,
                "meal_preference": meal_preference,
                "hunger_level": hunger_level,
                "dietary_preference": dietary_preference,
                "meal_type": meal_type,
                "mood_energy": mood_energy,
                "food_restrictions": food_restrictions,
                "notes": notes,
            }
        }), 200
    except Exception as e:
        logger.exception("Failed to update morning survey for user %s: %s", user_id, e)
        return jsonify({"success": False, "message": "Failed to update morning survey."}), 500


FOOD_SURVEY_TIMEZONE = ZoneInfo("Asia/Kolkata")
DEFAULT_FOOD_SURVEY_WINDOWS = {
    "breakfast": (time(6, 0), time(10, 0)),
    "lunch": (time(10, 30), time(15, 0)),
    "dinner": (time(17, 0), time(21, 0)),
}


def _survey_windows_from_row(row):
    def parse(v, fallback):
        raw = str(v or fallback.strftime("%H:%M"))[:5]
        h, m = [int(x) for x in raw.split(":")]
        return time(h, m)
    return {
        "breakfast": (parse(row.get("breakfast_start"), time(6,0)), parse(row.get("breakfast_end"), time(10,0))),
        "lunch": (parse(row.get("lunch_start"), time(10,30)), parse(row.get("lunch_end"), time(15,0))),
        "dinner": (parse(row.get("dinner_start"), time(17,0)), parse(row.get("dinner_end"), time(21,0))),
    }


def _food_survey_status(now=None, windows=None):
    now = now or datetime.now(FOOD_SURVEY_TIMEZONE)
    current = now.time()
    windows = windows or DEFAULT_FOOD_SURVEY_WINDOWS
    for period, (start, end) in windows.items():
        if start <= current < end:
            return {
                "meal_period": period,
                "status": "open",
                "start_time": start.strftime("%H:%M"),
                "end_time": end.strftime("%H:%M"),
            }
    next_period = None
    for period, (start, end) in windows.items():
        if current < start:
            next_period = period
            break
    return {
        "meal_period": None,
        "status": "closed",
        "next_meal_period": next_period,
        "start_time": None,
        "end_time": None,
    }


@customer_bp.get("/morning-poll/today")
@login_required
@role_required(["customer"])
def get_today_morning_poll():
    """Return today's Food Survey choices with breakfast/lunch/dinner time windows."""
    user_id = session.get("user_id")
    now = datetime.now(FOOD_SURVEY_TIMEZONE)
    today = now.strftime("%Y-%m-%d")
    current = _food_survey_status(now)

    surveys = DB.query("""
        SELECT v.id AS survey_id, v.shop_id, s.name AS shop_name, v.survey_date,
               v.breakfast_start, v.breakfast_end, v.lunch_start, v.lunch_end,
               v.dinner_start, v.dinner_end
        FROM vendor_daily_surveys v
        INNER JOIN shops s ON s.id = v.shop_id
        WHERE v.survey_date = %s AND v.is_serving_today = 1
        ORDER BY s.name
    """, (today,))
    result = []
    for survey in surveys:
        survey_windows = _survey_windows_from_row(survey)
        survey_current = _food_survey_status(now, survey_windows)
        # Read meal period from the master menu item instead of requiring the
        # production daily-menu/vote migration to have completed. This keeps the
        # customer Food Survey page compatible with older production databases.
        options = DB.query("""
            SELECT d.id, d.menu_item_id, m.meal_period, d.item_name, d.price, d.quantity, d.is_available
            FROM vendor_daily_menu_items d
            INNER JOIN menu_items m ON m.id = d.menu_item_id
            WHERE d.survey_id = %s AND d.is_available = 1
            ORDER BY
                CASE m.meal_period
                    WHEN 'breakfast' THEN 1
                    WHEN 'lunch' THEN 2
                    WHEN 'dinner' THEN 3
                    ELSE 4
                END,
                d.item_name
        """, (survey["survey_id"],))

        voted_rows = DB.query(
            """SELECT v.menu_item_id, m.meal_period
               FROM morning_survey_votes v
               INNER JOIN vendor_daily_menu_items d ON d.id = v.menu_item_id
               INNER JOIN menu_items m ON m.id = d.menu_item_id
               WHERE v.survey_id=%s AND v.student_user_id=%s
               ORDER BY v.id""",
            (survey["survey_id"], user_id),
        )
        voted_by_period = {}
        for row in voted_rows:
            voted_by_period.setdefault(str(row["meal_period"]), []).append(int(row["menu_item_id"]))

        result.append({
            "survey_id": survey["survey_id"],
            "shop_id": survey["shop_id"],
            "shop_name": survey["shop_name"],
            "date": str(survey["survey_date"]),
            "current_meal_period": survey_current.get("meal_period"),
            "survey_status": survey_current.get("status"),
            "voted": bool(voted_rows),
            "voted_menu_item_ids": [int(row["menu_item_id"]) for row in voted_rows],
            "voted_menu_item_ids_by_period": voted_by_period,
            "meal_windows": {
                period: {
                    "start_time": start.strftime("%H:%M"),
                    "end_time": end.strftime("%H:%M"),
                    "status": "open" if survey_current.get("meal_period") == period else (
                        "upcoming" if now.time() < start else "closed"
                    ),
                }
                for period, (start, end) in survey_windows.items()
            },
            "options": [{
                "id": row["id"],
                "menu_item_id": row["menu_item_id"],
                "meal_period": str(row.get("meal_period") or "lunch").lower(),
                "item_name": row["item_name"],
                "price": float(row["price"]),
                "quantity": int(row["quantity"] or 0),
            } for row in options]
        })
    return jsonify({
        "success": True,
        "date": today,
        "timezone": "Asia/Kolkata",
        "current": current,
        "surveys": result,
    }), 200


@customer_bp.post("/morning-poll/vote")
@login_required
@role_required(["customer"])
def vote_morning_poll():
    """Record one Food Survey submission for the currently open meal period."""
    user_id = session.get("user_id")
    data = request.get_json(silent=True) or {}
    try:
        survey_id = int(data.get("survey_id"))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Survey is required."}), 400

    meal_period = str(data.get("meal_period") or "").strip().lower()
    if meal_period not in DEFAULT_FOOD_SURVEY_WINDOWS:
        return jsonify({"success": False, "message": "A valid meal period is required."}), 400

    raw_items = data.get("menu_item_ids")
    if raw_items is None and data.get("menu_item_id") is not None:
        raw_items = [data.get("menu_item_id")]
    if not isinstance(raw_items, list):
        return jsonify({"success": False, "message": "Select at least one food item."}), 400

    try:
        menu_item_ids = list(dict.fromkeys(int(item_id) for item_id in raw_items))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Invalid food selection."}), 400

    if not menu_item_ids:
        return jsonify({"success": False, "message": "Select at least one food item."}), 400
    if len(menu_item_ids) > 20:
        return jsonify({"success": False, "message": "You can select up to 20 food items."}), 400

    now = datetime.now(FOOD_SURVEY_TIMEZONE)
    today = now.strftime("%Y-%m-%d")

    survey = DB.get_one(
        """SELECT id, shop_id, breakfast_start, breakfast_end,
                  lunch_start, lunch_end, dinner_start, dinner_end
           FROM vendor_daily_surveys
           WHERE id=%s AND survey_date=%s AND is_serving_today=1
           LIMIT 1""",
        (survey_id, today),
    )
    if not survey:
        return jsonify({"success": False, "message": "This Food Survey is not available today."}), 404

    survey_windows = _survey_windows_from_row(survey)
    start, end = survey_windows[meal_period]
    if not (start <= now.time() < end):
        return jsonify({
            "success": False,
            "message": f"{meal_period.title()} Food Survey is available only from {start.strftime('%I:%M %p')} to {end.strftime('%I:%M %p')} IST."
        }), 403
    if not survey:
        return jsonify({"success": False, "message": "This Food Survey is not available today."}), 404

    placeholders = ",".join(["%s"] * len(menu_item_ids))
    options = DB.query(
        f"""SELECT id FROM vendor_daily_menu_items
            WHERE id IN ({placeholders}) AND survey_id=%s
              AND meal_period=%s AND is_available=1""",
        tuple(menu_item_ids) + (survey_id, meal_period),
    )
    valid_ids = {int(row["id"]) for row in options}
    if len(valid_ids) != len(menu_item_ids):
        return jsonify({"success": False, "message": f"All selected foods must belong to the {meal_period} Food Survey."}), 400

    existing = DB.get_one(
        "SELECT id FROM morning_survey_votes WHERE survey_id=%s AND student_user_id=%s AND meal_period=%s LIMIT 1",
        (survey_id, user_id, meal_period),
    )
    if existing:
        return jsonify({"success": False, "message": f"You have already submitted the {meal_period} Food Survey."}), 409

    try:
        with DB.transaction() as tx:
            for menu_item_id in menu_item_ids:
                tx.execute(
                    """INSERT INTO morning_survey_votes
                       (survey_id, menu_item_id, student_user_id, meal_period)
                       VALUES (%s,%s,%s,%s)""",
                    (survey_id, menu_item_id, user_id, meal_period),
                )
        return jsonify({
            "success": True,
            "message": f"Your {meal_period} Food Survey has been recorded.",
            "meal_period": meal_period,
            "vote_count": len(menu_item_ids),
        }), 201
    except Exception as e:
        if "UNIQUE" in str(e).upper() or "uq_msv_student_survey" in str(e).lower():
            return jsonify({"success": False, "message": f"You have already submitted the {meal_period} Food Survey."}), 409
        logger.exception("Failed to save food survey vote for user %s", user_id)
        return jsonify({"success": False, "message": "Unable to record your Food Survey."}), 500
