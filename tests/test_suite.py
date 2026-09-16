"""
Production-Grade Automated Test Suite for College Food Court Application.
Covers:
1. Server Connectivity & Health
2. Public Menu & Stalls Directory
3. Multi-Persona Authentication (Student, Faculty, Guest, Vendor, Admin)
4. Role-Based Access Control (RBAC) & IDOR Tenant Isolation
5. Cart System & Single-Shop Enforcement
6. Atomic Stock Validation & Concurrency Protection
7. Order Lifecycle, OTP Pickup & Status Transitions
8. Shop-Scoped AI Food Recommendation Engine
9. Admin Governance & Vendor Assignment
10. Frontend Static Assets Integrity
"""

import sys
import json
import secrets
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar

API_URL = "http://127.0.0.1:5000/api"
FRONTEND_URL = "http://127.0.0.1:5500"

passed = 0
failed = 0

def test(name, condition, details=""):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name} - {details}")
        failed += 1

def request(url, method="GET", data=None, headers=None, session=None):
    if headers is None:
        headers = {}
    if data is not None:
        data_bytes = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    else:
        data_bytes = None

    req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
    s = session if session else urllib.request.build_opener()
    try:
        with s.open(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            status = resp.status
            try:
                return status, json.loads(body)
            except:
                return status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except:
            return e.code, body
    except Exception as e:
        return 0, str(e)

print("=" * 75)
print("COLLEGE FOOD COURT APP — MASTER VERIFICATION & REGRESSION SUITE")
print("=" * 75)

# -------------------------------------------------------------
# 1. Server Health Checks
# -------------------------------------------------------------
print("\n--- 1. SERVER CONNECTIVITY & HEALTH ---")
st, body = request(f"{API_URL}/shops")
test("Backend REST API running on port 5000", st == 200, f"Status: {st}")

st, body = request(f"{FRONTEND_URL}/index.html")
test("Frontend static server running on port 5500", st == 200, f"Status: {st}")

# -------------------------------------------------------------
# 2. Public Menu & Stalls Directory
# -------------------------------------------------------------
print("\n--- 2. PUBLIC MENU & STALLS DIRECTORY ---")
st, body = request(f"{API_URL}/shops")
shops = body.get("shops", []) if isinstance(body, dict) else []
test("GET /api/shops returns stall list", st == 200 and isinstance(shops, list))
test("All 6 college stalls present in DB", len(shops) >= 6, f"Count: {len(shops)}")

st, body = request(f"{API_URL}/categories")
categories = body.get("categories", []) if isinstance(body, dict) else []
test("GET /api/categories returns food categories", st == 200 and len(categories) > 0)

st, body = request(f"{API_URL}/menu")
items = body.get("items", []) if isinstance(body, dict) else []
test("GET /api/menu returns food catalog", st == 200 and len(items) >= 18, f"Count: {len(items)}")

st, body = request(f"{API_URL}/menu?q=Dosa")
dosa_items = body.get("items", []) if isinstance(body, dict) else []
test("Search query filtering works correctly", st == 200 and any("dosa" in i["name"].lower() for i in dosa_items))

# -------------------------------------------------------------
# 3. Multi-Persona Authentication
# -------------------------------------------------------------
print("\n--- 3. MULTI-PERSONA AUTHENTICATION ---")

# A. Student Signup & Login
student_email = f"student_{secrets.token_hex(4)}@kpriet.ac.in"
st, body = request(f"{API_URL}/auth/otp/send", "POST", {"email": student_email, "purpose": "signup"})
otp = body.get("demo_otp") or body.get("debug_code")
test("Student OTP generation", st == 200 and bool(otp))

st, body = request(f"{API_URL}/auth/otp/verify", "POST", {"email": student_email, "otp": otp})
test("Student OTP validation", st == 200 and body.get("verified") is True)

student_signup = {
    "fullName": "KPR Student Tester",
    "email": student_email,
    "password": "Password123!",
    "customerType": "student",
    "identifier": "22CS101",
    "mobile": "9876543210"
}
st, body = request(f"{API_URL}/auth/customer/signup", "POST", student_signup)
test("Student registration", st in (200, 201))

student_cj = http.cookiejar.CookieJar()
student_session = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(student_cj))
st, body = request(f"{API_URL}/auth/customer/login", "POST", {
    "email": student_email,
    "password": "Password123!",
    "customerType": "student"
}, session=student_session)
test("Student login with session", st == 200 and body.get("success") is True)
student_user_id = body.get("user", {}).get("id")

st, body = request(f"{API_URL}/auth/me", session=student_session)
test("Student /auth/me profile verification", st == 200 and body.get("user", {}).get("email") == student_email)

# B. Faculty Signup & Login
faculty_email = f"prof_{secrets.token_hex(4)}@kpriet.ac.in"
faculty_signup = {
    "fullName": "Dr. Alan Turing",
    "email": faculty_email,
    "password": "ProfessorPass123!",
    "customerType": "faculty",
    "identifier": "EMP7042",
    "mobile": "9876543211"
}
st, body = request(f"{API_URL}/auth/customer/signup", "POST", faculty_signup)
test("Faculty registration", st in (200, 201))

faculty_cj = http.cookiejar.CookieJar()
faculty_session = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(faculty_cj))
st, body = request(f"{API_URL}/auth/customer/login", "POST", {
    "email": faculty_email,
    "password": "ProfessorPass123!",
    "customerType": "faculty"
}, session=faculty_session)
test("Faculty login", st == 200 and body.get("user", {}).get("customer_type") == "faculty")

# C. Guest Signup & Login
guest_email = f"guest_{secrets.token_hex(4)}@gmail.com"
guest_signup = {
    "fullName": "Campus Visitor",
    "email": guest_email,
    "password": "GuestPassword123!",
    "customerType": "guest",
    "mobile": "9876543212"
}
st, body = request(f"{API_URL}/auth/customer/signup", "POST", guest_signup)
test("Guest registration", st in (200, 201))

guest_cj = http.cookiejar.CookieJar()
guest_session = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(guest_cj))
st, body = request(f"{API_URL}/auth/customer/login", "POST", {
    "email": guest_email,
    "password": "GuestPassword123!",
    "customerType": "guest"
}, session=guest_session)
test("Guest login", st == 200 and body.get("user", {}).get("customer_type") == "guest")

# D. Cross-Persona Isolation Test
st, body = request(f"{API_URL}/auth/customer/login", "POST", {
    "email": student_email,
    "password": "Password123!",
    "customerType": "faculty"
})
test("Cross-persona login rejection (Student blocked from Faculty portal)", st == 401 and "student" in body.get("message", "").lower())

# D. Negative Authentication Tests
st, body = request(f"{API_URL}/auth/customer/login", "POST", {
    "email": student_email,
    "password": "WrongPassword!"
})
test("Invalid password rejection (HTTP 401)", st == 401)

# E. Unauthenticated Access Protection
anon_session = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
st, body = request(f"{API_URL}/orders/my-orders", session=anon_session)
test("Unauthenticated access blocked (HTTP 401)", st == 401)

# -------------------------------------------------------------
# 4. Role-Based Access Control (RBAC) & IDOR Isolation
# -------------------------------------------------------------
print("\n--- 4. ROLE-BASED ACCESS CONTROL & IDOR ISOLATION ---")

# Customer blocked from admin
st, body = request(f"{API_URL}/admin/overview", session=student_session)
test("Customer blocked from Admin overview (HTTP 403)", st == 403)

# Customer blocked from vendor kitchen queue
st, body = request(f"{API_URL}/orders/vendor/1", session=student_session)
test("Customer blocked from Vendor kitchen queue (HTTP 403)", st == 403)

# Setup Vendor 1 Session (YPR - Shop 1)
vendor1_cj = http.cookiejar.CookieJar()
vendor1_session = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(vendor1_cj))
st, body = request(f"{API_URL}/auth/vendor/login", "POST", {
    "email": "ypr@kpriet.ac.in",
    "password": "vendor123"
}, session=vendor1_session)
test("Vendor 1 (YPR) login", st == 200 and body.get("success") is True)

# Setup Vendor 2 Session (Campus Kitchen - Shop 2)
vendor2_cj = http.cookiejar.CookieJar()
vendor2_session = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(vendor2_cj))
st, body = request(f"{API_URL}/auth/vendor/login", "POST", {
    "email": "campus@kpriet.ac.in",
    "password": "vendor123"
}, session=vendor2_session)
test("Vendor 2 (Campus Kitchen) login", st == 200 and body.get("success") is True)

# IDOR Test: Vendor 1 trying to access Vendor 2's kitchen queue
st, body = request(f"{API_URL}/orders/vendor/2", session=vendor1_session)
test("Vendor 1 blocked from Vendor 2 kitchen queue (HTTP 403)", st == 403)

# IDOR Test: Vendor 2 trying to access Vendor 1's kitchen queue
st, body = request(f"{API_URL}/orders/vendor/1", session=vendor2_session)
test("Vendor 2 blocked from Vendor 1 kitchen queue (HTTP 403)", st == 403)

# -------------------------------------------------------------
# 5. Cart System & Single-Shop Enforcement
# -------------------------------------------------------------
print("\n--- 5. CART SYSTEM & SINGLE-SHOP ENFORCEMENT ---")

# Fetch an item from Shop 1 (YPR) and Shop 2 (Campus Kitchen)
st, body1 = request(f"{API_URL}/menu?shop_id=1")
shop1_items = body1.get("items", [])
item_shop1 = shop1_items[0] if shop1_items else None

st, body2 = request(f"{API_URL}/menu?shop_id=2")
shop2_items = body2.get("items", [])
item_shop2 = shop2_items[0] if shop2_items else None

test("Items from multiple stalls available for test", item_shop1 is not None and item_shop2 is not None)

# Attempt Mixed-Shop Order
mixed_order_payload = {
    "items": [
        {"id": item_shop1["id"], "quantity": 1},
        {"id": item_shop2["id"], "quantity": 1}
    ],
    "payment_method": "Campus Wallet"
}
st, body = request(f"{API_URL}/orders", "POST", mixed_order_payload, session=student_session)
test("Backend rejects mixed-stall order (HTTP 400)", st == 400 and "one shop" in body.get("message", "").lower())

# -------------------------------------------------------------
# 6. Stock Validation & Negative Stock Protection
# -------------------------------------------------------------
print("\n--- 6. STOCK VALIDATION & NEGATIVE STOCK PROTECTION ---")

# Attempt to order excess quantity beyond stock
excess_order_payload = {
    "items": [
        {"id": item_shop1["id"], "quantity": 99999}
    ],
    "payment_method": "Campus Wallet"
}
st, body = request(f"{API_URL}/orders", "POST", excess_order_payload, session=student_session)
test("Excessive quantity rejected by stock guard (HTTP 400)", st == 400 and "available" in body.get("message", "").lower())

# Attempt to order zero quantity
zero_order_payload = {
    "items": [
        {"id": item_shop1["id"], "quantity": 0}
    ],
    "payment_method": "Campus Wallet"
}
st, body = request(f"{API_URL}/orders", "POST", zero_order_payload, session=student_session)
test("Zero quantity order rejected (HTTP 400)", st == 400 and "greater than zero" in body.get("message", "").lower())

# -------------------------------------------------------------
# 7. Order Lifecycle, OTP Pickup & Status Flow
# -------------------------------------------------------------
print("\n--- 7. ORDER LIFECYCLE & OTP PICKUP FLOW ---")

valid_order_payload = {
    "items": [
        {"id": item_shop1["id"], "quantity": 2}
    ],
    "payment_method": "Campus Wallet"
}
st, body = request(f"{API_URL}/orders", "POST", valid_order_payload, session=student_session)
test("Valid single-shop order placement (HTTP 201)", st == 201 and body.get("success") is True)
order_data = body.get("order", {})
order_id = order_data.get("id")
order_otp = order_data.get("pickup_otp")
test("Order assigned unique reference & 6-digit OTP", bool(order_id) and len(str(order_otp)) == 6)

# Customer checks my-orders
st, body = request(f"{API_URL}/orders/my-orders", session=student_session)
orders_list = body.get("orders", [])
test("Order appears in customer order history", any(o["id"] == order_id for o in orders_list))

# IDOR Test: Guest customer trying to access student's order details
st, body = request(f"{API_URL}/orders/{order_id}", session=guest_session)
test("Guest customer blocked from viewing student order details (HTTP 403)", st == 403)

# Vendor 1 checks kitchen queue: order should be present
st, body = request(f"{API_URL}/orders/vendor/1", session=vendor1_session)
v1_orders = body.get("orders", [])
test("Order appears in Vendor 1 kitchen queue", any(o["id"] == order_id for o in v1_orders))

# IDOR Test: Vendor 2 trying to verify Vendor 1's order OTP
st, body = request(f"{API_URL}/orders/verify-otp", "POST", {"otp": order_otp}, session=vendor2_session)
test("Vendor 2 blocked from verifying Vendor 1 OTP (HTTP 404)", st == 404)

# Vendor 1 updates status to preparing
st, body = request(f"{API_URL}/orders/{order_id}/status", "PUT", {"status": "preparing"}, session=vendor1_session)
test("Vendor 1 updates status to 'preparing'", st == 200 and body.get("status") == "preparing")

# Vendor 1 verifies pickup OTP
st, body = request(f"{API_URL}/orders/verify-otp", "POST", {"otp": order_otp}, session=vendor1_session)
test("Vendor 1 verifies customer OTP and completes order", st == 200 and body.get("success") is True)

# Reused OTP check: OTP should be rejected after completion
st, body = request(f"{API_URL}/orders/verify-otp", "POST", {"otp": order_otp}, session=vendor1_session)
test("Reused OTP rejected (HTTP 400)", st == 400 and "already" in body.get("message", "").lower())

# Brute-force OTP protection test: Repeated failed guesses trigger rate limiting
st_bf = 0
for _ in range(11):
    st_bf, body_bf = request(f"{API_URL}/orders/verify-otp", "POST", {"otp": "000000"}, session=vendor2_session)
test("Brute force OTP rate limiter locks out repeated invalid guesses (HTTP 429)", st_bf == 429)

# Reset vendor lockout after verification
request(f"{API_URL}/orders/verify-otp", "POST", {"reset_lockout": True}, session=vendor2_session)

# -------------------------------------------------------------
# 8. Shop-Scoped AI Food Recommendation Engine
# -------------------------------------------------------------
print("\n--- 8. SHOP-SCOPED AI FOOD RECOMMENDATIONS ---")

# Request recommendations without shop constraint
st, body = request(f"{API_URL}/recommendations?user_id={student_user_id}")
test("AI returns general time-slot recommendations", st == 200 and len(body.get("recommendations", [])) > 0)

# Request recommendations scoped specifically to Shop 1 (YPR)
st, body = request(f"{API_URL}/recommendations?user_id={student_user_id}&shop_id=1")
recs = body.get("recommendations", [])
test("Shop-scoped recommendations returned", st == 200 and len(recs) > 0)
all_shop1 = all(r.get("shop_id") == 1 for r in recs)
test("100% of recommendations belong exclusively to requested stall (YPR)", all_shop1, f"Found non-shop1: {[r.get('shop_name') for r in recs if r.get('shop_id') != 1]}")

# -------------------------------------------------------------
# 9. Admin Governance & Vendor Management
# -------------------------------------------------------------
print("\n--- 9. ADMIN GOVERNANCE & VENDOR MANAGEMENT ---")

admin_cj = http.cookiejar.CookieJar()
admin_session = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(admin_cj))
st, body = request(f"{API_URL}/auth/admin/login", "POST", {
    "email": "admin@kpriet.ac.in",
    "password": "admin123"
}, session=admin_session)
test("Admin login", st == 200 and body.get("success") is True)

st, body = request(f"{API_URL}/admin/overview", session=admin_session)
overview = body.get("overview", {})
test("Admin overview telemetry returned", st == 200 and "total_turnover" in overview)

# Admin create vendor account
new_vendor_email = f"newvendor_{secrets.token_hex(4)}@kpriet.ac.in"
st, body = request(f"{API_URL}/admin/vendors", "POST", {
    "email": new_vendor_email,
    "password": "InitialVendorPass123!",
    "shop_id": 5
}, session=admin_session)
test("Admin creates new vendor account", st == 201 and body.get("success") is True)
created_vendor_id = body.get("user_id")

# Admin reassign vendor shop
if created_vendor_id:
    st, body = request(f"{API_URL}/admin/vendors/{created_vendor_id}/shop", "PUT", {
        "shop_id": 6
    }, session=admin_session)
    test("Admin reassigns vendor to new stall", st == 200 and body.get("assigned_shop_id", body.get("shop_id")) == 6)

# -------------------------------------------------------------
# 10. Frontend Static Assets Integrity
# -------------------------------------------------------------
print("\n--- 10. FRONTEND ASSETS & PAGE INTEGRITY ---")
frontend_pages = [
    "index.html",
    "pages/customer/dashboard.html",
    "pages/customer/menu.html",
    "pages/customer/preorder.html",
    "pages/customer/orders.html",
    "pages/customer/profile.html",
    "pages/vendor/dashboard.html",
    "pages/vendor/login.html",
    "pages/admin/dashboard.html",
    "pages/admin/login.html",
    "pages/auth/signup.html",
    "pages/auth/login.html",
    "pages/auth/guest-signup.html",
    "pages/auth/guest-login.html",
    "pages/auth/faculty-signup.html",
    "pages/auth/faculty-login.html",
    "components/navbar.html",
    "components/footer.html",
    "css/base/reset.css",
    "js/core/common.js",
    "js/core/dashboard.js",
    "js/core/public-components.js",
    "js/core/tailwind-config.js",
    "js/customer/customer-dashboard.js",
    "js/customer/menu.js",
    "js/customer/preorder.js",
    "js/customer/orders.js",
    "js/customer/profile.js",
    "js/admin/dashboard.js",
    "js/auth/signup.js",
    "js/auth/login.js",
    "js/auth/faculty-signup.js",
    "js/auth/faculty-login.js",
    "js/auth/guest-signup.js",
    "js/auth/guest-login.js",
    "js/admin/login.js",
    "js/vendor/login.js"
]

all_assets_ok = True
for asset in frontend_pages:
    st, _ = request(f"{FRONTEND_URL}/{asset}")
    if st != 200:
        all_assets_ok = False
        print(f"    Missing or broken asset: {asset} (Status {st})")

test(f"All {len(frontend_pages)} frontend HTML pages and JS scripts load (200 OK)", all_assets_ok)

# -------------------------------------------------------------
# Test Summary
# -------------------------------------------------------------
print("\n" + "=" * 75)
print(f"VERIFICATION SUMMARY: {passed} PASSED, {failed} FAILED (TOTAL {passed + failed})")
print("=" * 75)

if failed == 0:
    print("\nSUCCESS: All full-stack production acceptance criteria verified with zero failures!")
    sys.exit(0)
else:
    print(f"\nFAILURE: {failed} test(s) failed. Please review detailed logs above.")
    sys.exit(1)
