import re
import logging
from decimal import Decimal, InvalidOperation
from flask import Blueprint, jsonify, request, session
from db import DB
from routes.auth import role_required

logger = logging.getLogger("food_court.vendor")
vendor_bp = Blueprint("vendor", __name__)


def validate_price(val):
    """Validates and sanitizes menu price to a safe positive 2-decimal float."""
    if val is None or isinstance(val, bool):
        return None, "Price is required."
    try:
        val_str = str(val).strip()
        # Reject non-numeric strings, currency symbols, and exponential notation
        if not re.match(r"^\d+(\.\d{1,2})?$", val_str):
            return None, "Invalid price format. Must be a positive numeric value with at most 2 decimal places."
        d = Decimal(val_str)
        if d.is_nan() or d.is_infinite():
            return None, "Invalid numeric price."
        if d <= 0:
            return None, "Price must be greater than zero."
        if d > Decimal("10000.00"):
            return None, "Price exceeds maximum allowable limit of ₹10,000."
        return float(d.quantize(Decimal("0.01"))), None
    except (InvalidOperation, ValueError, TypeError):
        return None, "Invalid price format. Must be a valid positive number."


def validate_quantity(val):
    """Validates and sanitizes menu stock quantity to a non-negative integer."""
    if val is None:
        return 0, None
    try:
        # Reject floats with non-zero decimal part
        if isinstance(val, float) and not val.is_integer():
            return None, "Stock quantity must be a whole number."
        if isinstance(val, str):
            val = val.strip()
            if "." in val and float(val) != int(float(val)):
                return None, "Stock quantity must be a whole number."
        q = int(val)
        if q < 0:
            return None, "Stock quantity cannot be negative."
        if q > 100000:
            return None, "Stock quantity exceeds maximum allowable limit."
        return q, None
    except (ValueError, TypeError):
        return None, "Invalid quantity format. Must be a non-negative integer."


def _get_active_shop_id():
    """
    Resolves the authoritative shop_id for vendor operations.
    - Vendor role: Strictly resolved from the active database assignment for this user.
      Never trusts client-supplied shop_id in parameters or JSON bodies.
      If stall is deactivated or unassigned, returns None.
    - Admin role: Can specify shop_id or shop name via query params or JSON body.
    - NEVER defaults to shop_id = 1.
    """
    role = session.get("role")
    user_id = session.get("user_id")

    if role == "vendor":
        if not user_id:
            return None
        # Always verify current shop assignment and active status directly from DB
        shop = DB.get_one(
            "SELECT id, is_active FROM shops WHERE owner_user_id = %s LIMIT 1",
            (user_id,)
        )
        if not shop or not shop.get("is_active"):
            return None
        return shop["id"]

    if role == "admin":
        data = request.get_json(silent=True) or {}
        shop_id = request.args.get("shop_id") or data.get("shop_id")
        shop_name = request.args.get("shop") or data.get("shop")

        if shop_id and str(shop_id).isdigit():
            return int(shop_id)
        if shop_name:
            shop = DB.get_one("SELECT id FROM shops WHERE LOWER(name) = %s LIMIT 1", (str(shop_name).strip().lower(),))
            if shop:
                return shop["id"]

        # Fall back to session shop_id if admin has one assigned
        return session.get("shop_id")

    return None


@vendor_bp.get("/analytics")
@role_required(["vendor", "admin"])
def get_vendor_analytics():
    """Returns real-time sales, order volume, and inventory telemetry for the stall."""
    shop_id = _get_active_shop_id()
    if not shop_id:
        return jsonify({
            "success": False,
            "message": "No active stall specified or stall is currently deactivated."
        }), 403

    shop = DB.get_one("SELECT * FROM shops WHERE id = %s", (shop_id,))
    shop_name = shop["name"] if shop else "Stall"

    # Orders count and revenue
    revenue_row = DB.get_one(
        """
        SELECT COALESCE(SUM(total_amount), 0) as total_revenue,
               COUNT(id) as total_orders,
               SUM(CASE WHEN order_status IN ('pending', 'preparing', 'ready') THEN 1 ELSE 0 END) as active_orders
        FROM orders
        WHERE shop_id = %s
        """,
        (shop_id,),
    ) or {}

    # Menu item count and stock stats
    menu_stats = DB.get_one(
        """
        SELECT COUNT(id) as total_dishes,
               SUM(CASE WHEN is_available = 1 AND quantity > 0 THEN 1 ELSE 0 END) as available_dishes,
               SUM(CASE WHEN quantity <= 0 OR is_available = 0 THEN 1 ELSE 0 END) as out_of_stock_dishes,
               COALESCE(SUM(quantity), 0) as total_stock
        FROM menu_items
        WHERE shop_id = %s
        """,
        (shop_id,),
    ) or {}

    return jsonify({
        "success": True,
        "shop": {
            "id": shop_id,
            "name": shop_name,
        },
        "analytics": {
            "today_revenue": float(revenue_row.get("total_revenue") or 0.0),
            "total_orders": int(revenue_row.get("total_orders") or 0),
            "active_orders": int(revenue_row.get("active_orders") or 0),
            "total_dishes": int(menu_stats.get("total_dishes") or 0),
            "available_dishes": int(menu_stats.get("available_dishes") or 0),
            "out_of_stock_dishes": int(menu_stats.get("out_of_stock_dishes") or 0),
            "total_stock": int(menu_stats.get("total_stock") or 0),
        }
    }), 200


@vendor_bp.post("/menu/item")
@role_required(["vendor", "admin"])
def add_menu_item():
    """Adds a new dish to the vendor's assigned active stall."""
    shop_id = _get_active_shop_id()
    if not shop_id:
        return jsonify({
            "success": False,
            "message": "Forbidden: No active stall assigned or stall is currently deactivated."
        }), 403

    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    if not name:
        return jsonify({"success": False, "message": "Dish name is required."}), 400
    if len(name) > 150:
        return jsonify({"success": False, "message": "Dish name cannot exceed 150 characters."}), 400

    if not re.match(r"^[\w\s&/\-\(\)\.,'!]+$", name, re.UNICODE):
        return jsonify({"success": False, "message": "Invalid dish name format. Special symbols/scripts are not permitted."}), 400

    # Validate price
    price, price_err = validate_price(data.get("price"))
    if price_err:
        return jsonify({"success": False, "message": price_err}), 400

    # Validate quantity
    quantity, qty_err = validate_quantity(data.get("quantity") if "quantity" in data else data.get("stock_quantity"))
    if qty_err:
        return jsonify({"success": False, "message": qty_err}), 400

    category = str(data.get("category", "Food")).strip()
    if not category:
        return jsonify({"success": False, "message": "Category is required."}), 400
    if len(category) > 100:
        return jsonify({"success": False, "message": "Category cannot exceed 100 characters."}), 400
    if not re.match(r"^[\w\s&/\-\(\)\.,'!]+$", category, re.UNICODE):
        return jsonify({"success": False, "message": "Invalid category format. Special symbols/scripts are not permitted."}), 400

    raw_avail = data.get("available") if "available" in data else data.get("is_available", True)
    available = 1 if (bool(raw_avail) and quantity > 0) else 0

    description = str(data.get("description", "")).strip()
    if len(description) > 500:
        return jsonify({"success": False, "message": "Description cannot exceed 500 characters."}), 400
    if not description:
        description = f"Fresh authentic {name} prepared at our stall."

    item_id = DB.execute(
        """
        INSERT INTO menu_items (shop_id, name, description, price, category, quantity, is_available)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (shop_id, name, description, price, category, quantity, available),
    )

    return jsonify({
        "success": True,
        "message": f"'{name}' added to menu successfully!",
        "item": {
            "id": item_id,
            "shop_id": shop_id,
            "name": name,
            "description": description,
            "price": price,
            "category": category,
            "quantity": quantity,
            "is_available": available,
        }
    }), 201


@vendor_bp.put("/menu/item/<int:item_id>")
@role_required(["vendor", "admin"])
def update_menu_item(item_id):
    """
    Updates price, stock, category, or availability of a dish.
    Enforces strict stall ownership (IDOR prevention).
    """
    data = request.get_json(silent=True) or {}
    item = DB.get_one("SELECT * FROM menu_items WHERE id = %s", (item_id,))
    if not item:
        return jsonify({"success": False, "message": "Dish not found."}), 404

    active_shop = _get_active_shop_id()
    if not active_shop:
        return jsonify({
            "success": False,
            "message": "Forbidden: No active stall assigned or stall is currently deactivated."
        }), 403

    # Strict isolation: Vendor cannot modify another stall's menu items
    if session.get("role") == "vendor" and item["shop_id"] != active_shop:
        return jsonify({
            "success": False,
            "message": "Forbidden: You cannot modify dishes belonging to another stall."
        }), 403

    # Validate price if provided
    if "price" in data:
        price, price_err = validate_price(data.get("price"))
        if price_err:
            return jsonify({"success": False, "message": price_err}), 400
    else:
        price = float(item["price"])

    # Validate quantity if provided
    if "quantity" in data or "stock_quantity" in data:
        raw_q = data.get("quantity") if "quantity" in data else data.get("stock_quantity")
        quantity, qty_err = validate_quantity(raw_q)
        if qty_err:
            return jsonify({"success": False, "message": qty_err}), 400
    else:
        quantity = int(item["quantity"])

    # Category update
    if "category" in data:
        category = str(data["category"]).strip()
        if not category:
            return jsonify({"success": False, "message": "Category cannot be empty."}), 400
        if not re.match(r"^[\w\s&/\-\(\)\.,'!]+$", category, re.UNICODE):
            return jsonify({"success": False, "message": "Invalid category format. Special symbols/scripts are not permitted."}), 400
    else:
        category = item["category"]

    # Name update
    if "name" in data:
        name = str(data["name"]).strip()
        if not name:
            return jsonify({"success": False, "message": "Dish name cannot be empty."}), 400
        if len(name) > 150:
            return jsonify({"success": False, "message": "Dish name cannot exceed 150 characters."}), 400
        if not re.match(r"^[\w\s&/\-\(\)\.,'!]+$", name, re.UNICODE):
            return jsonify({"success": False, "message": "Invalid dish name format. Special symbols/scripts are not permitted."}), 400
    else:
        name = item["name"]

    # Availability logic: if quantity is 0, item MUST be unavailable
    if "available" in data or "is_available" in data:
        raw_avail = data.get("available") if "available" in data else data.get("is_available")
        is_available = 1 if (bool(raw_avail) and quantity > 0) else 0
    else:
        is_available = 1 if (quantity > 0 and item["is_available"]) else 0

    description = str(data.get("description", item.get("description") or "")).strip()

    DB.execute(
        """
        UPDATE menu_items
        SET name = %s, description = %s, price = %s, quantity = %s, category = %s, is_available = %s
        WHERE id = %s
        """,
        (name, description, price, quantity, category, is_available, item_id),
    )

    return jsonify({
        "success": True,
        "message": f"Updated '{name}' successfully.",
        "item": {
            "id": item_id,
            "shop_id": item["shop_id"],
            "name": name,
            "description": description,
            "price": price,
            "quantity": quantity,
            "category": category,
            "is_available": is_available,
        }
    }), 200


@vendor_bp.delete("/menu/item/<int:item_id>")
@role_required(["vendor", "admin"])
def delete_menu_item(item_id):
    """
    Deletes or deactivates a menu item.
    Enforces strict stall ownership (IDOR prevention).
    If item has historical orders, soft-deactivates to preserve order history.
    """
    item = DB.get_one("SELECT id, name, shop_id FROM menu_items WHERE id = %s", (item_id,))
    if not item:
        return jsonify({"success": False, "message": "Dish not found."}), 404

    active_shop = _get_active_shop_id()
    if not active_shop:
        return jsonify({
            "success": False,
            "message": "Forbidden: No active stall assigned or stall is currently deactivated."
        }), 403

    # Strict isolation: Vendor cannot delete another stall's menu item
    if session.get("role") == "vendor" and item["shop_id"] != active_shop:
        return jsonify({
            "success": False,
            "message": "Forbidden: You cannot delete dishes belonging to another stall."
        }), 403

    # Check if item exists in historical orders
    historical_order = DB.get_one("SELECT id FROM order_items WHERE menu_item_id = %s LIMIT 1", (item_id,))
    if historical_order:
        # Safe soft-deactivation to preserve order history records
        DB.execute("UPDATE menu_items SET is_available = 0, quantity = 0 WHERE id = %s", (item_id,))
        return jsonify({
            "success": True,
            "message": f"'{item['name']}' archived and marked unavailable to preserve order history."
        }), 200
    else:
        # No historical orders exist; safe to physically delete
        DB.execute("DELETE FROM menu_items WHERE id = %s", (item_id,))
        return jsonify({
            "success": True,
            "message": f"'{item['name']}' removed from menu."
        }), 200
