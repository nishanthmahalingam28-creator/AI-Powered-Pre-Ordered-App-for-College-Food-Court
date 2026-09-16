from flask import Blueprint, jsonify, request, session
from db import DB
from routes.auth import role_required

vendor_bp = Blueprint("vendor", __name__)


def _get_active_shop_id():
    # Strict tenant isolation: Vendors are locked to their own shop_id
    if session.get("role") == "vendor":
        return session.get("shop_id") or 1

    # Admins can query any shop via param
    shop_id = request.args.get("shop_id")
    shop_name = request.args.get("shop")

    if shop_id:
        return shop_id
    if shop_name:
        shop = DB.get_one("SELECT id FROM shops WHERE LOWER(name) = %s LIMIT 1", (shop_name.lower(),))
        if shop:
            return shop["id"]

    return session.get("shop_id") or 1


@vendor_bp.get("/analytics")
@role_required(["vendor", "admin"])
def get_vendor_analytics():
    shop_id = _get_active_shop_id()

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
    )

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
    )

    return jsonify({
        "success": True,
        "shop": {
            "id": shop_id,
            "name": shop_name,
        },
        "analytics": {
            "today_revenue": float(revenue_row.get("total_revenue", 0.0)),
            "total_orders": int(revenue_row.get("total_orders", 0)),
            "active_orders": int(revenue_row.get("active_orders", 0)),
            "total_dishes": int(menu_stats.get("total_dishes", 0)),
            "available_dishes": int(menu_stats.get("available_dishes", 0)),
            "out_of_stock_dishes": int(menu_stats.get("out_of_stock_dishes", 0)),
            "total_stock": int(menu_stats.get("total_stock", 0)),
        }
    }), 200


@vendor_bp.post("/menu/item")
@role_required(["vendor", "admin"])
def add_menu_item():
    data = request.get_json(silent=True) or {}
    shop_id = _get_active_shop_id()
    name = str(data.get("name", "")).strip()
    price = float(data.get("price") or 0)
    quantity = int(data.get("quantity") or data.get("stock_quantity") or 0)
    category = str(data.get("category", "Main Course")).strip()
    available = 1 if (data.get("available", True) and quantity > 0) else 0
    description = str(data.get("description", "")).strip() or f"Delicious fresh {name}"

    if not name or price <= 0:
        return jsonify({"success": False, "message": "Dish name and valid price are required."}), 400

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
            "price": price,
            "category": category,
            "quantity": quantity,
            "is_available": available,
        }
    }), 201


@vendor_bp.put("/menu/item/<int:item_id>")
@role_required(["vendor", "admin"])
def update_menu_item(item_id):
    data = request.get_json(silent=True) or {}
    item = DB.get_one("SELECT * FROM menu_items WHERE id = %s", (item_id,))
    if not item:
        return jsonify({"success": False, "message": "Dish not found."}), 404

    # Strict isolation: Vendor cannot modify another stall's menu
    active_shop = _get_active_shop_id()
    if session.get("role") == "vendor" and item["shop_id"] != active_shop:
        return jsonify({"success": False, "message": "Forbidden: You cannot modify dishes belonging to another stall."}), 403

    price = float(data.get("price")) if "price" in data else item["price"]
    quantity = int(data.get("quantity")) if "quantity" in data else item["quantity"]
    category = data.get("category") if "category" in data else item["category"]

    if "available" in data or "is_available" in data:
        is_available = 1 if (data.get("available") or data.get("is_available")) else 0
    else:
        is_available = 1 if (quantity > 0 and item["is_available"]) else 0

    DB.execute(
        """
        UPDATE menu_items
        SET price = %s, quantity = %s, category = %s, is_available = %s
        WHERE id = %s
        """,
        (price, quantity, category, is_available, item_id),
    )

    return jsonify({
        "success": True,
        "message": f"Updated '{item['name']}' successfully.",
        "item": {
            "id": item_id,
            "name": item["name"],
            "price": price,
            "quantity": quantity,
            "category": category,
            "is_available": is_available
        }
    }), 200


@vendor_bp.delete("/menu/item/<int:item_id>")
@role_required(["vendor", "admin"])
def delete_menu_item(item_id):
    item = DB.get_one("SELECT id, name, shop_id FROM menu_items WHERE id = %s", (item_id,))
    if not item:
        return jsonify({"success": False, "message": "Dish not found."}), 404

    # Strict isolation: Vendor cannot delete another stall's menu item
    active_shop = _get_active_shop_id()
    if session.get("role") == "vendor" and item["shop_id"] != active_shop:
        return jsonify({"success": False, "message": "Forbidden: You cannot delete dishes belonging to another stall."}), 403

    DB.execute("DELETE FROM menu_items WHERE id = %s", (item_id,))
    return jsonify({"success": True, "message": f"'{item['name']}' removed from menu."}), 200
