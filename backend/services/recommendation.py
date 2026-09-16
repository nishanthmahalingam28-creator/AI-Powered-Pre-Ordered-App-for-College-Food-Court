"""
Legacy Recommendation Service Compatibility Bridge.

Routes calls to the centralized AI/ML engine (backend/ai/recommender.py)
while preserving exact signature and backward compatibility.
"""

from ai.recommender import FoodCourtRecommender as CoreAIRec
from ai.features import FoodCourtFeatures


class FoodCourtRecommender:
    """Compatibility adapter bridging legacy routes to the Phase 8 AI Engine."""

    @staticmethod
    def get_current_meal_context():
        return FoodCourtFeatures.get_current_meal_context()

    @classmethod
    def get_recommendations(cls, user_id=None, shop_id=None, limit=6):
        res = CoreAIRec.get_recommendations(
            customer_id=user_id,
            shop_id=shop_id,
            limit=limit
        )
        return {
            "slot": res.get("slot", "Campus Specials"),
            "heading": res.get("heading", "Chef's Recommendations"),
            "shop_id": res.get("shop_id"),
            "shop_name": res.get("shop_name"),
            "total_evaluated": len(res.get("recommendations", [])),
            "recommendations": res.get("recommendations", []),
        }
