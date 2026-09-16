"""
Manual End-to-End Test for Phase 4: Real-World Ordering System.
Simulates the complete real-world food court lifecycle from customer cart to stall pickup:

Customer selects food
↓
Customer adds food to cart
↓
Cart validation (Single-stall rule, stock, price)
↓
Checkout & Order creation
↓
Atomic Stock deduction
↓
Payment processing (Campus Wallet & Server-verified UPI Gateway)
↓
Vendor receives order in kitchen queue
↓
Vendor accepts/prepares order (preparing_time)
↓
Order becomes READY (ready_time)
↓
Customer arrives with secure pickup OTP
↓
Vendor verifies OTP & releases food (completed_time)
↓
Itemized bill & historical price immutability verified
"""

import os
import sys
import json
from decimal import Decimal

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ["FLASK_ENV"] = "development"
os.environ["USE_SQLITE"] = "1"
os.environ["SECRET_KEY"] = "manual-e2e-phase4-secret-key-32b"

import init_db
init_db.init_sqlite()

from app import app
from db import DB
from werkzeug.security import generate_password_hash

print("=================================================================")
print("STARTING PHASE 4 MANUAL END-TO-END VERIFICATION (STEPS 1-16)")
print("=================================================================")

# SETUP USERS & TEST STALLS
cust_email = "e2e.student@kpriet.ac.in"
cust_pwd = "Student@123"
c_user = DB.get_one("SELECT id FROM users WHERE email = %s", (cust_email,))
if not c_user:
    cust_id = DB.execute(
        "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'customer', 1)",
        (cust_email, generate_password_hash(cust_pwd))
    )
    DB.execute(
        "INSERT INTO customer_profiles (user_id, full_name, identifier, customer_type, wallet_balance) "
        "VALUES (%s, 'E2E Student Customer', '22CS888', 'student', 500.00)",
        (cust_id,)
    )
else:
    cust_id = c_user["id"]
    DB.execute("UPDATE users SET password_hash = %s, is_active = 1 WHERE id = %s", (generate_password_hash(cust_pwd), cust_id))
    DB.execute("UPDATE customer_profiles SET wallet_balance = 500.00 WHERE user_id = %s", (cust_id,))

# Ensure YPR Stall & Vendor
vendor_email = "ypr@kpriet.ac.in"
vendor_pwd = "vendor123"
v_user = DB.get_one("SELECT id FROM users WHERE email = %s", (vendor_email,))
vendor_id = v_user["id"]

ypr_shop = DB.get_one("SELECT id FROM shops WHERE name = 'YPR'")
ypr_shop_id = ypr_shop["id"]
DB.execute("UPDATE shops SET owner_user_id = %s, is_active = 1 WHERE id = %s", (vendor_id, ypr_shop_id))

# German Cafe stall (for multi-stall cart test)
gc_shop = DB.get_one("SELECT id FROM shops WHERE name = 'German Cafe'")
gc_shop_id = gc_shop["id"]

# Seed specific test items for E2E run
DB.execute("DELETE FROM menu_items WHERE name IN ('E2E Paneer Wrap', 'E2E Cold Coffee', 'E2E German Croissant')")
item_wrap_id = DB.execute(
    "INSERT INTO menu_items (shop_id, name, price, quantity, category, is_available) "
    "VALUES (%s, 'E2E Paneer Wrap', 90.00, 10, 'Snacks', 1)",
    (ypr_shop_id,)
)
item_coffee_id = DB.execute(
    "INSERT INTO menu_items (shop_id, name, price, quantity, category, is_available) "
    "VALUES (%s, 'E2E Cold Coffee', 45.00, 15, 'Beverages', 1)",
    (ypr_shop_id,)
)
item_croissant_id = DB.execute(
    "INSERT INTO menu_items (shop_id, name, price, quantity, category, is_available) "
    "VALUES (%s, 'E2E German Croissant', 75.00, 8, 'Bakery', 1)",
    (gc_shop_id,)
)

customer_client = app.test_client()
vendor_client = app.test_client()

# STEP 1: Customer Login
print("\n[STEP 1] Customer logs into Food Court mobile/web portal...")
login_res = customer_client.post("/api/auth/customer/login", json={"email": cust_email, "password": cust_pwd})
assert login_res.status_code == 200, f"Customer login failed: {login_res.get_data(as_text=True)}"
prof = DB.get_one("SELECT wallet_balance FROM customer_profiles WHERE user_id = %s", (cust_id,))
print(f"  [OK] Customer logged in successfully. Campus Wallet balance: Rs. {float(prof['wallet_balance']):.2f}")

# STEP 2: Menu stock inspection
print("\n[STEP 2] Customer browses menu & checks live stock...")
menu_res = customer_client.get(f"/api/menu?shop_id={ypr_shop_id}")
assert menu_res.status_code == 200
items = menu_res.get_json()["items"]
wrap_item = next(i for i in items if i["id"] == item_wrap_id)
assert wrap_item["quantity"] == 10, f"Expected 10 in stock, got {wrap_item['quantity']}"
print(f"  [OK] Verified 'E2E Paneer Wrap' is in stock (Qty: {wrap_item['quantity']}, Rs. {wrap_item['price']:.2f})")

# STEP 3: Multi-Stall Cart Validation
print("\n[STEP 3] Customer attempts to combine items from YPR and German Cafe in one cart...")
multi_cart_res = customer_client.post("/api/orders", json={
    "items": [
        {"id": item_wrap_id, "quantity": 1},
        {"id": item_croissant_id, "quantity": 1}
    ],
    "payment_method": "Campus Wallet"
})
assert multi_cart_res.status_code == 400, "Expected single-stall rule violation rejection!"
print(f"  [OK] Backend correctly rejected multi-stall cart: '{multi_cart_res.get_json()['message']}'")

# STEP 4: Quantity Exceeding Stock Validation
print("\n[STEP 4] Customer attempts to order more units than available stock...")
overstock_res = customer_client.post("/api/orders", json={
    "items": [{"id": item_wrap_id, "quantity": 50}],
    "payment_method": "Campus Wallet"
})
assert overstock_res.status_code == 400, "Expected insufficient stock rejection!"
print(f"  [OK] Backend correctly rejected quantity > stock: '{overstock_res.get_json()['message']}'")

# STEP 5: Order Creation & Stock Deduction with Campus Wallet
print("\n[STEP 5] Customer orders: 2x E2E Paneer Wrap (2 * Rs. 90 = Rs. 180) via Campus Wallet...")
wallet_order_res = customer_client.post("/api/orders", json={
    "items": [{"id": item_wrap_id, "quantity": 2}],
    "payment_method": "Campus Wallet"
})
assert wallet_order_res.status_code == 201, f"Order placement failed: {wallet_order_res.get_data(as_text=True)}"
order_1 = wallet_order_res.get_json()["order"]
print(f"  [OK] Order created! Ref: #{order_1['order_reference']}, Total: Rs. {order_1['total_amount']:.2f}")

# STEP 6: Verify Atomic Stock & Wallet Deduction
print("\n[STEP 6] Verify atomic stock decrement and wallet deduction...")
wrap_stock_after = DB.get_one("SELECT quantity FROM menu_items WHERE id = %s", (item_wrap_id,))["quantity"]
assert wrap_stock_after == 8, f"Expected 8 remaining, got {wrap_stock_after}"
wallet_after = DB.get_one("SELECT wallet_balance FROM customer_profiles WHERE user_id = %s", (cust_id,))["wallet_balance"]
assert float(wallet_after) == 320.00, f"Expected 320.00, got {wallet_after}"
print(f"  [OK] Stock decremented from 10 -> {wrap_stock_after}")
print(f"  [OK] Wallet balance deducted from 500.00 -> Rs. {float(wallet_after):.2f}")
print(f"  [OK] Payment Status: '{order_1['payment_status']}' | Pickup OTP: '{order_1['pickup_otp']}'")

# STEP 7: Price Immutability Protection Test
print("\n[STEP 7] Vendor updates current menu item price from Rs. 90 to Rs. 130...")
DB.execute("UPDATE menu_items SET price = 130.00 WHERE id = %s", (item_wrap_id,))
bill_1_res = customer_client.get(f"/api/orders/{order_1['id']}/bill")
assert bill_1_res.status_code == 200
bill_1 = bill_1_res.get_json()["bill"]
assert float(bill_1["total_amount"]) == 180.00, f"Historical total corrupted! Got {bill_1['total_amount']}"
assert float(bill_1["items"][0]["unit_price"]) == 90.00, f"Historical unit price corrupted! Got {bill_1['items'][0]['unit_price']}"
print(f"  [OK] Immutability verified: Current menu is Rs. 130, but historical bill retains Rs. {bill_1['total_amount']:.2f} (unit price: Rs. {bill_1['items'][0]['unit_price']:.2f})")
DB.execute("UPDATE menu_items SET price = 90.00 WHERE id = %s", (item_wrap_id,))

# STEP 8: Place Order via UPI / Online
print("\n[STEP 8] Customer places second order: 1x E2E Cold Coffee (Rs. 45) via UPI / Online...")
upi_order_res = customer_client.post("/api/orders", json={
    "items": [{"id": item_coffee_id, "quantity": 1}],
    "payment_method": "UPI / Online"
})
assert upi_order_res.status_code == 201
order_2 = upi_order_res.get_json()["order"]
print(f"  [OK] Order created! Ref: #{order_2['order_reference']}, Total: Rs. {order_2['total_amount']:.2f}")

# STEP 9: Verify Server Gateway Pending Lifecycle
print("\n[STEP 9] Verify online order starts as 'pending' with server-signed token...")
assert order_2["payment_status"] == "pending", f"Expected payment_status 'pending', got {order_2['payment_status']}"
gateway_token = order_2["payment"]["gateway_token"]
assert gateway_token is not None and len(gateway_token) > 10
print(f"  [OK] Verified payment_status is 'pending'. Cryptographic Gateway Token issued: {gateway_token[:25]}...")

# STEP 10: Reject Fake / Spoofed Payment Confirmation
print("\n[STEP 10] Client attempts to spoof payment with forged token...")
fake_pay_res = customer_client.post(f"/api/orders/{order_2['id']}/confirm-payment", json={
    "gateway_token": "tampered_fake_signature_token_12345",
    "transaction_id": "FAKE-TXN-001"
})
assert fake_pay_res.status_code == 400
print(f"  [OK] Backend rejected forged payment confirmation: '{fake_pay_res.get_json()['message']}'")

# STEP 11: Valid Server-Side Gateway Confirmation
print("\n[STEP 11] Payment Gateway webhook/confirm verifies signed token on backend...")
real_pay_res = customer_client.post(f"/api/orders/{order_2['id']}/confirm-payment", json={
    "gateway_token": gateway_token,
    "transaction_id": "UPI-GATEWAY-TXN-998877"
})
assert real_pay_res.status_code == 200
print(f"  [OK] Server verified payment: '{real_pay_res.get_json()['message']}'")
db_order_2 = DB.get_one("SELECT payment_status, payment_time FROM orders WHERE id = %s", (order_2['id'],))
assert db_order_2["payment_status"] == "paid"
assert db_order_2["payment_time"] is not None
print(f"  [OK] Database confirmed: payment_status = 'paid' (Timestamp: {db_order_2['payment_time']})")

# STEP 12: Stall Vendor Kitchen Queue
print("\n[STEP 12] YPR Vendor logs into kitchen terminal...")
v_res = vendor_client.post("/api/auth/vendor/login", json={"email": vendor_email, "password": vendor_pwd})
assert v_res.status_code == 200
queue_res = vendor_client.get(f"/api/orders/vendor/{ypr_shop_id}")
assert queue_res.status_code == 200
active_orders = queue_res.get_json()["orders"]
active_ids = [o["id"] for o in active_orders]
assert order_2["id"] in active_ids, "Order 2 missing from kitchen queue!"
print(f"  [OK] Vendor logged in. Live Kitchen Queue contains {len(active_orders)} order(s).")

# STEP 13: Vendor transitions order to 'preparing'
print("\n[STEP 13] Vendor accepts order and marks 'preparing'...")
prep_res = vendor_client.put(f"/api/orders/{order_2['id']}/status", json={"status": "preparing"})
assert prep_res.status_code == 200
db_prep = DB.get_one("SELECT order_status, preparing_time FROM orders WHERE id = %s", (order_2['id'],))
assert db_prep["order_status"] == "preparing"
assert db_prep["preparing_time"] is not None
print(f"  [OK] Order status updated to 'preparing' (Recorded at: {db_prep['preparing_time']})")

# STEP 14: Vendor transitions order to 'ready'
print("\n[STEP 14] Food is cooked! Vendor marks order 'ready' for pickup...")
ready_res = vendor_client.put(f"/api/orders/{order_2['id']}/status", json={"status": "ready"})
assert ready_res.status_code == 200
db_ready = DB.get_one("SELECT order_status, ready_time FROM orders WHERE id = %s", (order_2['id'],))
assert db_ready["order_status"] == "ready"
assert db_ready["ready_time"] is not None
print(f"  [OK] Order status updated to 'ready' (Notification broadcast at: {db_ready['ready_time']})")

# STEP 15: Customer arrives at stall counter & presents pickup OTP
print(f"\n[STEP 15] Customer arrives at stall counter with OTP: '{order_2['pickup_otp']}'...")
verify_otp_res = vendor_client.post("/api/orders/verify-otp", json={
    "otp": order_2["pickup_otp"],
    "shop_id": ypr_shop_id
})
assert verify_otp_res.status_code == 200, f"OTP verification failed: {verify_otp_res.get_data(as_text=True)}"
db_done = DB.get_one("SELECT order_status, completed_time FROM orders WHERE id = %s", (order_2['id'],))
assert db_done["order_status"] == "completed"
assert db_done["completed_time"] is not None
print(f"  [OK] Vendor verified OTP! Order fulfilled & completed (Handed over at: {db_done['completed_time']})")

# STEP 16: Final Itemized Tax Bill & Receipt
print("\n[STEP 16] Customer views official tax invoice and audit trail...")
final_bill_res = customer_client.get(f"/api/orders/{order_2['id']}/bill")
assert final_bill_res.status_code == 200
final_bill = final_bill_res.get_json()["bill"]

assert final_bill["order_status"] == "completed"
assert final_bill["payment_status"] == "paid"
assert final_bill["shop_name"] == "YPR"
assert float(final_bill["total_amount"]) == 45.00
assert len(final_bill["items"]) == 1
assert final_bill["items"][0]["item_name"] == "E2E Cold Coffee"
ts = final_bill["timestamps"]
assert ts["order_time"] is not None
assert ts["payment_time"] is not None
assert ts["preparing_time"] is not None
assert ts["ready_time"] is not None
assert ts["completed_time"] is not None

print(f"  [OK] Bill Reference: #{final_bill['order_reference']}")
print(f"  [OK] Total Paid: Rs. {final_bill['total_amount']:.2f} ({final_bill['payment_method']})")
print(f"  [OK] Order Timestamps Trail:")
print(f"       - Order Placed:    {ts['order_time']}")
print(f"       - Payment Verified: {ts['payment_time']}")
print(f"       - Preparation:     {ts['preparing_time']}")
print(f"       - Ready for Pickup:{ts['ready_time']}")
print(f"       - Handover (OTP):  {ts['completed_time']}")

print("\n=================================================================")
print("ALL 16 STEPS OF PHASE 4 REAL-WORLD E2E PASSED PERFECTLY!")
print("=================================================================")
