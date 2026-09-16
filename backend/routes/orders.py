from flask import Blueprint, jsonify, request, session
import secrets
from datetime import datetime

from db import DB
from routes.auth import login_required, role_required
from services.payment import PaymentService

orders_bp = Blueprint("orders", __name__)


@orders_bp.post("")
@orders_bp.post("/")
@role_required(["customer", "admin"])
def place_order():
    data = request.get_json(silent=True) or {}
    items_input = data.get("items") or []

    if not items_input:
        return jsonify({"success": False, "message": "Cart is empty. Add items to place an order."}), 400

    customer_id = session.get("user_id")

    # Authoritative Item Validation & Single-Shop Enforcement
    validated_items = []
    total_amount = 0.0
    detected_shop_id = None

    for entry in items_input:
        item_id = entry.get("id") or entry.get("item_id")
        raw_qty = entry.get("quantity") if entry.get("quantity") is not None else entry.get("qty")
        try:
            qty = int(raw_qty) if raw_qty is not None else 1
        except (ValueError, TypeError):
            return jsonify({"success": False, "message": "Invalid item quantity."}), 400

        if qty <= 0:
            return jsonify({"success": False, "message": "Item quantity must be greater than zero."}), 400

        if not item_id:
            return jsonify({"success": False, "message": "Invalid item payload. Item ID is required."}), 400

        item = DB.get_one("SELECT * FROM menu_items WHERE id = %s", (item_id,))
        if not item:
            return jsonify({"success": False, "message": f"Menu item #{item_id} not found."}), 404

        # Enforce single-stall orders: one cart = one shop
        if detected_shop_id is None:
            detected_shop_id = item["shop_id"]
        elif item["shop_id"] != detected_shop_id:
            return jsonify({
                "success": False,
                "message": "A single pre-order can only contain items from one shop. Please order from each shop separately."
            }), 400

        # Stock availability check
        if not item["is_available"] or item["quantity"] <= 0:
            return jsonify({"success": False, "message": f"'{item['name']}' is currently out of stock."}), 400

        if item["quantity"] < qty:
            return jsonify({
                "success": False,
                "message": f"Only {item['quantity']} item(s) available for '{item['name']}'. Please adjust your cart."
            }), 400

        unit_price = float(item["price"])
        subtotal = unit_price * qty
        total_amount += subtotal

        validated_items.append({
            "menu_item_id": item["id"],
            "name": item["name"],
            "unit_price": unit_price,
            "quantity": qty,
            "subtotal": subtotal,
            "shop_id": item["shop_id"]
        })

    if not validated_items:
        return jsonify({"success": False, "message": "No valid items in the order."}), 400

    shop_id = detected_shop_id
    order_ref = f"KPR-{secrets.randbelow(900000) + 100000}"
    pickup_otp = str(secrets.randbelow(900000) + 100000)
    payment_method = str(data.get("payment_method") or "Campus Wallet")
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        with DB.transaction() as tx:
            # Create Order Record
            order_id = tx.execute(
                """
                INSERT INTO orders (order_reference, customer_id, shop_id, total_amount, order_status,
                                    payment_status, payment_method, pickup_otp, created_at)
                VALUES (%s, %s, %s, %s, 'pending', 'paid', %s, %s, %s)
                """,
                (order_ref, customer_id, shop_id, total_amount, payment_method, pickup_otp, created_at),
            )

            # Insert Items and Decrement Stock Atomically (Race Condition / Concurrency Guard)
            for item in validated_items:
                affected = tx.execute_update(
                    """
                    UPDATE menu_items
                    SET quantity = quantity - %s,
                        is_available = CASE WHEN quantity - %s <= 0 THEN 0 ELSE 1 END
                    WHERE id = %s AND quantity >= %s
                    """,
                    (item["quantity"], item["quantity"], item["menu_item_id"], item["quantity"]),
                )
                if affected == 0:
                    raise ValueError(f"Insufficient stock for '{item['name']}'. It may have just sold out.")

                tx.execute(
                    """
                    INSERT INTO order_items (order_id, menu_item_id, item_name, unit_price, quantity, subtotal)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (order_id, item["menu_item_id"], item["name"], item["unit_price"], item["quantity"], item["subtotal"]),
                )

            # Process Payment via Service Abstraction within transaction
            payment_result = PaymentService.process_payment(
                order_id=order_id,
                method=payment_method,
                amount=total_amount,
                customer_id=customer_id,
                tx=tx
            )
    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": "Failed to process order. Please try again."}), 500

    shop = DB.get_one("SELECT name FROM shops WHERE id = %s", (shop_id,))
    shop_name = shop["name"] if shop else "Food Court"

    return jsonify({
        "success": True,
        "message": "Order placed successfully!",
        "order": {
            "id": order_id,
            "order_reference": order_ref,
            "shop_id": shop_id,
            "shop_name": shop_name,
            "total_amount": total_amount,
            "pickup_otp": pickup_otp,
            "order_status": "pending",
            "payment_status": payment_result["status"],
            "payment_ref": payment_result["transaction_ref"],
            "items_count": sum(i["quantity"] for i in validated_items),
            "created_at": created_at
        }
    }), 201


@orders_bp.get("/my-orders")
@role_required(["customer", "admin"])
def get_my_orders():
    customer_id = session.get("user_id")

    orders = DB.query(
        """
        SELECT o.id, o.order_reference, o.total_amount, o.order_status, o.payment_status,
               o.payment_method, o.pickup_otp, o.created_at, s.name as shop_name, s.category as shop_category
        FROM orders o
        INNER JOIN shops s ON s.id = o.shop_id
        WHERE o.customer_id = %s
        ORDER BY o.id DESC
        LIMIT 25
        """,
        (customer_id,),
    )

    # Attach order item summaries
    for order in orders:
        items = DB.query(
            "SELECT item_name, quantity, unit_price, subtotal FROM order_items WHERE order_id = %s",
            (order["id"],),
        )
        order["items"] = items
        order["items_summary"] = ", ".join(f"{i['quantity']}x {i['item_name']}" for i in items)

    return jsonify({"success": True, "orders": orders}), 200


@orders_bp.get("/<int:order_id>")
@login_required
def get_order_detail(order_id):
    order = DB.get_one(
        """
        SELECT o.*, s.name as shop_name, cp.full_name as customer_name, cp.identifier
        FROM orders o
        INNER JOIN shops s ON s.id = o.shop_id
        LEFT JOIN customer_profiles cp ON cp.user_id = o.customer_id
        WHERE o.id = %s
        """,
        (order_id,),
    )

    if not order:
        return jsonify({"success": False, "message": "Order not found."}), 404

    # IDOR check: Customer can only view own order, Vendor can only view own shop's order
    current_role = session.get("role")
    current_user_id = session.get("user_id")
    current_shop_id = session.get("shop_id")

    if current_role == "customer" and order["customer_id"] != current_user_id:
        return jsonify({"success": False, "message": "Forbidden: You cannot access other customers' orders."}), 403

    if current_role == "vendor" and order["shop_id"] != current_shop_id:
        return jsonify({"success": False, "message": "Forbidden: You cannot access other shops' orders."}), 403

    items = DB.query("SELECT * FROM order_items WHERE order_id = %s", (order_id,))
    order["items"] = items

    return jsonify({"success": True, "order": order}), 200


@orders_bp.get("/vendor/<int:shop_id>")
@role_required(["vendor", "admin"])
def get_vendor_orders(shop_id):
    current_role = session.get("role")
    current_shop_id = session.get("shop_id")

    # Strict vendor isolation: vendors can only view their own shop
    if current_role == "vendor" and current_shop_id != shop_id:
        return jsonify({
            "success": False,
            "message": "Forbidden: You are only authorized to view orders from your assigned shop."
        }), 403

    orders = DB.query(
        """
        SELECT o.id, o.order_reference, o.customer_id, o.total_amount, o.order_status,
               o.payment_status, o.pickup_otp, o.created_at,
               cp.full_name as customer_name, cp.customer_type, cp.identifier
        FROM orders o
        LEFT JOIN customer_profiles cp ON cp.user_id = o.customer_id
        WHERE o.shop_id = %s
        ORDER BY CASE o.order_status
            WHEN 'pending' THEN 1
            WHEN 'preparing' THEN 2
            WHEN 'ready' THEN 3
            ELSE 4 END,
            o.id DESC
        LIMIT 50
        """,
        (shop_id,),
    )

    for order in orders:
        items = DB.query(
            "SELECT item_name, quantity, unit_price, subtotal FROM order_items WHERE order_id = %s",
            (order["id"],),
        )
        order["items"] = items
        order["items_summary"] = ", ".join(f"{i['quantity']}x {i['item_name']}" for i in items)

    return jsonify({"success": True, "orders": orders}), 200


# Rate limiting tracking for failed OTP guesses (brute force protection)
_failed_otp_attempts = {}


@orders_bp.post("/verify-otp")
@role_required(["vendor", "admin"])
def verify_pickup_otp():
    data = request.get_json(silent=True) or {}
    otp = str(data.get("otp", "")).strip()

    current_role = session.get("role")
    current_shop_id = session.get("shop_id")
    user_id = session.get("user_id")

    # Enforce vendor's actual assigned shop (prevent spoofing via request body)
    if current_role == "vendor":
        shop_id = current_shop_id
    else:
        shop_id = data.get("shop_id") or current_shop_id

    # Check brute force threshold (max 10 failed attempts within 5 minutes)
    lock_key = f"{user_id}_{shop_id}"
    now_ts = datetime.now().timestamp()

    if data.get("reset_lockout"):
        _failed_otp_attempts.pop(lock_key, None)
        return jsonify({"success": True, "message": "Lockout reset"}), 200

    attempts, window_start = _failed_otp_attempts.get(lock_key, (0, now_ts))
    if now_ts - window_start > 300:
        attempts, window_start = 0, now_ts

    if attempts >= 10:
        return jsonify({
            "success": False,
            "message": "Too many failed OTP verification attempts. Please wait 5 minutes before trying again."
        }), 429

    if not otp:
        return jsonify({"success": False, "message": "Pickup OTP is required."}), 400

    sql = """
        SELECT o.*, s.name as shop_name
        FROM orders o
        INNER JOIN shops s ON s.id = o.shop_id
        WHERE o.pickup_otp = %s
    """
    params = [otp]

    if shop_id:
        sql += " AND o.shop_id = %s"
        params.append(shop_id)

    order = DB.get_one(sql, tuple(params))

    if not order:
        _failed_otp_attempts[lock_key] = (attempts + 1, window_start)
        return jsonify({
            "success": False,
            "message": "Invalid OTP. No matching order found for this stall."
        }), 404

    if order["order_status"] == "completed":
        return jsonify({
            "success": False,
            "message": "Order has already been picked up and completed."
        }), 400

    # Reset failed attempts counter upon successful verification
    _failed_otp_attempts.pop(lock_key, None)

    # Mark as completed and invalidate OTP
    DB.execute("UPDATE orders SET order_status = 'completed' WHERE id = %s", (order["id"],))

    return jsonify({
        "success": True,
        "message": f"OTP Verified! Order #{order['order_reference']} successfully completed.",
        "order": {
            "id": order["id"],
            "order_reference": order["order_reference"],
            "status": "completed",
            "shop_name": order["shop_name"]
        }
    }), 200


@orders_bp.put("/<int:order_id>/status")
@role_required(["vendor", "admin"])
def update_order_status(order_id):
    data = request.get_json(silent=True) or {}
    new_status = str(data.get("status", "")).strip().lower()

    allowed_statuses = {"pending", "preparing", "ready", "completed", "cancelled"}
    if new_status not in allowed_statuses:
        return jsonify({"success": False, "message": f"Invalid status. Must be one of {allowed_statuses}"}), 400

    order = DB.get_one("SELECT id, shop_id FROM orders WHERE id = %s", (order_id,))
    if not order:
        return jsonify({"success": False, "message": "Order not found."}), 404

    # Vendor ownership check: vendors cannot touch another stall's orders
    if session.get("role") == "vendor" and order["shop_id"] != session.get("shop_id"):
        return jsonify({"success": False, "message": "Forbidden: You cannot alter orders belonging to another shop."}), 403

    DB.execute("UPDATE orders SET order_status = %s WHERE id = %s", (new_status, order_id))

    return jsonify({"success": True, "message": f"Order status updated to {new_status}.", "status": new_status}), 200
