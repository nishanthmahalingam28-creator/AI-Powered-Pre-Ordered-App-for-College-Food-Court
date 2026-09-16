"""
Manual End-to-End Test for Phase 3: Shop & Menu Management.
Follows the exact 14-step real-world flow from Section 25.
"""

import os
import sys
import json

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ["FLASK_ENV"] = "development"
os.environ["USE_SQLITE"] = "1"
os.environ["SECRET_KEY"] = "manual-e2e-phase3-secret-key-32b"

from app import app
from db import DB

client = app.test_client()

print("=================================================================")
print("STARTING MANUAL END-TO-END FLOW (STEPS 1-14)")
print("=================================================================")

# STEP 1: Login as admin
print("\n[STEP 1] Login as admin...")
admin_resp = client.post("/api/auth/admin/login", json={
    "email": "admin@kpriet.ac.in",
    "password": "admin123"
})
assert admin_resp.status_code == 200, f"Admin login failed: {admin_resp.get_data(as_text=True)}"
print("  [OK] Admin logged in successfully.")

# STEP 2: Verify YPR, German Cafe, Royal Kitchen, Mario, Saaral exist
print("\n[STEP 2] Verify required shops exist...")
shops_resp = client.get("/api/shops")
assert shops_resp.status_code == 200
shops = shops_resp.get_json()["shops"]
shop_names = [s["name"] for s in shops]
required_shops = ["YPR", "German Cafe", "Royal Kitchen", "Mario", "Saaral"]
for r in required_shops:
    assert r in shop_names, f"Shop '{r}' missing from active shops list!"
    print(f"  [OK] Verified shop '{r}' exists and is active.")

# STEP 3: Login as Vendor A assigned to YPR
print("\n[STEP 3] Login as Vendor A assigned to YPR...")
vendor_client = app.test_client()
v_login = vendor_client.post("/api/auth/vendor/login", json={
    "email": "ypr@kpriet.ac.in",
    "password": "vendor123"
})
assert v_login.status_code == 200, f"Vendor A login failed: {v_login.get_data(as_text=True)}"
v_data = v_login.get_json()
assert v_data["user"]["shop_name"] == "YPR", f"Expected YPR shop assignment, got {v_data['user'].get('shop_name')}"
print("  [OK] Vendor A (YPR) logged in successfully with assigned stall.")

# STEP 4: Add: Test Food Item, Price = Rs. 50, Stock = 20
print("\n[STEP 4] Vendor A adds 'Test Food Item', Price = Rs. 50, Stock = 20...")
add_resp = vendor_client.post("/api/vendor/menu/item", json={
    "name": "Test Food Item",
    "price": 50.00,
    "quantity": 20,
    "category": "Food",
    "description": "Delicious test dish",
    "available": True
})
assert add_resp.status_code == 201, f"Failed to add item: {add_resp.get_data(as_text=True)}"
item_id = add_resp.get_json()["item"]["id"]
print(f"  [OK] 'Test Food Item' created with ID #{item_id}, Price = Rs. 50.00, Stock = 20.")

# STEP 5 & 6: Open customer menu & Select YPR
print("\n[STEP 5 & 6] Open customer menu and select YPR...")
ypr_shop = next(s for s in shops if s["name"] == "YPR")
cust_client = app.test_client()
menu_resp = cust_client.get(f"/api/menu?shop_id={ypr_shop['id']}")
assert menu_resp.status_code == 200
ypr_items = menu_resp.get_json()["items"]
print(f"  [OK] Fetched {len(ypr_items)} dishes from YPR stall.")

# STEP 7: Verify Test Food Item appears
print("\n[STEP 7] Verify 'Test Food Item' appears on customer menu...")
found_item = next((i for i in ypr_items if i["id"] == item_id), None)
assert found_item is not None, "Test Food Item was not found in YPR menu!"
assert float(found_item["price"]) == 50.00
assert found_item["quantity"] == 20
assert found_item["is_available"] == 1
print(f"  [OK] 'Test Food Item' appears on customer menu: Price = Rs. {found_item['price']}, Stock = {found_item['quantity']}.")

# STEP 8: Vendor changes price: Rs. 50 -> Rs. 60
print("\n[STEP 8] Vendor changes price: Rs. 50 -> Rs. 60...")
price_update = vendor_client.put(f"/api/vendor/menu/item/{item_id}", json={
    "price": 60.00
})
assert price_update.status_code == 200
print("  [OK] Price update succeeded in database.")

# STEP 9 & 10: Refresh customer menu & Verify customer sees Rs. 60
print("\n[STEP 9 & 10] Refresh customer menu and verify price Rs. 60...")
refresh_resp = cust_client.get(f"/api/menu/{item_id}")
assert refresh_resp.status_code == 200
refreshed_item = refresh_resp.get_json()["item"]
assert float(refreshed_item["price"]) == 60.00, f"Expected 60.00, got {refreshed_item['price']}"
print(f"  [OK] Customer menu immediately reflects updated price: Rs. {refreshed_item['price']}.")

# STEP 11: Vendor changes stock: 20 -> 0
print("\n[STEP 11] Vendor changes stock: 20 -> 0...")
stock_update = vendor_client.put(f"/api/vendor/menu/item/{item_id}", json={
    "quantity": 0,
    "available": False
})
assert stock_update.status_code == 200
print("  [OK] Stock update succeeded in database.")

# STEP 12: Customer sees OUT OF STOCK
print("\n[STEP 12] Customer sees OUT OF STOCK...")
stock_resp = cust_client.get(f"/api/menu/{item_id}")
assert stock_resp.status_code == 200
depleted_item = stock_resp.get_json()["item"]
assert depleted_item["quantity"] == 0
assert depleted_item["is_available"] == 0
print(f"  [OK] Customer menu reflects stock = {depleted_item['quantity']}, is_available = {depleted_item['is_available']} (OUT OF STOCK).")

# STEP 13: Attempt ordering the item -> Order rejected because item is out of stock
print("\n[STEP 13] Customer attempts ordering out-of-stock item...")
# Login customer
cust_login = cust_client.post("/api/auth/customer/login", json={
    "email": "student@kpriet.ac.in",
    "password": "password123",
    "customerType": "student"
})
assert cust_login.status_code == 200

order_attempt = cust_client.post("/api/orders", json={
    "items": [{"id": item_id, "quantity": 1}],
    "payment_method": "Campus Wallet"
})
assert order_attempt.status_code == 400, f"Expected 400 rejection, got {order_attempt.status_code}"
order_err = order_attempt.get_json()
assert not order_err["success"]
assert "out of stock" in order_err["message"].lower()
print(f"  [OK] Order securely rejected: '{order_err['message']}'.")

# STEP 14: Attempt to modify a Royal Kitchen item using YPR vendor credentials -> 403 Forbidden
print("\n[STEP 14] Vendor A (YPR) attempts to modify Royal Kitchen item...")
rk_shop = next(s for s in shops if s["name"] == "Royal Kitchen")
rk_menu = cust_client.get(f"/api/menu?shop_id={rk_shop['id']}").get_json()["items"]
assert len(rk_menu) > 0
rk_item = rk_menu[0]

idor_attempt = vendor_client.put(f"/api/vendor/menu/item/{rk_item['id']}", json={
    "price": 1.00
})
assert idor_attempt.status_code == 403, f"Expected 403 Forbidden, got {idor_attempt.status_code}"
idor_data = idor_attempt.get_json()
assert not idor_data["success"]
print(f"  [OK] IDOR attack prevented: HTTP {idor_attempt.status_code} - '{idor_data['message']}'.")

print("\n=================================================================")
print("ALL 14 MANUAL END-TO-END STEPS PASSED PERFECTLY!")
print("=================================================================")
