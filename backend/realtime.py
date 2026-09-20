"""Real-time Socket.IO event hub for customer/vendor order updates.

Authentication is established by the normal Flask HTTP login first. Socket.IO then
uses the same Flask session and places each authenticated connection into a
customer room and/or vendor shop room.
"""
import logging
from flask import session
from flask_socketio import SocketIO, join_room

logger = logging.getLogger("food_court.realtime")

socketio = SocketIO(manage_session=True, logger=False, engineio_logger=False)

def customer_room(user_id):
    return f"customer:{int(user_id)}"

def shop_room(shop_id):
    return f"shop:{int(shop_id)}"

@socketio.on("connect")
def handle_connect(auth=None):
    user_id = session.get("user_id")
    role = session.get("role")
    if not user_id or not role:
        return False
    join_room(f"user:{int(user_id)}")
    if role == "customer":
        join_room(customer_room(user_id))
    elif role == "vendor":
        shop_id = session.get("shop_id")
        if shop_id:
            join_room(shop_room(shop_id))
    elif role == "admin":
        join_room("admins")
    logger.info("Realtime connected user=%s role=%s shop=%s", user_id, role, session.get("shop_id"))

def emit_order_created(order):
    payload = {
        "event": "ORDER_CREATED",
        "order_id": order.get("id"),
        "order_reference": order.get("order_reference"),
        "customer_id": order.get("customer_id"),
        "shop_id": order.get("shop_id"),
        "shop_name": order.get("shop_name"),
        "total_amount": float(order.get("total_amount") or 0),
        "order_status": order.get("order_status", "pending"),
        "payment_status": order.get("payment_status"),
        "items_count": order.get("items_count", 0),
        "created_at": str(order.get("created_at") or ""),
    }
    socketio.emit("order:created", payload, to=shop_room(order["shop_id"]))
    socketio.emit("order:created", payload, to=customer_room(order["customer_id"]))

def emit_order_status(order, status, updated_at=None):
    payload = {
        "event": "ORDER_STATUS_CHANGED",
        "order_id": order.get("id"),
        "order_reference": order.get("order_reference"),
        "customer_id": order.get("customer_id"),
        "shop_id": order.get("shop_id"),
        "shop_name": order.get("shop_name"),
        "order_status": status,
        "updated_at": str(updated_at or ""),
    }
    socketio.emit("order:status", payload, to=shop_room(order["shop_id"]))
    socketio.emit("order:status", payload, to=customer_room(order["customer_id"]))

def emit_order_cancelled(order):
    payload = {
        "event": "ORDER_CANCELLED",
        "order_id": order.get("id"),
        "order_reference": order.get("order_reference"),
        "customer_id": order.get("customer_id"),
        "shop_id": order.get("shop_id"),
        "shop_name": order.get("shop_name"),
        "order_status": "cancelled",
    }
    socketio.emit("order:cancelled", payload, to=shop_room(order["shop_id"]))
    socketio.emit("order:cancelled", payload, to=customer_room(order["customer_id"]))
