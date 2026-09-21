import logging
import secrets
from datetime import datetime
from flask import Blueprint, jsonify, request, session

from db import DB
from routes.auth import login_required, role_required
from services.payment import PaymentService
from services.audit import AuditService
from services.notification import NotificationService
from realtime import emit_order_created, emit_order_status, emit_order_cancelled

logger = logging.getLogger("food_court.orders")
orders_bp = Blueprint("orders", __name__)


@orders_bp.post("")
@orders_bp.post("/")
@orders_bp.post("/place")
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
        item_id = entry.get("id") or entry.get("item_id") or entry.get("menu_item_id")
        raw_qty = entry.get("quantity") if entry.get("quantity") is not None else entry.get("qty")
        try:
            qty = int(raw_qty) if raw_qty is not None else 1
        except (ValueError, TypeError):
            return jsonify({"success": False, "message": "Invalid item quantity."}), 400

        if qty <= 0:
            return jsonify({"success": False, "message": "Item quantity must be greater than zero."}), 400

        if not item_id:
            return jsonify({"success": False, "message": "Invalid item payload. Item ID is required."}), 400

        item = DB.get_one(
            """
            SELECT m.*, s.name as shop_name, s.is_active as shop_is_active, s.operational_status as shop_operational_status
            FROM menu_items m
            INNER JOIN shops s ON s.id = m.shop_id
            WHERE m.id = %s
            """,
            (item_id,)
        )
        if not item:
            return jsonify({"success": False, "message": f"Menu item #{item_id} not found."}), 404

        op_status = str(item.get("shop_operational_status") or "OPEN").upper()
        if not item.get("shop_is_active") or op_status != "OPEN":
            status_desc = "closed or temporarily unavailable" if op_status in ("CLOSED", "TEMPORARILY_UNAVAILABLE") else "closed or inactive"
            return jsonify({
                "success": False,
                "message": f"Stall '{item['shop_name']}' is currently {status_desc}. Orders cannot be placed."
            }), 400

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
            "meal_period": str(item.get("meal_period") or "lunch").lower(),
            "shop_id": item["shop_id"]
        })

    if not validated_items:
        return jsonify({"success": False, "message": "No valid items in the order."}), 400

    shop_id = detected_shop_id
    order_ref = f"KPR-{secrets.randbelow(900000) + 100000}"
    pickup_otp = str(secrets.randbelow(900000) + 100000)
    raw_method = str(data.get("payment_method") or "Pay at Counter")
    _, payment_method_label = PaymentService.normalize_method(raw_method)

    try:
        with DB.transaction() as tx:
            # 1. Create Order Record with pending payment_status by default
            order_id = tx.execute(
                """
                INSERT INTO orders (order_reference, customer_id, shop_id, total_amount, order_status,
                                    payment_status, payment_method, pickup_otp, created_at)
                VALUES (%s, %s, %s, %s, 'pending', 'pending', %s, %s, UTC_TIMESTAMP())
                """,
                (order_ref, customer_id, shop_id, total_amount, payment_method_label, pickup_otp),
            )

            # 2. Insert Items and Decrement Stock Atomically (Race Condition / Concurrency Guard)
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
                    INSERT INTO order_items
                        (order_id, menu_item_id, item_name, meal_period, unit_price, quantity, subtotal)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        order_id,
                        item["menu_item_id"],
                        item["name"],
                        item.get("meal_period") or "lunch",
                        item["unit_price"],
                        item["quantity"],
                        item["subtotal"],
                    ),
                )

            # 3. Process Payment via Service Abstraction within transaction
            # Campus Wallet: verified & deducted server-side atomically
            # UPI/Online: initiated as pending with gateway_token
            # Cash: initiated as pending
            payment_result = PaymentService.process_payment(
                order_id=order_id,
                method=raw_method,
                amount=total_amount,
                customer_id=customer_id,
                tx=tx
            )
    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        logger.error("Order placement error for customer_id=%s: %s: %s", customer_id, type(e).__name__, str(e))
        return jsonify({"success": False, "message": "Failed to process order. Please try again."}), 500

    created_row = DB.get_one("SELECT created_at FROM orders WHERE id = %s", (order_id,))
    created_at = str(created_row["created_at"]) if created_row and created_row.get("created_at") else None

    shop = DB.get_one("SELECT name FROM shops WHERE id = %s", (shop_id,))
    shop_name = shop["name"] if shop else "Food Court"

    # Automatically clear user's database shopping cart upon successful order placement
    try:
        DB.execute("DELETE FROM cart_items WHERE user_id = %s", (customer_id,))
    except Exception as ce:
        logger.warning("Failed to clear database cart for user #%s: %s", customer_id, ce)

    # Dispatch persistent notifications safely (non-blocking)
    try:
        NotificationService.notify_customer(
            customer_id=customer_id,
            notif_type="ORDER_PLACED",
            title=f"Order Placed #{order_ref}",
            message=f"Your order at {shop_name} for ₹{total_amount:.2f} has been placed successfully.",
            order_id=order_id
        )
        NotificationService.notify_vendor(
            shop_id=shop_id,
            notif_type="ORDER_PLACED",
            title=f"New Order #{order_ref}",
            message=f"New order received ({sum(i['quantity'] for i in validated_items)} items, ₹{total_amount:.2f}).",
            order_id=order_id
        )
        if payment_result.get("status") == "paid":
            NotificationService.notify_customer(
                customer_id=customer_id,
                notif_type="PAYMENT_SUCCESS",
                title=f"Payment Successful #{order_ref}",
                message=f"Payment of ₹{total_amount:.2f} via {payment_result.get('method', payment_method_label)} was successful.",
                order_id=order_id
            )
    except Exception as ne:
        logger.warning("Notification dispatch failed in place_order (non-fatal): %s", ne)

    # Push the committed order to the vendor/customer browsers immediately.
    # This is deliberately after the DB transaction succeeds, so clients never
    # receive a real-time order that was rolled back.
    try:
        emit_order_created({
            "id": order_id,
            "order_reference": order_ref,
            "customer_id": customer_id,
            "shop_id": shop_id,
            "shop_name": shop_name,
            "total_amount": total_amount,
            "order_status": "pending",
            "payment_status": payment_result.get("status"),
            "items_count": sum(i["quantity"] for i in validated_items),
            "created_at": created_at,
        })
    except Exception as re:
        logger.warning("Realtime order-created dispatch failed (non-fatal): %s", re)

    return jsonify({
        "success": True,
        "message": "Order placed successfully!",
        "order": {
            "id": order_id,
            "order_id": order_id,
            "order_reference": order_ref,
            "shop_id": shop_id,
            "shop_name": shop_name,
            "total_amount": total_amount,
            "pickup_otp": pickup_otp,
            "order_status": "pending",
            "payment_status": payment_result["status"],
            "payment_ref": payment_result.get("transaction_ref"),
            "gateway_token": payment_result.get("gateway_token"),
            "gateway_order_id": payment_result.get("gateway_order_id"),
            "razorpay_order_id": payment_result.get("razorpay_order_id"),
            "key_id": payment_result.get("key_id"),
            "amount_paise": payment_result.get("amount_paise", int(round(total_amount * 100))),
            "currency": payment_result.get("currency", "INR"),
            "payment_method": payment_result.get("method", payment_method_label),
            "payment": {
                "payment_id": payment_result.get("payment_id"),
                "payment_status": payment_result.get("status"),
                "gateway_token": payment_result.get("gateway_token"),
                "gateway_order_id": payment_result.get("gateway_order_id"),
                "razorpay_order_id": payment_result.get("razorpay_order_id"),
                "key_id": payment_result.get("key_id"),
                "amount_paise": payment_result.get("amount_paise", int(round(total_amount * 100))),
                "currency": payment_result.get("currency", "INR")
            },
            "items_count": sum(i["quantity"] for i in validated_items),
            "created_at": created_at
        }
    }), 201


@orders_bp.post("/<int:order_id>/verify-payment")
@role_required(["customer", "admin"])
def verify_order_payment(order_id):
    """
    CRITICAL: Official server-side payment verification endpoint for Razorpay Checkout.
    Validates razorpay_order_id, razorpay_payment_id, and cryptographic razorpay_signature.
    """
    data = request.get_json(silent=True) or {}
    gateway_order_id = str(data.get("razorpay_order_id") or data.get("gateway_order_id") or "").strip()
    gateway_payment_id = str(data.get("razorpay_payment_id") or data.get("gateway_payment_id") or "").strip()
    gateway_signature = str(data.get("razorpay_signature") or data.get("gateway_signature") or "").strip()

    if not gateway_order_id or not gateway_payment_id or not gateway_signature:
        return jsonify({
            "success": False,
            "message": "Payment verification requires razorpay_order_id, razorpay_payment_id, and razorpay_signature."
        }), 400

    customer_id = session.get("user_id") if session.get("role") == "customer" else None

    try:
        with DB.transaction() as tx:
            result = PaymentService.verify_gateway_payment(
                order_id=order_id,
                gateway_order_id=gateway_order_id,
                gateway_payment_id=gateway_payment_id,
                gateway_signature=gateway_signature,
                customer_id=customer_id,
                tx=tx
            )
        return jsonify({
            "success": True,
            "message": result["message"],
            "status": "paid",
            "payment_status": "paid",
            "order_id": order_id,
            "transaction_ref": gateway_payment_id
        }), 200
    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400
    except PermissionError as pe:
        return jsonify({"success": False, "message": str(pe)}), 403
    except Exception as e:
        logger.error("Payment verification error for order %s: %s", order_id, e)
        return jsonify({"success": False, "message": "Failed to verify payment."}), 500


@orders_bp.post("/<int:order_id>/confirm-payment")
@role_required(["customer", "admin"])
def confirm_order_payment(order_id):
    """
    Backwards-compatible payment confirmation endpoint.
    Accepts either Razorpay signature credentials or legacy HMAC server tokens.
    """
    data = request.get_json(silent=True) or {}
    tx_ref = str(data.get("transaction_ref") or data.get("transaction_id") or "").strip()
    gateway_token = str(data.get("gateway_token") or data.get("token") or "").strip()
    gateway_order_id = str(data.get("razorpay_order_id") or data.get("gateway_order_id") or "").strip()
    gateway_payment_id = str(data.get("razorpay_payment_id") or data.get("gateway_payment_id") or tx_ref).strip()
    gateway_signature = str(data.get("razorpay_signature") or data.get("gateway_signature") or "").strip()

    if not gateway_signature and (not tx_ref or not gateway_token):
        return jsonify({
            "success": False,
            "message": "Payment confirmation requires transaction_ref and valid server gateway_token."
        }), 400

    customer_id = session.get("user_id") if session.get("role") == "customer" else None

    try:
        with DB.transaction() as tx:
            result = PaymentService.verify_gateway_payment(
                order_id=order_id,
                transaction_ref=tx_ref,
                gateway_token=gateway_token,
                gateway_order_id=gateway_order_id,
                gateway_payment_id=gateway_payment_id,
                gateway_signature=gateway_signature,
                customer_id=customer_id,
                tx=tx
            )
        return jsonify({
            "success": True,
            "message": result["message"],
            "status": "paid",
            "payment_status": "paid",
            "order_id": order_id,
            "transaction_ref": result.get("transaction_ref", tx_ref)
        }), 200
    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400
    except PermissionError as pe:
        return jsonify({"success": False, "message": str(pe)}), 403
    except Exception as e:
        logger.error("Payment confirmation error for order %s: %s", order_id, e)
        return jsonify({"success": False, "message": "Failed to confirm payment."}), 500


@orders_bp.post("/<int:order_id>/cancel")
@role_required(["customer", "vendor", "admin"])
def cancel_order(order_id):
    """
    Cancels an order, restores reserved stock to menu_items, and refunds/cancels payment.
    Enforces business rule: orders cannot be cancelled once the kitchen starts preparing.
    """
    order = DB.get_one("SELECT * FROM orders WHERE id = %s", (order_id,))
    if not order:
        return jsonify({"success": False, "message": "Order not found."}), 404

    current_role = session.get("role")
    current_user_id = session.get("user_id")
    current_shop_id = session.get("shop_id")

    # Authorization / IDOR check
    if current_role == "customer" and order["customer_id"] != current_user_id:
        return jsonify({"success": False, "message": "Forbidden: You cannot cancel another customer's order."}), 403

    if current_role == "vendor" and order["shop_id"] != current_shop_id:
        return jsonify({"success": False, "message": "Forbidden: You cannot cancel another stall's order."}), 403

    if order["order_status"] in ("preparing", "ready", "completed"):
        return jsonify({
            "success": False,
            "message": f"Cannot cancel order. The kitchen has already started {order['order_status']} your food."
        }), 400

    if order["order_status"] == "cancelled":
        return jsonify({"success": False, "message": "Order is already cancelled."}), 400

    try:
        with DB.transaction() as tx:
            # 1. Update order status to cancelled using authoritative DB time.
            tx.execute(
                "UPDATE orders SET order_status = 'cancelled', cancellation_time = UTC_TIMESTAMP() WHERE id = %s",
                (order_id,)
            )

            # 2. Restore reserved stock for each item
            order_items = tx.query("SELECT menu_item_id, quantity FROM order_items WHERE order_id = %s", (order_id,))
            for item in order_items:
                if item.get("menu_item_id"):
                    tx.execute_update(
                        """
                        UPDATE menu_items
                        SET quantity = quantity + %s,
                            is_available = 1
                        WHERE id = %s
                        """,
                        (item["quantity"], item["menu_item_id"])
                    )

            # 3. Refund or cancel payment record
            PaymentService.cancel_or_refund_payment(order_id, reason="Customer cancelled", customer_id=order["customer_id"], tx=tx)

        actor_id = session.get("user_id")
        AuditService.log_action(
            actor_id=actor_id,
            action="ORDER_CANCELLED",
            entity_type="order",
            entity_id=order_id,
            details={"order_reference": order["order_reference"], "cancelled_by": current_role}
        )

        was_paid = (order.get("payment_status") == "paid")
        refund_msg = f" ₹{float(order['total_amount']):.2f} has been refunded to your Campus Wallet." if (was_paid and "wallet" in order.get("payment_method", "").lower()) else ""
        try:
            NotificationService.notify_customer(
                customer_id=order["customer_id"],
                notif_type="ORDER_CANCELLED",
                title=f"Order Cancelled #{order['order_reference']}",
                message=f"Your order has been cancelled.{refund_msg}",
                order_id=order_id
            )
            NotificationService.notify_vendor(
                shop_id=order["shop_id"],
                notif_type="ORDER_CANCELLED",
                title=f"Order Cancelled #{order['order_reference']}",
                message=f"Order #{order['order_reference']} was cancelled by the customer.",
                order_id=order_id
            )
        except Exception as ne:
            logger.warning("Notification dispatch error in cancel_order (non-fatal): %s", ne)

        try:
            emit_order_cancelled(order)
        except Exception as re:
            logger.warning("Realtime customer-cancel dispatch failed (non-fatal): %s", re)

        return jsonify({
            "success": True,
            "message": "Order cancelled successfully. Reserved stock has been restored.",
            "order_id": order_id,
            "status": "cancelled"
        }), 200
    except Exception as e:
        logger.error("Order cancellation error for order %s: %s", order_id, e)
        return jsonify({"success": False, "message": "Failed to cancel order."}), 500


@orders_bp.get("/<int:order_id>/bill")
@orders_bp.get("/<int:order_id>/receipt")
@login_required
def get_order_bill(order_id):
    """
    Returns the complete, immutable bill/receipt for an order.
    Protected by IDOR access control.
    """
    order = DB.get_one(
        """
        SELECT o.*, s.name as shop_name, s.category as shop_category,
               cp.full_name as customer_name, cp.customer_type, cp.identifier, cp.mobile,
               u.email as customer_email
        FROM orders o
        INNER JOIN shops s ON s.id = o.shop_id
        LEFT JOIN customer_profiles cp ON cp.user_id = o.customer_id
        LEFT JOIN users u ON u.id = o.customer_id
        WHERE o.id = %s
        """,
        (order_id,)
    )
    if not order:
        return jsonify({"success": False, "message": "Order not found."}), 404

    current_role = session.get("role")
    current_user_id = session.get("user_id")
    current_shop_id = session.get("shop_id")

    if current_role == "customer" and order["customer_id"] != current_user_id:
        return jsonify({"success": False, "message": "Forbidden: You cannot access other customers' bills."}), 403

    if current_role == "vendor" and order["shop_id"] != current_shop_id:
        return jsonify({"success": False, "message": "Forbidden: You cannot access other stalls' bills."}), 403

    items = DB.query(
        "SELECT id, menu_item_id, item_name, unit_price, quantity, subtotal FROM order_items WHERE order_id = %s",
        (order_id,)
    )

    payment = DB.get_one(
        "SELECT id, method, amount, status, transaction_ref, created_at FROM payments WHERE order_id = %s ORDER BY id DESC LIMIT 1",
        (order_id,)
    )

    total_amount = float(order["total_amount"])
    subtotal = sum(float(i["subtotal"]) for i in items)

    bill = {
        "order_id": order["id"],
        "order_reference": order["order_reference"],
        "order_status": order["order_status"],
        "payment_status": order["payment_status"],
        "payment_method": order["payment_method"],
        "pickup_otp": order["pickup_otp"],
        "shop_id": order["shop_id"],
        "shop_name": order["shop_name"],
        "total_amount": total_amount,
        "subtotal": subtotal,
        "customer": {
            "name": order.get("customer_name") or "Customer",
            "type": order.get("customer_type") or "student",
            "identifier": order.get("identifier") or "",
            "mobile": order.get("mobile") or "",
            "email": order.get("customer_email") or ""
        },
        "shop": {
            "id": order["shop_id"],
            "name": order["shop_name"],
            "category": order.get("shop_category") or "Food Court"
        },
        "items": items,
        "financials": {
            "subtotal": subtotal,
            "convenience_fee": 0.00,
            "total_amount": total_amount
        },
        "payment": payment,
        "timestamps": {
            "order_time": str(order["created_at"]),
            "payment_time": str(order["payment_time"]) if order.get("payment_time") else None,
            "preparing_time": str(order["preparing_time"]) if order.get("preparing_time") else None,
            "ready_time": str(order["ready_time"]) if order.get("ready_time") else None,
            "completed_time": str(order["completed_time"]) if order.get("completed_time") else None,
            "cancellation_time": str(order["cancellation_time"]) if order.get("cancellation_time") else None
        }
    }

    return jsonify({"success": True, "bill": bill}), 200


@orders_bp.get("")
@orders_bp.get("/")
@orders_bp.get("/my-orders")
@role_required(["customer", "admin"])
def get_my_orders():
    customer_id = session.get("user_id")

    status_filter = str(request.args.get("status") or "").strip().lower()
    shop_filter = str(request.args.get("shop") or "").strip()
    from_date = str(request.args.get("from") or "").strip()
    to_date = str(request.args.get("to") or "").strip()

    sql = """
        SELECT o.id, o.order_reference, o.total_amount, o.order_status, o.payment_status,
               o.payment_method, o.pickup_otp, o.created_at, o.payment_time, o.preparing_time,
               o.ready_time, o.completed_time, o.cancellation_time,
               s.name as shop_name, s.category as shop_category
        FROM orders o
        INNER JOIN shops s ON s.id = o.shop_id
        WHERE o.customer_id = %s
    """
    params = [customer_id]
    allowed_statuses = {"pending", "preparing", "ready", "completed", "cancelled"}

    if status_filter and status_filter in allowed_statuses:
        sql += " AND o.order_status = %s"
        params.append(status_filter)
    if shop_filter:
        sql += " AND LOWER(s.name) = LOWER(%s)"
        params.append(shop_filter)
    if from_date:
        sql += " AND DATE(o.created_at) >= %s"
        params.append(from_date)
    if to_date:
        sql += " AND DATE(o.created_at) <= %s"
        params.append(to_date)

    sql += " ORDER BY o.created_at DESC, o.id DESC LIMIT 100"
    orders = DB.query(sql, tuple(params))

    # Attach order item summaries
    for order in orders:
        order["total_amount"] = float(order.get("total_amount") or 0.0)
        items = DB.query(
            "SELECT menu_item_id, item_name, quantity, unit_price, subtotal FROM order_items WHERE order_id = %s",
            (order["id"],),
        )
        for item in items:
            item["unit_price"] = float(item.get("unit_price") or 0.0)
            item["subtotal"] = float(item.get("subtotal") or 0.0)
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

    if current_role == "vendor" and (not current_shop_id or order["shop_id"] != current_shop_id):
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
    if current_role == "vendor" and (not current_shop_id or current_shop_id != shop_id):
        return jsonify({
            "success": False,
            "message": "Forbidden: You are only authorized to view orders from your assigned shop."
        }), 403

    include_all = request.args.get("include_all", "0") in ("1", "true")

    sql = """
        SELECT o.id, o.order_reference, o.customer_id, o.total_amount, o.order_status,
               o.payment_status, o.payment_method, o.pickup_otp, o.created_at,
               o.payment_time, o.preparing_time, o.ready_time, o.completed_time, o.cancellation_time,
               cp.full_name as customer_name, cp.customer_type, cp.identifier
        FROM orders o
        LEFT JOIN customer_profiles cp ON cp.user_id = o.customer_id
        WHERE o.shop_id = %s
    """
    params = [shop_id]

    # In real operations, exclude unpaid abandoned orders unless paid or Pay at Counter
    if not include_all and current_role == "vendor":
        sql += " AND (o.payment_status = 'paid' OR LOWER(o.payment_method) LIKE '%counter%' OR LOWER(o.payment_method) LIKE '%cash%')"

    sql += """
        ORDER BY CASE o.order_status
            WHEN 'pending' THEN 1
            WHEN 'preparing' THEN 2
            WHEN 'ready' THEN 3
            ELSE 4 END,
            o.id DESC
        LIMIT 50
    """

    orders = DB.query(sql, tuple(params))

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
    otp = str(data.get("otp") or data.get("pickup_otp") or "").strip()

    current_role = session.get("role")
    current_shop_id = session.get("shop_id")
    user_id = session.get("user_id")

    # Enforce vendor's actual assigned shop (prevent spoofing via request body)
    if current_role == "vendor":
        if not current_shop_id:
            return jsonify({"success": False, "message": "Forbidden: No assigned stall found for vendor session."}), 403
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

    if order["order_status"] == "cancelled":
        return jsonify({
            "success": False,
            "message": "Cannot verify OTP for a cancelled order."
        }), 400

    # Reset failed attempts counter upon successful verification
    _failed_otp_attempts.pop(lock_key, None)

    # The database clock is authoritative for the completion event.
    # The client/device clock is never trusted for order timestamps.

    # Complete the order, settle any pending payment, and record the food
    # expense in ONE database transaction. This guarantees that a completed
    # order always has its matching expense entry.
    try:
        with DB.transaction() as tx:
            tx.execute(
                """
                UPDATE orders
                SET order_status = 'completed',
                    completed_time = UTC_TIMESTAMP(),
                    payment_status = 'paid',
                    payment_time = COALESCE(payment_time, UTC_TIMESTAMP())
                WHERE id = %s
                """,
                (order["id"],),
            )
            tx.execute(
                "UPDATE payments SET status = 'successful' WHERE order_id = %s AND status = 'pending'",
                (order["id"],),
            )
            # expenses.order_id is UNIQUE, so this is safe to retry.
            PaymentService._record_food_expense(order["id"], tx)
    except Exception as completion_error:
        logger.error(
            "Failed to complete order %s and record food expense: %s",
            order["id"],
            completion_error,
        )
        return jsonify({
            "success": False,
            "message": "Could not complete the order and record the food expense. Please try again."
        }), 500

    actor_id = session.get("user_id")
    AuditService.log_action(
        actor_id=actor_id,
        action="ORDER_OTP_VERIFIED",
        entity_type="order",
        entity_id=order["id"],
        details={"order_reference": order["order_reference"], "shop_id": order["shop_id"], "verified_by": current_role}
    )

    try:
        NotificationService.notify_customer(
            customer_id=order["customer_id"],
            notif_type="ORDER_COMPLETED",
            title=f"Order Completed #{order['order_reference']}",
            message=f"Your order from {order['shop_name']} has been collected and completed. Thank you for dining with us!",
            order_id=order["id"]
        )
    except Exception as ne:
        logger.warning("Notification dispatch error in verify_pickup_otp (non-fatal): %s", ne)

    try:
        emit_order_status(order, "completed", now_str)
    except Exception as re:
        logger.warning("Realtime order-completed dispatch failed (non-fatal): %s", re)

    return jsonify({
        "success": True,
        "message": f"OTP Verified! Order #{order['order_reference']} successfully completed.",
        "order": {
            "id": order["id"],
            "order_reference": order["order_reference"],
            "status": "completed",
            "payment_status": "paid",
            "shop_name": order["shop_name"],
            "completed_time": now_str
        }
    }), 200


@orders_bp.put("/<int:order_id>/status")
@role_required(["vendor", "admin"])
def update_order_status(order_id):
    data = request.get_json(silent=True) or {}
    new_status = str(data.get("status", "")).strip().lower()

    allowed_statuses = {"pending", "preparing", "ready", "completed", "cancelled"}
    if new_status not in allowed_statuses:
        return jsonify({"success": False, "message": f"Invalid status. Must be one of {sorted(list(allowed_statuses))}"}), 400

    order = DB.get_one("SELECT * FROM orders WHERE id = %s", (order_id,))
    if not order:
        return jsonify({"success": False, "message": "Order not found."}), 404

    # Vendor ownership check: vendors cannot touch another stall's orders
    if session.get("role") == "vendor":
        vendor_shop_id = session.get("shop_id")
        if not vendor_shop_id or order["shop_id"] != vendor_shop_id:
            return jsonify({"success": False, "message": "Forbidden: You cannot alter orders belonging to another shop."}), 403

    current_status = str(order["order_status"]).strip().lower()

    if current_status == new_status:
        return jsonify({
            "success": True,
            "message": f"Order is already in {new_status} status.",
            "status": new_status
        }), 200

    # Terminal states: Completed or cancelled orders cannot undergo status changes
    if current_status == "completed":
        return jsonify({"success": False, "message": "Order has already been completed and cannot be changed."}), 400
    if current_status == "cancelled":
        return jsonify({"success": False, "message": "Order is already cancelled and cannot be changed."}), 400

    # Strict workflow transition rules: PENDING -> PREPARING -> READY -> PICKUP OTP -> COMPLETED
    status_order = {"pending": 1, "preparing": 2, "ready": 3, "completed": 4}

    if new_status != "cancelled":
        # Reject invalid backward transitions
        if status_order.get(new_status, 0) < status_order.get(current_status, 0):
            return jsonify({
                "success": False,
                "message": f"Invalid backward status transition from '{current_status}' to '{new_status}'."
            }), 400

        # Disallow forward skips (e.g. pending directly to ready)
        if current_status == "pending" and new_status == "ready":
            return jsonify({
                "success": False,
                "message": "Invalid status transition: Order must be set to 'preparing' before 'ready'."
            }), 400

        # Completion requires pickup OTP verification
        if new_status == "completed":
            return jsonify({
                "success": False,
                "message": "Order completion requires customer pickup OTP verification."
            }), 400

    # Use the database clock for every vendor lifecycle timestamp.
    if new_status == "cancelled" and current_status != "cancelled":
        with DB.transaction() as tx:
            tx.execute(
                "UPDATE orders SET order_status = 'cancelled', cancellation_time = UTC_TIMESTAMP() WHERE id = %s",
                (order_id,)
            )
            items = tx.query("SELECT menu_item_id, quantity FROM order_items WHERE order_id = %s", (order_id,))
            for i in items:
                if i.get("menu_item_id"):
                    tx.execute_update(
                        """
                        UPDATE menu_items
                        SET quantity = quantity + %s,
                            is_available = 1
                        WHERE id = %s
                        """,
                        (i["quantity"], i["menu_item_id"])
                    )
            PaymentService.cancel_or_refund_payment(order_id, reason="Vendor cancelled", customer_id=order["customer_id"], tx=tx)

        actor_id = session.get("user_id")
        AuditService.log_action(
            actor_id=actor_id,
            action="ORDER_CANCELLED",
            entity_type="order",
            entity_id=order_id,
            details={"order_reference": order["order_reference"], "old_status": current_status, "cancelled_by": session.get("role")}
        )

        was_paid = (order.get("payment_status") == "paid")
        refund_msg = f" ₹{float(order['total_amount']):.2f} has been refunded to your Campus Wallet." if (was_paid and "wallet" in order.get("payment_method", "").lower()) else ""
        try:
            NotificationService.notify_customer(
                customer_id=order["customer_id"],
                notif_type="ORDER_CANCELLED",
                title=f"Order Cancelled #{order['order_reference']}",
                message=f"Your order has been cancelled by the kitchen.{refund_msg}",
                order_id=order_id
            )
            NotificationService.notify_vendor(
                shop_id=order["shop_id"],
                notif_type="ORDER_CANCELLED",
                title=f"Order Cancelled #{order['order_reference']}",
                message=f"Order #{order['order_reference']} was cancelled by the kitchen.",
                order_id=order_id
            )
        except Exception as ne:
            logger.warning("Notification dispatch error in kitchen cancel (non-fatal): %s", ne)
        try:
            emit_order_cancelled(order)
        except Exception as re:
            logger.warning("Realtime vendor-cancel dispatch failed (non-fatal): %s", re)
        return jsonify({"success": True, "message": "Order cancelled and stock restored.", "status": "cancelled"}), 200

    # Timestamp update per lifecycle state
    sql = "UPDATE orders SET order_status = %s"
    params = [new_status]

    if new_status == "preparing":
        sql += ", preparing_time = COALESCE(preparing_time, UTC_TIMESTAMP())"
    elif new_status == "ready":
        sql += ", ready_time = COALESCE(ready_time, UTC_TIMESTAMP())"

    sql += " WHERE id = %s"
    params.append(order_id)

    DB.execute(sql, tuple(params))
    status_row = DB.get_one(
        "SELECT preparing_time, ready_time FROM orders WHERE id = %s",
        (order_id,),
    )
    event_time = None
    if new_status == "preparing":
        event_time = status_row.get("preparing_time") if status_row else None
    elif new_status == "ready":
        event_time = status_row.get("ready_time") if status_row else None
    event_time = str(event_time) if event_time else None

    actor_id = session.get("user_id")
    AuditService.log_action(
        actor_id=actor_id,
        action="ORDER_STATUS_CHANGED",
        entity_type="order",
        entity_id=order_id,
        details={"order_reference": order["order_reference"], "old_status": current_status, "new_status": new_status, "role": session.get("role")}
    )

    shop_rec = DB.get_one("SELECT name FROM shops WHERE id = %s", (order["shop_id"],))
    order_shop_name = shop_rec["name"] if shop_rec else "Food Court"

    try:
        if new_status == "preparing":
            NotificationService.notify_customer(
                customer_id=order["customer_id"],
                notif_type="ORDER_PREPARING",
                title=f"Order Preparing #{order['order_reference']}",
                message=f"Your order at {order_shop_name} is now being prepared in the kitchen.",
                order_id=order_id
            )
        elif new_status == "ready":
            NotificationService.notify_customer(
                customer_id=order["customer_id"],
                notif_type="ORDER_READY",
                title=f"Order Ready for Pickup #{order['order_reference']}",
                message=f"Your order is fresh and ready for pickup at {order_shop_name}! Please present your pickup OTP ({order['pickup_otp']}) at the counter.",
                order_id=order_id
            )
    except Exception as ne:
        logger.warning("Notification dispatch error in status change (non-fatal): %s", ne)

    try:
        emit_order_status(order, new_status, event_time)
    except Exception as re:
        logger.warning("Realtime order-status dispatch failed (non-fatal): %s", re)

    return jsonify({
        "success": True,
        "message": f"Order status updated to {new_status}.",
        "status": new_status,
        "updated_at": event_time
    }), 200

