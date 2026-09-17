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

    results = FoodCourtRecommender.get_recommendations(
        customer_id=customer_id,
        shop_id=shop_id,
        limit=limit
    )
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
