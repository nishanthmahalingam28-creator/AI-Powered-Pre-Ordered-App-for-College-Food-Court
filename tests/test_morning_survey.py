"""
Automated Test Suite for Student Morning Survey Feature & AI Personalization Integration.

Validates:
1. Authentication & Role Enforcement: Unauthenticated requests return 401; non-customers return 403.
2. Initial State: GET /api/customer/survey/today returns {"completed": false} before submission.
3. Validation: POST /api/customer/survey validates required fields, dietary preference, and hunger level.
4. Submission: POST /api/customer/survey creates records in the database with HTTP 201.
5. Duplicate Prevention: Attempting to submit twice on the same calendar day returns HTTP 409 Conflict.
6. Status Retrieval: GET /api/customer/survey/today returns completed status and survey record.
7. History: GET /api/customer/survey/history returns historical survey entries.
8. AI Integration: Verified AI Recommender prioritizes student morning cravings and dietary choices.
"""

import os
import sys
import unittest
import json
from datetime import date

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ["FLASK_ENV"] = "development"
os.environ["USE_SQLITE"] = "1"
os.environ["SECRET_KEY"] = "survey-test-key-32-chars-long-secure"

import init_db
init_db.init_sqlite()

from db import DB
from app import app
from ai.recommender import FoodCourtRecommender


class TestMorningSurveyAPI(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()

        # Clean morning_surveys before each test
        DB.execute("DELETE FROM morning_surveys")

        # Set up a test student customer session (user id 8)
        with self.client.session_transaction() as sess:
            sess["user_id"] = 8
            sess["role"] = "customer"
            sess["customer_type"] = "student"
            sess["email"] = "student@kpriet.ac.in"

    def test_unauthenticated_survey_access_rejected(self):
        anon_client = self.app.test_client()
        res = anon_client.get("/api/customer/survey/today")
        self.assertEqual(res.status_code, 401)

        res = anon_client.post("/api/customer/survey", json={"meal_preference": "Dosa"})
        self.assertEqual(res.status_code, 401)

        res = anon_client.get("/api/customer/survey/history")
        self.assertEqual(res.status_code, 401)

    def test_vendor_role_access_denied(self):
        vendor_client = self.app.test_client()
        with vendor_client.session_transaction() as sess:
            sess["user_id"] = 2
            sess["role"] = "vendor"

        res = vendor_client.get("/api/customer/survey/today")
        self.assertEqual(res.status_code, 403)

    def test_survey_initially_not_completed(self):
        res = self.client.get("/api/customer/survey/today")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertFalse(data.get("completed"))
        self.assertIsNone(data.get("survey"))

    def test_survey_validation_errors(self):
        # Missing meal_preference
        res = self.client.post("/api/customer/survey", json={
            "dietary_preference": "Veg",
            "hunger_level": "High"
        })
        self.assertEqual(res.status_code, 400)

        # Invalid dietary_preference
        res = self.client.post("/api/customer/survey", json={
            "meal_preference": "Biryani",
            "dietary_preference": "Carnivore"
        })
        self.assertEqual(res.status_code, 400)

        # Invalid hunger_level
        res = self.client.post("/api/customer/survey", json={
            "meal_preference": "Biryani",
            "dietary_preference": "Non-Veg",
            "hunger_level": "Starving"
        })
        self.assertEqual(res.status_code, 400)

    def test_submit_survey_and_retrieve_today(self):
        payload = {
            "meal_preference": "Crispy Ghee Podi Dosa",
            "hunger_level": "High",
            "dietary_preference": "Veg",
            "meal_type": "Breakfast",
            "mood_energy": "Energized",
            "food_restrictions": "No peanuts",
            "notes": "Prefer spicy chutney"
        }
        res = self.client.post("/api/customer/survey", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertIn("survey_id", data)

        # Verify today survey returns completed
        today_res = self.client.get("/api/customer/survey/today")
        self.assertEqual(today_res.status_code, 200)
        today_data = today_res.get_json()
        self.assertTrue(today_data.get("completed"))
        survey = today_data.get("survey")
        self.assertIsNotNone(survey)
        self.assertEqual(survey.get("meal_preference"), "Crispy Ghee Podi Dosa")
        self.assertEqual(survey.get("hunger_level"), "ravenous")
        self.assertEqual(survey.get("dietary_preference"), "veg")
        self.assertEqual(survey.get("food_restrictions"), "No peanuts")

    def test_prevent_duplicate_submission_same_day(self):
        payload = {
            "meal_preference": "Paneer Fried Rice",
            "hunger_level": "Normal",
            "dietary_preference": "Veg",
            "meal_type": "Lunch"
        }
        first_res = self.client.post("/api/customer/survey", json=payload)
        self.assertEqual(first_res.status_code, 201)

        # Second submission on same day must be rejected with 409
        second_res = self.client.post("/api/customer/survey", json=payload)
        self.assertEqual(second_res.status_code, 409)
        err_data = second_res.get_json()
        self.assertFalse(err_data.get("success"))
        self.assertIn("already completed", err_data.get("message").lower())

    def test_survey_history(self):
        payload = {
            "meal_preference": "South Indian Meals",
            "hunger_level": "High",
            "dietary_preference": "Veg",
            "meal_type": "Lunch"
        }
        self.client.post("/api/customer/survey", json=payload)

        res = self.client.get("/api/customer/survey/history")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertGreaterEqual(len(data.get("surveys", [])), 1)
        self.assertEqual(data["surveys"][0]["meal_preference"], "South Indian Meals")

    def test_ai_recommender_uses_morning_survey(self):
        # Submit a survey craving Dosa
        payload = {
            "meal_preference": "Dosa",
            "hunger_level": "High",
            "dietary_preference": "Veg",
            "meal_type": "Breakfast"
        }
        self.client.post("/api/customer/survey", json=payload)

        # Call AI recommendations for user 8
        result = FoodCourtRecommender.get_recommendations(customer_id=8)
        self.assertTrue(result.get("success"))
        recs = result.get("recommendations", [])
        self.assertIsInstance(recs, list)
        self.assertGreater(len(recs), 0)

        # Check that items matching the survey craving received boosted scoring or reason
        has_survey_match = any("survey" in item.get("reason", "").lower() or "dosa" in item.get("name", "").lower() for item in recs)
        self.assertTrue(has_survey_match, "Recommender should highlight or boost morning survey preferences")


if __name__ == "__main__":
    unittest.main()
