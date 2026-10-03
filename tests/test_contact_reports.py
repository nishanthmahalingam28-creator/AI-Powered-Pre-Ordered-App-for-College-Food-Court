import os
import sys
import pytest

# Ensure backend and tests can be resolved
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
os.environ["FLASK_ENV"] = "development"

import init_db
from app import app
from db import DB


@pytest.fixture(autouse=True)
def setup_db():
    """Ensure database is cleanly initialized before tests."""
    init_db.init_sqlite()


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def get_admin_token(client):
    """Authenticate default admin and return auth token."""
    res = client.post("/api/auth/admin/login", json={
        "username": "admin@kpriet.ac.in",
        "password": "admin123"
    })
    assert res.status_code == 200, f"Admin login failed: {res.get_json()}"
    return res.get_json()["auth_token"]


def get_customer_token(client):
    """Authenticate customer user and return auth token."""
    res = client.post("/api/auth/login", json={
        "email": "student@kpriet.ac.in",
        "password": "password123"
    })
    assert res.status_code == 200, f"Customer login failed: {res.get_json()}"
    return res.get_json()["auth_token"]


# ============================================================================
# CONTACT REPORT SUBMISSION (PUBLIC API)
# ============================================================================

def test_submit_contact_report_validation_errors(client):
    """Test validation errors for empty/invalid contact submissions."""
    # Missing name
    res = client.post("/api/contact", json={
        "email": "student@kpriet.ac.in",
        "subject": "Missing Name Test",
        "message": "Testing without name"
    })
    assert res.status_code == 400
    assert "name" in res.get_json()["message"].lower()

    # Invalid email format
    res = client.post("/api/contact", json={
        "name": "Arun Kumar",
        "email": "invalid-email-address",
        "subject": "Email Format Test",
        "message": "Testing invalid email"
    })
    assert res.status_code == 400
    assert "email" in res.get_json()["message"].lower()

    # Missing subject
    res = client.post("/api/contact", json={
        "name": "Arun Kumar",
        "email": "student@kpriet.ac.in",
        "subject": "",
        "message": "Testing empty subject"
    })
    assert res.status_code == 400
    assert "subject" in res.get_json()["message"].lower()

    # Missing message
    res = client.post("/api/contact", json={
        "name": "Arun Kumar",
        "email": "student@kpriet.ac.in",
        "subject": "Subject OK",
        "message": ""
    })
    assert res.status_code == 400
    assert "message" in res.get_json()["message"].lower()


def test_submit_contact_report_success_and_db_persistence(client):
    """Test successful public contact submission and verify database record."""
    payload = {
        "name": "Kavitha Raj",
        "email": "kavitha.raj@kpriet.ac.in",
        "subject": "Food Court Payment Issue",
        "message": "Money was deducted from my account but the stall receipt was not generated."
    }

    res = client.post("/api/contact", json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert data["success"] is True
    assert "contact_id" in data
    contact_id = data["contact_id"]

    # Verify directly in database
    row = DB.get_one("SELECT * FROM contact_messages WHERE id = %s", (contact_id,))
    assert row is not None
    assert row["full_name"] == "Kavitha Raj"
    assert row["email"] == "kavitha.raj@kpriet.ac.in"
    assert row["subject"] == "Food Court Payment Issue"
    assert "Money was deducted" in row["message"]
    assert row["status"] == "new"
    assert row["created_at"] is not None


# ============================================================================
# AUTHORIZATION & ACCESS CONTROL FOR ADMIN ENDPOINT
# ============================================================================

def test_admin_contact_reports_unauthorized_access(client):
    """Anonymous and non-admin users must be rejected."""
    # Anonymous request
    res = client.get("/api/contact/admin")
    assert res.status_code == 401

    # Customer user access attempt
    cust_token = get_customer_token(client)
    res = client.get("/api/contact/admin", headers={"Authorization": f"Bearer {cust_token}"})
    assert res.status_code == 403


# ============================================================================
# END-TO-END FLOW: SUBMIT -> DB INSERT -> ADMIN RETRIEVAL & UPDATE
# ============================================================================

def test_end_to_end_contact_report_flow(client):
    """Verify complete lifecycle: user submission -> admin retrieval -> status update."""
    admin_token = get_admin_token(client)

    # 1. User submits report
    unique_subject = "Delayed Delivery at Stall 4"
    unique_msg = "Waited for 25 minutes for South Indian meals."
    submit_res = client.post("/api/contact", json={
        "name": "Naveen Sundar",
        "email": "naveen@kpriet.ac.in",
        "subject": unique_subject,
        "message": unique_msg
    })
    assert submit_res.status_code == 201
    contact_id = submit_res.get_json()["contact_id"]

    # 2. Admin retrieves contact reports
    admin_res = client.get("/api/contact/admin", headers={"Authorization": f"Bearer {admin_token}"})
    assert admin_res.status_code == 200
    admin_data = admin_res.get_json()
    assert admin_data["success"] is True

    # Both 'reports' and 'messages' keys must be present for maximum frontend compatibility
    assert "messages" in admin_data
    assert "reports" in admin_data

    # 3. Verify the submitted report appears in admin list
    matching_reports = [r for r in admin_data["reports"] if r["id"] == contact_id]
    assert len(matching_reports) == 1, "Submitted report was not found in admin list!"

    report = matching_reports[0]
    assert report["full_name"] == "Naveen Sundar"
    assert report["name"] == "Naveen Sundar"
    assert report["email"] == "naveen@kpriet.ac.in"
    assert report["subject"] == unique_subject
    assert report["message"] == unique_msg
    assert report["status"] == "new"
    assert report["created_at"] is not None

    # 4. Test search filter
    search_res = client.get("/api/contact/admin?q=Naveen", headers={"Authorization": f"Bearer {admin_token}"})
    assert search_res.status_code == 200
    search_reports = search_res.get_json()["reports"]
    assert any(r["id"] == contact_id for r in search_reports)

    # 5. Admin marks report as read
    status_res = client.put(f"/api/contact/admin/{contact_id}/status",
                            headers={"Authorization": f"Bearer {admin_token}"},
                            json={"status": "read"})
    assert status_res.status_code == 200
    assert status_res.get_json()["status"] == "read"

    # Verify status changed in DB
    updated_row = DB.get_one("SELECT status FROM contact_messages WHERE id = %s", (contact_id,))
    assert updated_row["status"] == "read"

    # 6. Admin resolves report
    resolve_res = client.put(f"/api/contact/admin/{contact_id}/status",
                             headers={"Authorization": f"Bearer {admin_token}"},
                             json={"status": "resolved"})
    assert resolve_res.status_code == 200
    assert resolve_res.get_json()["status"] == "resolved"

    resolved_row = DB.get_one("SELECT status FROM contact_messages WHERE id = %s", (contact_id,))
    assert resolved_row["status"] == "resolved"
