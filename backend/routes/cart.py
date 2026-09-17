"""
Cart Management Routes for College Food Court Application.

Provides authenticated, database-backed shopping cart operations ensuring:
1. Server-side single-source of truth (replaces localStorage).
2. Authoritative real-time price, availability, and stock checks.
3. Strict single-stall cart invariant (multi-stall conflict detection and optional switch).
4. Full CRUD operations: GET, POST, PUT, DELETE.
"""

import logging
from flask import Blueprint, jsonify, request, session
from db import DB
from routes.auth import login_required

logger = logging.getLogger("food_court.cart")
cart_bp = Blueprint("cart", __name__)


def _get_cart_data(user_id: int):
    """
    Helper function to query and assemble the user's cart items
    joined with live menu and shop status from the database.
    """
    rows = DB.get_all(
        """
        SELECT ci.id as cart_item_id, ci.quantity, ci.created_at, ci.updated_at,
               m.id as item_id, m.name as item_name, m.price, m.category,
               m.quantity as stock_quantity, m.is_available, m.image_url,
               s.id as shop_id, s.name as shop_name, s.slug as shop_slug,
               s.operational_status as shop_operational_status, s.is_active as shop_is_active
        FROM cart_items ci
        INNER JOIN menu_items m ON m.id = ci.menu_item_id
        INNER JOIN shops s ON s.id = m.shop_id
        WHERE ci.user_id = %s
        ORDER BY ci.id ASC
        """,
        (user_id,)
    )

    items = []
    total_amount = 0.0
    total_items = 0
    shop_id = None
    shop_name = None
    validation_errors = []
    is_valid = True

    for row in rows:
        unit_price = float(row.get("price") or 0.0)
        qty = int(row.get("quantity") or 0)
        subtotal = round(unit_price * qty, 2)
        total_amount += subtotal
        total_items += qty

        if shop_id is None:
            shop_id = row.get("shop_id")
            shop_name = row.get("shop_name")
        elif shop_id != row.get("shop_id"):
            # Multi-stall anomaly detected
            is_valid = False
            validation_errors.append(
                f"Cart contains items from multiple stalls ({shop_name} and {row.get('shop_name')})."
            )

        # Live item availability check
        if not row.get("is_available"):
            is_valid = False
            validation_errors.append(f"'{row.get('item_name')}' is currently marked unavailable.")

        # Live stock check
        stock = int(row.get("stock_quantity") or 0)
        if stock < qty:
            is_valid = False
            validation_errors.append(
                f"'{row.get('item_name')}' only has {stock} left in stock (requested {qty})."
            )

        # Live stall status check
        shop_op_status = str(row.get("shop_operational_status") or "OPEN").upper()
        if shop_op_status != "OPEN" or not row.get("shop_is_active"):
            is_valid = False
            validation_errors.append(
                f"Stall '{row.get('shop_name')}' is currently closed or unavailable."
            )

        items.append({
            "cart_item_id": row.get("cart_item_id"),
            "item_id": row.get("item_id"),
            "id": row.get("item_id"),  # Alias for frontend compatibility
            "name": row.get("item_name"),
            "price": unit_price,
            "category": row.get("category"),
            "quantity": qty,
            "subtotal": subtotal,
            "stock_quantity": stock,
            "is_available": bool(row.get("is_available")),
            "image_url": row.get("image_url"),
            "shop_id": row.get("shop_id"),
            "shop_name": row.get("shop_name")
        })

    summary = {
        "total_amount": round(total_amount, 2),
        "total_items": total_items,
        "shop_id": shop_id,
        "shop_name": shop_name,
        "is_valid": is_valid,
        "validation_errors": validation_errors
    }

    return items, summary


@cart_bp.get("")
@cart_bp.get("/")
@login_required
def get_cart():
    """Retrieves the authenticated customer's current shopping cart."""
    user_id = session.get("user_id")
    items, summary = _get_cart_data(user_id)
    return jsonify({
        "success": True,
        "cart": items,
        "items": items,  # Alias
        "summary": summary
    }), 200


@cart_bp.post("")
@cart_bp.post("/")
@login_required
def add_to_cart():
    """
    Adds a menu item to the authenticated customer's cart or increments its quantity.
    Enforces live item validation, stall operation status, and single-stall policy.
    """
    user_id = session.get("user_id")
    data = request.get_json(silent=True) or {}

    raw_item_id = data.get("item_id") or data.get("id") or data.get("menu_item_id")
    if not raw_item_id:
        return jsonify({"success": False, "message": "Item ID is required."}), 400

    try:
        item_id = int(raw_item_id)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid Item ID."}), 400

    try:
        requested_qty = int(data.get("quantity", 1))
        if requested_qty <= 0:
            return jsonify({"success": False, "message": "Quantity must be greater than zero."}), 400
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Quantity must be a valid integer."}), 400

    clear_conflicting_stall = bool(data.get("clear_conflicting_stall", False))

    # Fetch live menu item and stall status
    menu_item = DB.get_one(
        """
        SELECT m.id, m.shop_id, m.name, m.price, m.quantity as stock, m.is_available,
               s.name as shop_name, s.operational_status, s.is_active as shop_active
        FROM menu_items m
        INNER JOIN shops s ON s.id = m.shop_id
        WHERE m.id = %s
        """,
        (item_id,)
    )

    if not menu_item:
        return jsonify({"success": False, "message": f"Menu item #{item_id} not found."}), 404

    if not menu_item.get("is_available"):
        return jsonify({"success": False, "message": f"'{menu_item['name']}' is currently not available."}), 400

    shop_op = str(menu_item.get("operational_status") or "OPEN").upper()
    if shop_op != "OPEN" or not menu_item.get("shop_active"):
        return jsonify({
            "success": False,
            "message": f"Stall '{menu_item['shop_name']}' is currently closed for new orders."
        }), 400

    available_stock = int(menu_item.get("stock") or 0)
    if available_stock <= 0:
        return jsonify({"success": False, "message": f"'{menu_item['name']}' is currently out of stock."}), 400

    target_shop_id = menu_item["shop_id"]
    target_shop_name = menu_item["shop_name"]

    # Check for multi-stall conflict against existing cart items
    existing_stall = DB.get_one(
        """
        SELECT s.id as shop_id, s.name as shop_name
        FROM cart_items ci
        INNER JOIN menu_items m ON m.id = ci.menu_item_id
        INNER JOIN shops s ON s.id = m.shop_id
        WHERE ci.user_id = %s
        LIMIT 1
        """,
        (user_id,)
    )

    if existing_stall and existing_stall["shop_id"] != target_shop_id:
        if not clear_conflicting_stall:
            return jsonify({
                "success": False,
                "conflict": True,
                "message": (
                    f"Your cart already contains items from '{existing_stall['shop_name']}'. "
                    f"To order from '{target_shop_name}', your current cart must be cleared."
                ),
                "current_shop_id": existing_stall["shop_id"],
                "current_shop_name": existing_stall["shop_name"],
                "new_shop_id": target_shop_id,
                "new_shop_name": target_shop_name
            }), 409

        # User consented to clear conflicting stall's items
        DB.execute("DELETE FROM cart_items WHERE user_id = %s", (user_id,))
        logger.info("User #%s cleared cart to switch to shop #%s (%s)", user_id, target_shop_id, target_shop_name)

    # Check if item is already in cart
    existing_cart_item = DB.get_one(
        "SELECT id, quantity FROM cart_items WHERE user_id = %s AND menu_item_id = %s",
        (user_id, item_id)
    )

    if existing_cart_item:
        new_total_qty = existing_cart_item["quantity"] + requested_qty
        if new_total_qty > available_stock:
            return jsonify({
                "success": False,
                "message": f"Cannot add {requested_qty} more. Only {available_stock} available in stock (you have {existing_cart_item['quantity']} in cart)."
            }), 400

        DB.execute(
            "UPDATE cart_items SET quantity = %s WHERE id = %s",
            (new_total_qty, existing_cart_item["id"])
        )
    else:
        if requested_qty > available_stock:
            return jsonify({
                "success": False,
                "message": f"Cannot add {requested_qty}. Only {available_stock} available in stock."
            }), 400

        DB.execute(
            "INSERT INTO cart_items (user_id, menu_item_id, quantity) VALUES (%s, %s, %s)",
            (user_id, item_id, requested_qty)
        )

    items, summary = _get_cart_data(user_id)
    return jsonify({
        "success": True,
        "message": f"Added '{menu_item['name']}' to cart.",
        "cart": items,
        "items": items,
        "summary": summary
    }), 200


@cart_bp.put("/<int:item_id>")
@login_required
def update_cart_item(item_id: int):
    """
    Updates the quantity of a specific item in the authenticated user's cart.
    If quantity <= 0, the item is removed.
    """
    user_id = session.get("user_id")
    data = request.get_json(silent=True) or {}

    try:
        new_qty = int(data.get("quantity", 1))
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Quantity must be a valid integer."}), 400

    cart_entry = DB.get_one(
        "SELECT id, menu_item_id FROM cart_items WHERE user_id = %s AND (menu_item_id = %s OR id = %s)",
        (user_id, item_id, item_id)
    )

    if not cart_entry:
        return jsonify({"success": False, "message": "Item is not in your cart."}), 404

    if new_qty <= 0:
        DB.execute("DELETE FROM cart_items WHERE id = %s", (cart_entry["id"],))
        items, summary = _get_cart_data(user_id)
        return jsonify({
            "success": True,
            "message": "Item removed from cart.",
            "cart": items,
            "items": items,
            "summary": summary
        }), 200

    # Stock validation
    menu_item = DB.get_one(
        "SELECT name, quantity as stock, is_available FROM menu_items WHERE id = %s",
        (cart_entry["menu_item_id"],)
    )

    if not menu_item or not menu_item.get("is_available"):
        DB.execute("DELETE FROM cart_items WHERE id = %s", (cart_entry["id"],))
        items, summary = _get_cart_data(user_id)
        return jsonify({
            "success": False,
            "message": "This item is no longer available and was removed from your cart.",
            "cart": items,
            "summary": summary
        }), 400

    stock = int(menu_item.get("stock") or 0)
    if new_qty > stock:
        return jsonify({
            "success": False,
            "message": f"Only {stock} units of '{menu_item['name']}' are available in stock."
        }), 400

    DB.execute("UPDATE cart_items SET quantity = %s WHERE id = %s", (new_qty, cart_entry["id"]))

    items, summary = _get_cart_data(user_id)
    return jsonify({
        "success": True,
        "message": "Cart updated successfully.",
        "cart": items,
        "items": items,
        "summary": summary
    }), 200


@cart_bp.delete("/<int:item_id>")
@login_required
def remove_cart_item(item_id: int):
    """Removes a specific menu item from the authenticated user's cart."""
    user_id = session.get("user_id")

    cart_entry = DB.get_one(
        "SELECT id FROM cart_items WHERE user_id = %s AND (menu_item_id = %s OR id = %s)",
        (user_id, item_id, item_id)
    )

    if not cart_entry:
        return jsonify({"success": False, "message": "Item was not found in your cart."}), 404

    DB.execute("DELETE FROM cart_items WHERE id = %s", (cart_entry["id"],))

    items, summary = _get_cart_data(user_id)
    return jsonify({
        "success": True,
        "message": "Item removed from cart.",
        "cart": items,
        "items": items,
        "summary": summary
    }), 200


@cart_bp.delete("")
@cart_bp.delete("/")
@login_required
def clear_cart():
    """Clears all items from the authenticated user's shopping cart."""
    user_id = session.get("user_id")
    DB.execute("DELETE FROM cart_items WHERE user_id = %s", (user_id,))

    items, summary = _get_cart_data(user_id)
    return jsonify({
        "success": True,
        "message": "Shopping cart cleared.",
        "cart": items,
        "items": items,
        "summary": summary
    }), 200
