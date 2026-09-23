"""
AI and Food Court Intelligence API Blueprint.

Exposes endpoints for personalized/shop-scoped recommendations
and vendor/admin demand analytics.
"""

import logging
from flask import Blueprint, jsonify, request, session
from ai.recommender import FoodCourtRecommender
from ai.analytics import FoodCourtAnalytics
from services.ai_assistant import AIAssistantService
from routes.auth import role_required, login_required
from db import DB

logger = logging.getLogger("food_court.ai.routes")
ai_bp = Blueprint("ai", __name__)


@ai_bp.post("/assistant/chat")
@login_required
@role_required(["customer"])
def chat_with_ai_assistant():
    """
    Secure Customer AI Financial Assistant Endpoint.
    Enforces:
    - User ID strictly derived from session (never user-supplied).
    - Data sanitization and PII/credential scrubbing.
    - Graceful fallback when AI API keys are missing or services fail.
    - Zero hallucination on empty transaction history.
    """
    user_id = session.get("user_id")
    data = request.get_json(silent=True) or {}
    message = data.get("message") or data.get("prompt") or ""

    result = AIAssistantService.generate_response(user_id=user_id, user_message=message)
    if not result.get("success") and result.get("error_code") == "INVALID_INPUT":
        return jsonify(result), 400

    return jsonify(result), 200


@ai_bp.get("/recommendations")
def get_ai_recommendations():
    """
    AI-Powered Food Recommendations API.

    Query Parameters:
    - shop_id: Optional shop ID to strictly scope recommendations.
    - limit: Max items to return (default 5, max 20).
    Owner user ID is derived from the authenticated session (or None for guest users).
    """
    customer_id = session.get("user_id")

    raw_shop_id = request.args.get("shop_id") or request.args.get("shop")
    shop_id = None
    if raw_shop_id:
        try:
            shop_id = int(raw_shop_id)
        except (ValueError, TypeError):
            shop_id = raw_shop_id

    # Personalized customer recommendations without a stall scope strictly require authentication
    if not shop_id and not customer_id:
        return jsonify({
            "success": False,
            "message": "Authentication required for personalized recommendations."
        }), 401

    try:
        limit = int(request.args.get("limit", 5))
    except (ValueError, TypeError):
        limit = 5

    try:
        results = FoodCourtRecommender.get_recommendations(
            customer_id=customer_id,
            shop_id=shop_id,
            limit=limit
        )
    except Exception as exc:
        logger.error("AI recommendation route failed: %s", type(exc).__name__)
        results = {"success": False, "recommendations": []}

    # Last-resort production-safe menu fallback. The AI engine is advisory;
    # the live menu remains the authoritative source. This intentionally uses
    # only columns that existed before the operational-status migration, so an
    # older production database can still render the customer dashboard while
    # its startup migration catches up.
    if not results.get("success") or not isinstance(results.get("recommendations"), list):
        try:
            fallback_sql = """
                SELECT m.id, m.name, m.description, m.price, m.category,
                       m.shop_id, s.name AS shop_name
                FROM menu_items m
                INNER JOIN shops s ON s.id = m.shop_id
                WHERE m.is_available = 1
                  AND m.quantity > 0
                  AND s.is_active = 1
            """
            fallback_params = []
            if shop_id:
                fallback_sql += " AND m.shop_id = %s"
                fallback_params.append(shop_id)
            fallback_sql += " ORDER BY m.id DESC LIMIT %s"
            fallback_params.append(limit)
            rows = DB.query(fallback_sql, tuple(fallback_params))
            results = {
                "success": True,
                "slot": "Campus Specials",
                "heading": "🍽️ Campus Favorites",
                "shop_id": shop_id,
                "shop_name": None,
                "recommendations": [{
                    "id": row["id"],
                    "item_id": row["id"],
                    "name": row["name"],
                    "item_name": row["name"],
                    "description": row.get("description") or row.get("category") or "Available now",
                    "price": float(row["price"]),
                    "category": row.get("category") or "Food",
                    "shop_id": row["shop_id"],
                    "shop_name": row["shop_name"],
                    "reason": "Available now",
                    "ai_badge": "Available now",
                    "score": 0.5,
                    "ai_score": 50.0
                } for row in rows]
            }
        except Exception as fallback_exc:
            logger.error("AI recommendation fallback failed: %s", type(fallback_exc).__name__)
            return jsonify({
                "success": False,
                "message": "Recommendations are temporarily unavailable."
            }), 503

    return jsonify(results), 200


@ai_bp.get("/analytics/shop/<int:shop_id>")
@role_required(["vendor", "admin"])
def get_shop_analytics_route(shop_id: int):
    """
    Stall Sales & Demand Intelligence API.
    Enforces strict vendor shop isolation.
    """
    role = session.get("role")
    user_id = session.get("user_id")

    # Vendor Isolation Enforcement
    if role == "vendor":
        assigned_shop = DB.get_one(
            "SELECT id FROM shops WHERE owner_user_id = %s AND is_active = 1 LIMIT 1",
            (user_id,)
        )
        if not assigned_shop or assigned_shop["id"] != shop_id:
            return jsonify({
                "success": False,
                "message": "Forbidden: You do not have permission to view analytics for this stall."
            }), 403

    analytics_data = FoodCourtAnalytics.get_shop_analytics(shop_id=shop_id)
    if not analytics_data:
        return jsonify({
            "success": False,
            "message": f"Stall #{shop_id} not found."
        }), 404

    return jsonify({
        "success": True,
        **analytics_data
    }), 200


@ai_bp.get("/analytics/overview")
@role_required(["admin"])
def get_admin_overview_analytics_route():
    """
    Platform-Wide Food Court Intelligence API.
    Provides multi-stall comparative metrics and demand velocity.
    """
    overview_data = FoodCourtAnalytics.get_admin_overview_analytics()
    return jsonify({
        "success": True,
        **overview_data
    }), 200
