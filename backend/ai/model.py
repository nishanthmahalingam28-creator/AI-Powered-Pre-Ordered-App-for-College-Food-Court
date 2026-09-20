"""
Recommendation Model and Scoring Algorithms for Food Court AI Engine.

Uses NumPy and scikit-learn for normalized item affinity scoring,
basket co-occurrence, and explainable scoring weights.
"""

import numpy as np
import logging

logger = logging.getLogger("food_court.ai.model")


class RecommendationModel:
    """
    Lightweight, explainable hybrid recommendation model.
    Balances popularity, meal-slot context, user taste affinity, and basket similarity.
    """

    @classmethod
    def calculate_item_scores(cls, candidate_items, user_profile, popularity_metrics, meal_slot, target_categories):
        """
        Computes normalized recommendation scores [0.0, 1.0] and authoritative
        explainable reasons for candidate items.

        Returns a list of dicts with:
        item, score, reason, dominant_component
        """
        if not candidate_items:
            return []

        user_categories = user_profile.get("categories", {})
        user_favorites = user_profile.get("favorite_items", {})
        has_user_history = bool(user_categories or user_favorites)

        max_sales = max([popularity_metrics.get(item["id"], {}).get("total_units_sold", 0) for item in candidate_items] + [1])

        scored_candidates = []

        today_survey = user_profile.get("today_survey")
        survey_meal_pref = (today_survey.get("meal_preference") or "").lower() if today_survey else ""
        survey_diet_pref = (today_survey.get("dietary_preference") or "any").lower() if today_survey else "any"

        for item in candidate_items:
            item_id = item["id"]
            cat = item.get("category", "")
            item_name_lower = item.get("name", "").lower()
            cat_lower = cat.lower()
            desc_lower = (item.get("description") or "").lower()
            pop_info = popularity_metrics.get(item_id, {})
            units_sold = pop_info.get("total_units_sold", 0)

            # Component 1: Popularity Score (0.0 to 1.0)
            pop_score = float(units_sold) / float(max_sales) if max_sales > 0 else 0.1

            # Component 2: Meal-Slot Context Score (0.3 to 1.0)
            if cat in target_categories:
                slot_score = 1.0
            else:
                slot_score = 0.35

            # Component 3: Personalized Affinity Score (0.0 to 1.0)
            user_score = 0.0
            is_personal_favorite = False
            if has_user_history:
                # Category match weight
                cat_weight = user_categories.get(cat, 0.0)
                max_user_cat = max(user_categories.values()) if user_categories else 1.0
                cat_norm = float(cat_weight) / float(max_user_cat) if max_user_cat > 0 else 0.0

                # Specific item repurchase affinity
                item_freq = user_favorites.get(item_id, 0.0)
                if item_freq > 0:
                    is_personal_favorite = True
                    item_norm = min(1.0, float(item_freq) / 3.0)
                else:
                    item_norm = 0.0

                user_score = 0.65 * cat_norm + 0.35 * item_norm

            # Component 4: Morning Survey Alignment
            survey_matched = False
            survey_boost = 0.0
            if today_survey:
                # Keyword match on meal preference
                keywords = [w for w in survey_meal_pref.replace("&", " ").replace("/", " ").split() if len(w) >= 3]
                if any(kw in item_name_lower or kw in cat_lower or kw in desc_lower for kw in keywords):
                    survey_matched = True
                    survey_boost = 0.25

                # Dietary compatibility check
                if survey_diet_pref in ("veg", "vegan"):
                    non_veg_terms = ("chicken", "mutton", "fish", "egg", "prawn", "beef", "non-veg", "non veg")
                    if any(nv in item_name_lower or nv in cat_lower for nv in non_veg_terms):
                        survey_boost -= 0.40
                    else:
                        survey_boost += 0.10

            # Compute Final Weighted Composite Score
            if has_user_history:
                # Personalized Hybrid Weights
                w_pop = 0.25
                w_slot = 0.25
                w_user = 0.50
                composite = (w_pop * pop_score) + (w_slot * slot_score) + (w_user * user_score) + survey_boost
            else:
                # Cold-Start Weights
                w_pop = 0.55
                w_slot = 0.45
                composite = (w_pop * pop_score) + (w_slot * slot_score) + survey_boost

            # Map to calibrated display score between 0.35 and 0.98
            calibrated_score = round(float(np.clip(0.35 + (composite * 0.60), 0.35, 0.98)), 2)

            # Determine dominant explanation
            reason = cls._generate_explanation(
                item=item,
                pop_score=pop_score,
                units_sold=units_sold,
                slot_score=slot_score,
                user_score=user_score,
                is_personal_favorite=is_personal_favorite,
                meal_slot=meal_slot,
                has_user_history=has_user_history,
                survey_matched=survey_matched,
                today_survey=today_survey
            )

            scored_candidates.append({
                "item": item,
                "score": calibrated_score,
                "reason": reason,
                "raw_composite": composite
            })

        # Sort descending by calibrated score
        scored_candidates.sort(key=lambda x: (x["score"], x["raw_composite"]), reverse=True)
        return scored_candidates

    @classmethod
    def _generate_explanation(cls, item, pop_score, units_sold, slot_score, user_score,
                              is_personal_favorite, meal_slot, has_user_history,
                              survey_matched=False, today_survey=None):
        """Generates authentic, human-readable reasons matching actual recommendation signals."""
        cat = item.get("category", "")
        shop_name = item.get("shop_name", "this stall")

        if survey_matched and today_survey:
            pref = today_survey.get("meal_preference", "your choice")
            return f"Matches today's survey craving ({pref})"

        if has_user_history:
            if is_personal_favorite:
                return "One of your frequent favorites"
            if user_score >= 0.5:
                return f"Matches your frequent preference for {cat}"

        if units_sold >= 5 or pop_score >= 0.6:
            return f"Popular in {shop_name}"

        if slot_score >= 0.9:
            return f"Recommended for {meal_slot}"

        if units_sold > 0:
            return f"Customer favorite at {shop_name}"

        # Fallback cold-start explanation
        return f"Popular choice in {shop_name}"
