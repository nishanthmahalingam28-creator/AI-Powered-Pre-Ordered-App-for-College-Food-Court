"""
Core AI Recommendation Engine for College Food Court.

Connects feature engineering, scoring models, and strict authoritative
database validation (availability, stock, and shop operational status).
"""

import logging
from datetime import datetime
from db import DB
from ai.features import FoodCourtFeatures
from ai.model import RecommendationModel

logger = logging.getLogger("food_court.ai.recommender")


class FoodCourtRecommender:
    """
    Production recommendation service adhering to the core principle:
    AI/ML is advisory; the database is authoritative.
    """

    @classmethod
    def get_recommendations(cls, customer_id: int = None, shop_id=None, limit: int = 5, hour: int = None):
        """
        Main entry point for AI food recommendations.

        Parameters:
        - customer_id: Authenticated user ID (optional; guest/new users get cold-start)
        - shop_id: Target shop ID or slug (enforces 100% shop isolation)
        - limit: Maximum recommendations to return (default 5, capped at 20)
        - hour: Optional override for time-of-day meal slot testing
        """
        try:
            limit = max(1, min(int(limit or 5), 20))

            # 1. Resolve Target Stall if requested (Server-Side Resolution)
            target_shop = None
            if shop_id:
                if str(shop_id).isdigit():
                    target_shop = DB.get_one(
                        "SELECT id, name, slug, is_active, operational_status FROM shops WHERE id = %s",
                        (int(shop_id),)
                    )
                else:
                    target_shop = DB.get_one(
                        "SELECT id, name, slug, is_active, operational_status FROM shops WHERE LOWER(name) = %s OR LOWER(slug) = %s",
                        (str(shop_id).strip().lower(), str(shop_id).strip().lower())
                    )

            target_shop_id = target_shop["id"] if target_shop else None
            target_shop_name = target_shop["name"] if target_shop else None

            # 2. Extract Temporal Context and Meal Slot
            meal_slot, target_categories, slot_heading = FoodCourtFeatures.get_current_meal_context(hour=hour)
            if target_shop:
                slot_heading = f"{slot_heading} · {target_shop_name}"

            # 3. Extract User Taste Affinity Profile (Excludes failed/cancelled orders)
            user_profile = FoodCourtFeatures.get_user_affinity_profile(customer_id)

            # 4. Extract Item Popularity Metrics (Strictly valid orders)
            popularity_metrics = FoodCourtFeatures.get_item_popularity_metrics(shop_id=target_shop_id)

            # 4b. Ground today's recommendations in the customer's daily eating plan
            # and the vendor-published breakfast/lunch/dinner menu.
            today_survey = None
            daily_item_ids = []
            daily_menu_published = False
            if customer_id:
                try:
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    today_survey = DB.get_one(
                        """SELECT plans_to_eat, meal_preference, hunger_level, dietary_preference, meal_type
                           FROM morning_surveys WHERE user_id = %s AND survey_date = %s LIMIT 1""",
                        (customer_id, today_str)
                    )
                    if today_survey and bool(today_survey.get("plans_to_eat", 1)):
                        daily_params = [today_str]
                        survey_sql = """
                            SELECT v.id FROM vendor_daily_surveys v
                            WHERE v.survey_date = %s AND v.is_serving_today = 1
                        """
                        if target_shop_id:
                            survey_sql += " AND v.shop_id = %s"
                            daily_params.append(target_shop_id)
                        survey_sql += " LIMIT 1"
                        published = DB.get_one(survey_sql, tuple(daily_params))
                        daily_menu_published = bool(published)
                        daily_params = [today_str, today_survey.get("meal_type") or meal_slot]
                        daily_sql = """
                            SELECT d.menu_item_id
                            FROM vendor_daily_menu_items d
                            INNER JOIN vendor_daily_surveys v ON v.id = d.survey_id
                            WHERE v.survey_date = %s
                              AND v.is_serving_today = 1
                              AND d.meal_period = %s
                              AND d.is_available = 1
                              AND d.quantity > 0
                        """
                        if target_shop_id:
                            daily_sql += " AND d.shop_id = %s"
                            daily_params.append(target_shop_id)
                        daily_rows = DB.query(daily_sql, tuple(daily_params))
                        daily_item_ids = [int(row["menu_item_id"]) for row in daily_rows]
                    elif today_survey and not bool(today_survey.get("plans_to_eat", 1)):
                        daily_item_ids = []
                except Exception as se:
                    logger.debug("Daily survey grounding lookup skipped: %s", se)

            # 5. Candidate Generation (Query available menu items)
            # Enforce single-stall constraint right at query level
            sql = """
                SELECT m.id, m.shop_id, m.name, m.description, m.price, m.category,
                       m.quantity, m.is_available, s.name as shop_name, s.is_active as shop_is_active,
                       s.operational_status as shop_operational_status
                FROM menu_items m
                INNER JOIN shops s ON s.id = m.shop_id
                WHERE m.is_available = 1
                  AND m.quantity > 0
                  AND s.is_active = 1
            """
            params = []

            # If shop_id was explicitly specified, enforce 100% shop isolation
            if target_shop_id:
                sql += " AND m.shop_id = %s"
                params.append(target_shop_id)

            # If the customer completed today's survey, recommend only dishes
            # explicitly published for the selected meal period today.
            if customer_id and today_survey:
                if not bool(today_survey.get("plans_to_eat", 1)):
                    sql += " AND 1 = 0"
                elif daily_menu_published and daily_item_ids:
                    placeholders = ",".join(["%s"] * len(daily_item_ids))
                    sql += f" AND m.id IN ({placeholders})"
                    params.extend(daily_item_ids)
                elif daily_menu_published:
                    sql += " AND 1 = 0"

            raw_candidates = DB.query(sql, tuple(params))
            if not raw_candidates:
                return {
                    "success": True,
                    "shop_id": target_shop_id,
                    "shop_name": target_shop_name,
                    "slot": meal_slot,
                    "heading": slot_heading,
                    "recommendations": []
                }

            # 6. AI Model Scoring (Hybrid popularity, meal context, user affinity)
            scored_candidates = RecommendationModel.calculate_item_scores(
                candidate_items=raw_candidates,
                user_profile=user_profile,
                popularity_metrics=popularity_metrics,
                meal_slot=meal_slot,
                target_categories=target_categories
            )

            # 6b. Apply today's survey preference boost after the authoritative daily-menu filter.
            if today_survey and not target_shop:
                slot_heading = f"Today's Survey Picks · {today_survey['meal_preference'].title()}"

            if today_survey:
                pref_tokens = [w.lower() for w in today_survey["meal_preference"].replace("-", " ").replace("/", " ").split() if len(w) > 2]
                diet = (today_survey.get("dietary_preference") or "any").lower()
                for entry in scored_candidates:
                    c_name = entry["item"]["name"].lower()
                    c_cat = entry["item"]["category"].lower()
                    matched = any(tok in c_name or tok in c_cat for tok in pref_tokens)
                    if matched:
                        entry["score"] += 0.4
                        entry["reason"] = f"Matches your morning preference ({today_survey['meal_preference']})"
                    elif diet in ("veg", "vegetarian") and "chicken" not in c_name and "egg" not in c_name:
                        entry["score"] += 0.1
                scored_candidates.sort(key=lambda x: x["score"], reverse=True)

            # 7. AUTHORITATIVE AVAILABILITY & INTEGRITY FILTER (Mandatory Step 7)
            # Re-verifies every candidate against real-time database before dispatching
            final_recommendations = []
            seen_item_ids = set()

            for entry in scored_candidates:
                candidate = entry["item"]
                item_id = candidate["id"]

                if item_id in seen_item_ids:
                    continue

                # Live Authoritative Verification
                auth_check = DB.get_one(
                    """
                    SELECT m.id, m.name, m.price, m.quantity, m.is_available, m.category,
                           s.id as shop_id, s.name as shop_name, s.is_active as shop_is_active,
                           s.operational_status as shop_operational_status
                    FROM menu_items m
                    INNER JOIN shops s ON s.id = m.shop_id
                    WHERE m.id = %s
                    """,
                    (item_id,)
                )

                if not auth_check:
                    continue

                # Availability check 1: Active and In-Stock
                if not auth_check["is_available"] or auth_check["quantity"] <= 0:
                    continue

                # Availability check 2: Shop Active and Open
                op_status = str(auth_check.get("shop_operational_status") or "OPEN").upper()
                if not auth_check.get("shop_is_active") or op_status != "OPEN":
                    continue

                # Availability check 3: Stall Isolation Guarantee
                if target_shop_id and auth_check["shop_id"] != target_shop_id:
                    continue

                # Authoritative Price Authority: Use DB price, never AI computed price
                live_price = float(auth_check["price"])

                final_recommendations.append({
                    "id": auth_check["id"],
                    "item_id": auth_check["id"],
                    "name": auth_check["name"],
                    "item_name": auth_check["name"],
                    "price": live_price,
                    "category": auth_check["category"],
                    "shop_id": auth_check["shop_id"],
                    "shop_name": auth_check["shop_name"],
                    "reason": entry["reason"],
                    "ai_badge": entry["reason"],
                    "score": entry["score"],
                    "ai_score": round(entry["score"] * 100, 1)
                })
                seen_item_ids.add(item_id)

                if len(final_recommendations) >= limit:
                    break

            return {
                "success": True,
                "shop_id": target_shop_id,
                "shop_name": target_shop_name,
                "slot": meal_slot,
                "heading": slot_heading,
                "recommendations": final_recommendations
            }

        except Exception as e:
            logger.error("FoodCourtRecommender exception (non-fatal): %s", e)
            return {
                "success": False,
                "shop_id": shop_id,
                "recommendations": [],
                "error": "Recommendation engine temporarily unavailable."
            }
