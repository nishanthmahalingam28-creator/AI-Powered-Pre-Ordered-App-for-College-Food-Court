from datetime import datetime
from db import DB


class FoodCourtRecommender:
    """
    AI-Powered Recommendation Engine for College Food Court.
    Features:
    1. Shop-Scoped Filtering: When a stall is selected (e.g. YPR), recommends ONLY items from that stall.
    2. Temporal meal-slot context (Breakfast, Lunch, Evening Snacks, Dinner).
    3. Historical sales velocity and order popularity.
    4. Personalized collaborative preference based on user order history.
    5. Smart tag generation with contextual AI explanations.
    6. Fault-tolerant: Never crashes the main ordering system.
    """

    @staticmethod
    def get_current_meal_context():
        current_hour = datetime.now().hour
        if 6 <= current_hour < 11:
            return "Breakfast", ["Breakfast", "Beverages", "Snacks"], "🌅 Fresh Morning Specials"
        elif 11 <= current_hour < 15:
            return "Lunch", ["Main Course", "Chinese", "South Indian", "Biryani & Chinese"], "🍲 Hearty Lunch Favorites"
        elif 15 <= current_hour < 19:
            return "Snacks", ["Snacks", "Beverages", "Fast Food", "Desserts"], "⚡ Quick Evening Energy"
        else:
            return "Dinner", ["Main Course", "South Indian", "Fast Food", "Chinese"], "🌙 Evening Dinner Picks"

    @classmethod
    def get_recommendations(cls, user_id=None, shop_id=None, limit=6):
        try:
            meal_slot, target_categories, slot_heading = cls.get_current_meal_context()

            # Resolve specific shop if requested
            target_shop = None
            if shop_id:
                if str(shop_id).isdigit():
                    target_shop = DB.get_one("SELECT id, name FROM shops WHERE id = %s", (int(shop_id),))
                else:
                    target_shop = DB.get_one(
                        "SELECT id, name FROM shops WHERE LOWER(name) = %s OR LOWER(slug) = %s",
                        (str(shop_id).lower(), str(shop_id).lower())
                    )

            if target_shop:
                slot_heading = f"{slot_heading} · {target_shop['name']}"

            # 1. Fetch user order history to calculate user preference profile
            user_fav_categories = {}
            user_fav_shops = {}

            if user_id:
                user_orders = DB.query(
                    """
                    SELECT m.category, m.shop_id, COUNT(oi.id) as count
                    FROM order_items oi
                    INNER JOIN orders o ON o.id = oi.order_id
                    INNER JOIN menu_items m ON m.id = oi.menu_item_id
                    WHERE o.customer_id = %s
                    GROUP BY m.category, m.shop_id
                    """,
                    (user_id,),
                )
                for row in user_orders:
                    cat = row.get("category")
                    shop = row.get("shop_id")
                    c = row.get("count", 1)
                    user_fav_categories[cat] = user_fav_categories.get(cat, 0) + c
                    user_fav_shops[shop] = user_fav_shops.get(shop, 0) + c

            # 2. Fetch available menu items (filtered by shop if target_shop specified)
            sql = """
                SELECT m.id, m.shop_id, m.name, m.description, m.price, m.category,
                       m.quantity, m.is_available, s.name as shop_name, s.category as shop_cuisine,
                       COALESCE(SUM(oi.quantity), 0) as total_sold
                FROM menu_items m
                INNER JOIN shops s ON s.id = m.shop_id
                LEFT JOIN order_items oi ON oi.menu_item_id = m.id
                WHERE m.is_available = 1 AND m.quantity > 0 AND s.is_active = 1
            """
            params = []

            if target_shop:
                sql += " AND m.shop_id = %s"
                params.append(target_shop["id"])

            sql += " GROUP BY m.id"

            all_items = DB.query(sql, tuple(params))

            if not all_items:
                return {
                    "slot": meal_slot,
                    "heading": slot_heading,
                    "shop_id": target_shop["id"] if target_shop else None,
                    "recommendations": []
                }

            # 3. AI Scoring Model
            scored_items = []
            for item in all_items:
                score = 10.0  # Base score
                reasons = []

                # A. Meal Slot Context Multiplier (+15 points)
                if item["category"] in target_categories:
                    score += 15.0
                    reasons.append(f"Ideal for {meal_slot}")

                # B. Popularity and Velocity Score (+ up to 20 points)
                sold_count = item["total_sold"]
                if sold_count > 0:
                    pop_bonus = min(20.0, float(sold_count) * 2.5)
                    score += pop_bonus
                    if sold_count >= 5:
                        reasons.append("🔥 Campus Top Seller")

                # C. Personalized User Affinity Boost (+ up to 25 points)
                item_cat = item["category"]
                if item_cat in user_fav_categories:
                    score += min(15.0, user_fav_categories[item_cat] * 3.0)
                    reasons.append("❤️ Matches Your Taste")

                item_shop = item["shop_id"]
                if item_shop in user_fav_shops:
                    score += min(10.0, user_fav_shops[item_shop] * 2.0)
                    reasons.append(f"From your frequent stall: {item['shop_name']}")

                # Fallback badge if no specific reason triggered
                if not reasons:
                    reasons.append(f"Fresh from {item['shop_name']}")

                scored_items.append({
                    "id": item["id"],
                    "shop_id": item["shop_id"],
                    "name": item["name"],
                    "description": item["description"],
                    "price": float(item["price"]),
                    "category": item["category"],
                    "shop_name": item["shop_name"],
                    "ai_score": round(score, 1),
                    "ai_badge": reasons[0],
                    "all_reasons": reasons,
                })

            # Sort descending by AI score
            scored_items.sort(key=lambda x: x["ai_score"], reverse=True)

            return {
                "slot": meal_slot,
                "heading": slot_heading,
                "shop_id": target_shop["id"] if target_shop else None,
                "shop_name": target_shop["name"] if target_shop else None,
                "total_evaluated": len(scored_items),
                "recommendations": scored_items[:limit],
            }

        except Exception as err:
            # Fault-tolerance: never crash calling system
            print(f"[FoodCourtRecommender] Recommendation error: {err}")
            return {
                "slot": "Campus Specials",
                "heading": "Chef's Recommendations",
                "recommendations": []
            }
