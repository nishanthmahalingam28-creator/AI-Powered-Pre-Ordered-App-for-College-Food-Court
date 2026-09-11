from flask import Blueprint, jsonify, request, session
from services.recommendation import FoodCourtRecommender

recommend_bp = Blueprint("recommendations", __name__)


@recommend_bp.get("")
@recommend_bp.get("/")
def get_recommendations():
    user_id = session.get("user_id") or request.args.get("user_id")
    shop_id = request.args.get("shop_id") or request.args.get("shop")
    limit = int(request.args.get("limit", 6))

    result = FoodCourtRecommender.get_recommendations(user_id=user_id, shop_id=shop_id, limit=limit)
    return jsonify({"success": True, **result}), 200
