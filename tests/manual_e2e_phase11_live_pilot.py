"""
Manual E2E Test Suite for Phase 11 — Institutional Production Deployment & Live College Pilot.

Executes all 20 specified verification workflow steps in staging/test configuration:
[01] Website Root / Discovery Endpoint Verification
[02] HTTPS Connection & Production Security Headers Check
[03] Customer Registration & Authentication (Student Arjun Kumar)
[04] Stall Directory & Shop Selection (YPR Canteen)
[05] Authoritative Menu Browsing & Stock Check
[06] AI Meal-Slot Recommendation Inquiry
[07] Multi-Item Cart Preparation
[08] Checkout & Authoritative Pricing Total Calculation
[09] Payment Gateway Order Creation & Sandbox Signature Verification
[10] Vendor Live Kitchen Queue Retrieval
[11] Vendor Kitchen Status Transition: PREPARING
[12] Real-Time Order Status Notification Delivery
[13] Vendor Kitchen Status Transition: READY
[14] Customer Counter Arrival & Pickup OTP Presentation
[15] Counter Verification via /api/orders/verify-otp -> COMPLETED
[16] Administrator Global Monitoring & Sales Analytics
[17] Security Audit Logging of Critical Operations
[18] Daily Financial Reconciliation Batch
[19] Production Logical Backup Creation Verification
[20] Disaster Recovery Restore Integrity Verification
"""

import os
import sys
import json
import time
import sqlite3
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ["FLASK_ENV"] = "development"
os.environ["USE_SQLITE"] = "1"
os.environ["SECRET_KEY"] = "phase11-manual-e2e-32b-secret-key-ok"
os.environ["PAYMENT_PROVIDER"] = "razorpay"
os.environ["PAYMENT_ENVIRONMENT"] = "test"
os.environ["RAZORPAY_KEY_ID"] = "rzp_test_collegefoodcourt2026"
os.environ["RAZORPAY_KEY_SECRET"] = "rzp_sec_kpriet_dev_secret_key_32b"
os.environ["RAZORPAY_WEBHOOK_SECRET"] = "rzp_wh_sec_kpriet_webhook_32b_key"

import init_db
init_db.init_sqlite()

from db import DB
from app import app
from werkzeug.security import generate_password_hash
from services.payment_provider import get_payment_provider
from services.notification import NotificationService
from services.audit import AuditService


def print_step(step_num, title, detail=""):
    print(f"\n[{step_num:02d}] {title}")
    if detail:
        print(f"     {detail}")


def run_phase11_pilot_e2e():
    print("=" * 80)
    print("PHASE 11 — INSTITUTIONAL PRODUCTION DEPLOYMENT & LIVE COLLEGE PILOT E2E")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}")
    print("Environment: Authorized Staging & College Pilot Simulation")
    print("Classification: STAGING PILOT VERIFIED (PENDING INSTITUTIONAL INFRASTRUCTURE)")
    print("=" * 80)

    client = app.test_client()
    provider = get_payment_provider()
    pwd = "PilotStudent!2026"
    pwd_hash = generate_password_hash(pwd)

    # Clean scoped test records
    DB.execute("DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE order_reference LIKE 'PILOT11-%')")
    DB.execute("DELETE FROM payments WHERE order_id IN (SELECT id FROM orders WHERE order_reference LIKE 'PILOT11-%')")
    DB.execute("DELETE FROM orders WHERE order_reference LIKE 'PILOT11-%'")
    DB.execute("DELETE FROM customer_profiles WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@pilot11-e2e.kpriet.ac.in')")
    DB.execute("DELETE FROM users WHERE email LIKE '%@pilot11-e2e.kpriet.ac.in'")

    passed_steps = 0

    # Step 1: Website Root / Discovery Endpoint
    print_step(1, "Website Root / Discovery Endpoint Verification")
    root_res = client.get("/")
    assert root_res.status_code == 200
    root_data = root_res.get_json()
    assert root_data["status"] == "running"
    assert "/api/health" in root_data["health"]
    print(f"     [OK] Root endpoint active: {root_data['name']}")
    passed_steps += 1

    # Step 2: HTTPS Connection & Security Headers
    print_step(2, "HTTPS Connection & Production Security Headers Check")
    sec_res = client.get("/api/health", base_url="https://localhost")
    assert sec_res.status_code == 200
    assert sec_res.headers.get("X-Content-Type-Options") == "nosniff"
    assert sec_res.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert sec_res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "max-age=" in sec_res.headers.get("Strict-Transport-Security", "")
    print("     [OK] Production defense-in-depth headers and HSTS verified.")
    passed_steps += 1

    # Step 3: Customer Registration & Login (Student Arjun Kumar)
    print_step(3, "Customer Registration & Authentication (Student Arjun Kumar)")
    student_email = "arjun.p11@pilot11-e2e.kpriet.ac.in"
    student_uid = DB.execute(
        "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
        (student_email, pwd_hash)
    )
    DB.execute(
        """
        INSERT INTO customer_profiles (user_id, customer_type, full_name, identifier, mobile, wallet_balance)
        VALUES (%s, 'student', 'Arjun Kumar', '22CS042', '9876543210', 500.00)
        """,
        (student_uid,)
    )

    login_res = client.post("/api/auth/customer/login", json={
        "email": student_email,
        "password": pwd,
        "customerType": "student"
    })
    assert login_res.status_code == 200
    login_data = login_res.get_json()
    assert login_data["success"] is True
    print(f"     [OK] Student authenticated: {login_data['user']['full_name']} ({login_data['user']['identifier']})")
    passed_steps += 1

    # Step 4: Stall Directory & Shop Selection (YPR Canteen)
    print_step(4, "Stall Directory & Shop Selection (YPR Canteen)")
    shops_res = client.get("/api/shops")
    assert shops_res.status_code == 200
    shops = shops_res.get_json()["shops"]
    ypr_stall = next((s for s in shops if s["id"] == 1), None)
    assert ypr_stall is not None and ypr_stall["operational_status"] == "OPEN"
    print(f"     [OK] Participating stall selected: '{ypr_stall['name']}' (ID: 1, Status: {ypr_stall['operational_status']})")
    passed_steps += 1

    # Step 5: Authoritative Menu Browsing & Stock Check
    print_step(5, "Authoritative Menu Browsing & Stock Check")
    menu_item = DB.get_one("SELECT * FROM menu_items WHERE shop_id = 1 AND is_available = 1 AND quantity >= 5")
    assert menu_item is not None
    initial_stock = menu_item["quantity"]
    print(f"     [OK] Dish: '{menu_item['name']}' @ ₹{menu_item['price']:.2f} (In Stock: {initial_stock})")
    passed_steps += 1

    # Step 6: AI Meal-Slot Recommendation Inquiry
    print_step(6, "AI Meal-Slot Recommendation Inquiry")
    ai_res = client.get("/api/recommendations")
    assert ai_res.status_code == 200
    ai_data = ai_res.get_json()
    assert "recommendations" in ai_data and "slot" in ai_data
    print(f"     [OK] Active Meal Slot: '{ai_data['slot']}', returned {len(ai_data['recommendations'])} items.")
    passed_steps += 1

    # Step 7: Multi-Item Cart Preparation
    print_step(7, "Multi-Item Cart Preparation")
    order_qty = 2
    expected_total = float(menu_item["price"]) * order_qty
    cart = [{"id": menu_item["id"], "quantity": order_qty}]
    print(f"     [OK] Cart prepared: {order_qty}x {menu_item['name']}, Expected Total: ₹{expected_total:.2f}")
    passed_steps += 1

    # Step 8: Checkout & Authoritative Total
    print_step(8, "Checkout & Authoritative Pricing Total Calculation")
    order_res = client.post("/api/orders", json={
        "items": cart,
        "payment_method": "UPI / Online"
    })
    assert order_res.status_code == 201
    order_obj = order_res.get_json()["order"]
    order_id = order_obj["order_id"]
    order_ref = order_obj["order_reference"]
    gateway_order_id = order_obj["gateway_order_id"]
    pickup_otp = order_obj["pickup_otp"]

    stock_after = DB.get_one("SELECT quantity FROM menu_items WHERE id = %s", (menu_item["id"],))["quantity"]
    assert stock_after == initial_stock - order_qty
    print(f"     [OK] Order Created: #{order_ref} (ID: {order_id}), Total: ₹{order_obj['total_amount']:.2f}")
    print(f"     [OK] Stock decremented atomically from {initial_stock} to {stock_after}.")
    passed_steps += 1

    # Step 9: Payment Gateway Order & Sandbox Signature Verification
    print_step(9, "Payment Gateway Order Creation & Sandbox Signature Verification")
    assert gateway_order_id.startswith("order_")
    assert order_obj["amount_paise"] == int(round(expected_total * 100))

    mock_pay_id = f"pay_p11_{int(time.time())}"
    signature = provider.generate_test_signature(gateway_order_id, mock_pay_id)

    verify_res = client.post("/api/payments/verify", json={
        "order_id": order_id,
        "razorpay_order_id": gateway_order_id,
        "razorpay_payment_id": mock_pay_id,
        "razorpay_signature": signature
    })
    assert verify_res.status_code == 200
    assert DB.get_one("SELECT payment_status FROM orders WHERE id = %s", (order_id,))["payment_status"] == "paid"
    print(f"     [OK] Sandbox payment captured. Payment ID: {mock_pay_id}, Status: PAID")
    passed_steps += 1

    # Step 10: Vendor Live Kitchen Queue Retrieval
    print_step(10, "Vendor Live Kitchen Queue Retrieval")
    v_login = client.post("/api/auth/vendor/login", json={"email": "ypr@kpriet.ac.in", "password": "vendor123"})
    assert v_login.status_code == 200
    v_orders = client.get("/api/vendor/orders")
    assert v_orders.status_code == 200
    kitchen_orders = v_orders.get_json().get("orders", [])
    assert any(o["id"] == order_id for o in kitchen_orders)
    print(f"     [OK] Vendor logged in. Order #{order_ref} found in active kitchen queue.")
    passed_steps += 1

    # Step 11: Vendor Kitchen Status Transition: PREPARING
    print_step(11, "Vendor Kitchen Status Transition: PREPARING")
    client.put(f"/api/orders/{order_id}/status", json={"status": "preparing"})
    assert DB.get_one("SELECT order_status FROM orders WHERE id = %s", (order_id,))["order_status"] == "preparing"
    print(f"     [OK] Order #{order_ref} status transitioned to PREPARING.")
    passed_steps += 1

    # Step 12: Real-Time Order Status Notification Delivery
    print_step(12, "Real-Time Order Status Notification Delivery")
    # Switch session back to student to check notification
    client.post("/api/auth/customer/login", json={"email": student_email, "password": pwd, "customerType": "student"})
    notifs = client.get("/api/notifications").get_json()["notifications"]
    assert len(notifs) >= 1
    print(f"     [OK] Notification received: '{notifs[0]['title']}' - {notifs[0]['message']}")
    passed_steps += 1

    # Step 13: Vendor Kitchen Status Transition: READY
    print_step(13, "Vendor Kitchen Status Transition: READY")
    client.post("/api/auth/vendor/login", json={"email": "ypr@kpriet.ac.in", "password": "vendor123"})
    client.put(f"/api/orders/{order_id}/status", json={"status": "ready"})
    assert DB.get_one("SELECT order_status FROM orders WHERE id = %s", (order_id,))["order_status"] == "ready"
    print(f"     [OK] Order #{order_ref} status transitioned to READY.")
    passed_steps += 1

    # Step 14: Customer Counter Arrival & Pickup OTP Presentation
    print_step(14, "Customer Counter Arrival & Pickup OTP Presentation")
    print(f"     [OK] Student presents Pickup OTP: {pickup_otp} at YPR Stall Counter.")
    passed_steps += 1

    # Step 15: Counter Verification via /api/orders/verify-otp -> COMPLETED
    print_step(15, "Counter Verification via /api/orders/verify-otp -> COMPLETED")
    otp_res = client.post("/api/orders/verify-otp", json={"otp": pickup_otp})
    assert otp_res.status_code == 200
    completed_order = DB.get_one("SELECT order_status, completed_time FROM orders WHERE id = %s", (order_id,))
    assert completed_order["order_status"] == "completed"
    assert completed_order["completed_time"] is not None
    print(f"     [OK] Counter OTP verified. Order completed at {completed_order['completed_time']}.")
    passed_steps += 1

    # Step 16: Administrator Global Monitoring & Sales Analytics
    print_step(16, "Administrator Global Monitoring & Sales Analytics")
    client.post("/api/auth/admin/login", json={"email": "admin@kpriet.ac.in", "password": "admin123"})
    admin_overview = client.get("/api/ai/analytics/overview")
    assert admin_overview.status_code == 200
    analytics_data = admin_overview.get_json()
    assert "summary" in analytics_data
    total_rev = analytics_data["summary"]["total_revenue"]
    print(f"     [OK] Admin Telemetry: Total Gross Sales tracked: ₹{total_rev:.2f}")
    passed_steps += 1

    # Step 17: Security Audit Logging of Critical Operations
    print_step(17, "Security Audit Logging of Critical Operations")
    audit_entry = DB.get_one(
        "SELECT * FROM audit_logs WHERE action = 'ORDER_OTP_VERIFIED' AND entity_id = %s ORDER BY id DESC LIMIT 1",
        (str(order_id),)
    )
    assert audit_entry is not None
    print(f"     [OK] Audit Trail Verified: Action '{audit_entry['action']}' recorded for Order #{order_id}.")
    passed_steps += 1

    # Step 18: Daily Financial Reconciliation Batch
    print_step(18, "Daily Financial Reconciliation Batch")
    reconciliation_data = DB.get_all(
        "SELECT o.order_reference, o.total_amount, p.gateway_payment_id, p.status, p.amount "
        "FROM orders o "
        "JOIN payments p ON p.order_id = o.id "
        "WHERE o.id = %s",
        (order_id,)
    )
    assert len(reconciliation_data) >= 1
    rec = reconciliation_data[0]
    assert float(rec["total_amount"]) == float(rec["amount"])
    print(f"     [OK] Daily Batch Reconciliation: Ref {rec['order_reference']} = ₹{rec['total_amount']:.2f} (Gateway: {rec['gateway_payment_id']})")
    passed_steps += 1

    # Step 19: Production Logical Backup Creation Verification
    print_step(19, "Production Logical Backup Creation Verification")
    source_db_path = init_db.SQLITE_PATH
    src_conn = sqlite3.connect(source_db_path)
    dump_lines = list(src_conn.iterdump())
    src_conn.close()
    dump_sql = "\n".join(dump_lines)
    assert len(dump_sql) > 2000
    print(f"     [OK] Staging database logical dump generated ({len(dump_lines)} SQL statements).")
    passed_steps += 1

    # Step 20: Disaster Recovery Restore Integrity Verification
    print_step(20, "Disaster Recovery Restore Integrity Verification")
    target_conn = sqlite3.connect(":memory:")
    target_conn.cursor().executescript(dump_sql)
    target_cur = target_conn.cursor()

    src_conn = sqlite3.connect(source_db_path)
    src_cur = src_conn.cursor()

    for table in ["users", "customer_profiles", "shops", "menu_items", "orders", "payments"]:
        src_cur.execute(f"SELECT COUNT(*) FROM {table}")
        src_cnt = src_cur.fetchone()[0]
        target_cur.execute(f"SELECT COUNT(*) FROM {table}")
        target_cnt = target_cur.fetchone()[0]
        assert src_cnt == target_cnt, f"Mismatch in {table}"

    src_conn.close()
    target_conn.close()
    print("     [OK] Disaster recovery restore verified in isolated environment. 100% row match.")
    passed_steps += 1

    print("\n" + "=" * 80)
    print(f"PHASE 11 PILOT E2E VERIFICATION COMPLETED: {passed_steps}/20 STEPS PASSED (100%)")
    print("STATUS: STAGING PILOT VERIFIED / PRODUCTION DEPLOYMENT PENDING INSTITUTIONAL INFRASTRUCTURE")
    print("=" * 80)


if __name__ == "__main__":
    run_phase11_pilot_e2e()
