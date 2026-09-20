"""
Feature Extraction and Context Engineering for Food Court AI/ML Engine.

Extracts historical interaction signals, user preferences, and temporal contexts
strictly from valid completed/paid orders.
"""

from datetime import datetime, timedelta
import logging
from db import DB

logger = logging.getLogger("food_court.ai.features")


class FoodCourtFeatures:
    """Extracts features for recommendation and analytics from authoritative database."""

    MEAL_SLOTS = {
        "Breakfast": {
            "hours": range(6, 11),
            "target_categories": {"Breakfast", "Beverages", "Snacks", "South Indian"},
            "heading": "🌅 Morning Breakfast Picks",
        },
        "Lunch": {
            "hours": range(11, 15),
            "target_categories": {"Main Course", "South Indian", "Chinese", "Biryani & Chinese", "Meals"},
            "heading": "🍲 Hearty Lunch Specials",
        },
        "Snacks": {
            "hours": range(15, 19),
            "target_categories": {"Snacks", "Beverages", "Fast Food", "Desserts", "Tea"},
            "heading": "⚡ Quick Evening Energy",
        },
        "Dinner": {
            "hours": list(range(19, 24)) + list(range(0, 6)),
            "target_categories": {"Main Course", "South Indian", "Chinese", "Fast Food"},
            "heading": "🌙 Evening Dinner Picks",
        },
    }

    @classmethod
    def get_current_meal_context(cls, hour=None):
        """Returns the current meal slot, target categories, and contextual heading."""
        if hour is None:
            hour = datetime.now().hour

        for slot_name, slot_info in cls.MEAL_SLOTS.items():
            if hour in slot_info["hours"]:
                return slot_name, slot_info["target_categories"], slot_info["heading"]

        # Default fallback
        return "All-Day", {"Main Course", "Snacks", "Beverages"}, "🍽️ Campus Favorites"

    @classmethod
    def get_user_affinity_profile(cls, customer_id: int):
        """
        Extracts user taste affinity from valid historical orders.
        Strict Rule: Excludes cancelled and failed orders.
        Applies mild recency weighting to recent purchases.
        """
        if not customer_id:
            return {
                "categories": {},
                "favorite_items": {},
                "frequent_shops": {},
                "total_valid_orders": 0,
            }

        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            today_survey = DB.get_one(
                """
                SELECT meal_preference, hunger_level, dietary_preference, meal_type, mood_energy, food_restrictions
                FROM morning_surveys
                WHERE user_id = %s AND survey_date = %s
                LIMIT 1
                """,
                (customer_id, today_str),
            )

            # Query valid past purchases
            query = """
                SELECT oi.menu_item_id, m.name as item_name, m.category, o.shop_id,
                       oi.quantity, o.created_at
                FROM order_items oi
                INNER JOIN orders o ON o.id = oi.order_id
                INNER JOIN menu_items m ON m.id = oi.menu_item_id
                WHERE o.customer_id = %s
                  AND (o.payment_status = 'paid' OR o.order_status = 'completed')
                  AND o.order_status != 'cancelled'
                  AND o.payment_status != 'failed'
                ORDER BY o.created_at DESC
            """
            rows = DB.query(query, (customer_id,))
            if not rows:
                return {
                    "categories": {},
                    "favorite_items": {},
                    "frequent_shops": {},
                    "total_valid_orders": 0,
                    "today_survey": today_survey or None,
                }

            cat_weights = {}
            item_weights = {}
            shop_weights = {}
            now = datetime.now()

            for r in rows:
                qty = int(r.get("quantity") or 1)
                cat = r.get("category") or "General"
                item_id = r["menu_item_id"]
                shop_id = r["shop_id"]

                # Recency factor: within 7 days = 1.5x, within 30 days = 1.2x, else 1.0x
                recency_multiplier = 1.0
                order_time = r.get("created_at")
                if order_time:
                    try:
                        if isinstance(order_time, str):
                            ot = datetime.strptime(order_time[:19], "%Y-%m-%d %H:%M:%S")
                        else:
                            ot = order_time
                        delta_days = (now - ot).days
                        if delta_days <= 7:
                            recency_multiplier = 1.5
                        elif delta_days <= 30:
                            recency_multiplier = 1.2
                    except Exception:
                        recency_multiplier = 1.0

                effective_weight = qty * recency_multiplier
                cat_weights[cat] = cat_weights.get(cat, 0.0) + effective_weight
                item_weights[item_id] = item_weights.get(item_id, 0.0) + effective_weight
                shop_weights[shop_id] = shop_weights.get(shop_id, 0.0) + effective_weight

            return {
                "categories": cat_weights,
                "favorite_items": item_weights,
                "frequent_shops": shop_weights,
                "total_valid_orders": len(rows),
                "today_survey": today_survey or None,
            }
        except Exception as e:
            logger.error("Error extracting user affinity profile for customer_id=%s: %s", customer_id, e)
            return {
                "categories": {},
                "favorite_items": {},
                "frequent_shops": {},
                "total_valid_orders": 0,
                "today_survey": None,
            }

    @classmethod
    def get_item_popularity_metrics(cls, shop_id: int = None):
        """
        Computes item popularity and sales metrics across valid completed/paid orders.
        """
        try:
            sql = """
                SELECT oi.menu_item_id,
                       SUM(oi.quantity) as total_units_sold,
                       COUNT(DISTINCT o.id) as order_count,
                       SUM(oi.subtotal) as total_revenue
                FROM order_items oi
                INNER JOIN orders o ON o.id = oi.order_id
                WHERE (o.payment_status = 'paid' OR o.order_status = 'completed')
                  AND o.order_status != 'cancelled'
                  AND o.payment_status != 'failed'
            """
            params = []
            if shop_id:
                sql += " AND o.shop_id = %s"
                params.append(shop_id)

            sql += " GROUP BY oi.menu_item_id"

            rows = DB.query(sql, tuple(params))
            metrics = {}
            for r in rows:
                metrics[r["menu_item_id"]] = {
                    "total_units_sold": int(r.get("total_units_sold") or 0),
                    "order_count": int(r.get("order_count") or 0),
                    "total_revenue": float(r.get("total_revenue") or 0.0),
                }
            return metrics
        except Exception as e:
            logger.error("Error computing item popularity metrics: %s", e)
            return {}
