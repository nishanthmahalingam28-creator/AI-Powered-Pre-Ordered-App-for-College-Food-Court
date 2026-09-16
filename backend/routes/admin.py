import logging
from flask import Blueprint, jsonify, request
from werkzeug.security import generate_password_hash
from db import DB
from routes.auth import role_required

logger = logging.getLogger("food_court.admin")
admin_bp = Blueprint("admin", __name__)


@admin_bp.get("/overview")
@role_required(["admin"])
def get_admin_overview():
    stats = {}

    # Revenue and Orders
    order_stats = DB.get_one(
        """
        SELECT COALESCE(SUM(total_amount), 0) as total_turnover,
               COUNT(id) as total_orders,
               SUM(CASE WHEN order_status = 'completed' THEN 1 ELSE 0 END) as completed_orders,
               SUM(CASE WHEN order_status IN ('pending', 'preparing', 'ready') THEN 1 ELSE 0 END) as active_orders
        FROM orders
        """
    )
    stats["total_turnover"] = float(order_stats.get("total_turnover", 0.0))
    stats["total_orders"] = int(order_stats.get("total_orders", 0))
    stats["completed_orders"] = int(order_stats.get("completed_orders", 0))
    stats["active_orders"] = int(order_stats.get("active_orders", 0))

    # Shops count
    shop_count = DB.get_one("SELECT COUNT(id) as total FROM shops WHERE is_active = 1")
    stats["active_shops"] = int(shop_count.get("total", 0))

    # Users count
    user_counts = DB.get_one(
        """
        SELECT COUNT(id) as total_users,
               SUM(CASE WHEN role = 'customer' THEN 1 ELSE 0 END) as total_customers,
               SUM(CASE WHEN role = 'vendor' THEN 1 ELSE 0 END) as total_vendors
        FROM users
        WHERE is_active = 1
        """
    )
    stats["total_users"] = int(user_counts.get("total_users", 0))
    stats["total_customers"] = int(user_counts.get("total_customers", 0))
    stats["total_vendors"] = int(user_counts.get("total_vendors", 0))

    # Recent Transactions
    recent_orders = DB.query(
        """
        SELECT o.id, o.order_reference, o.total_amount, o.order_status, o.created_at,
               s.name as shop_name, cp.full_name as customer_name
        FROM orders o
        INNER JOIN shops s ON s.id = o.shop_id
        LEFT JOIN customer_profiles cp ON cp.user_id = o.customer_id
        ORDER BY o.id DESC
        LIMIT 10
        """
    )

    return jsonify({
        "success": True,
        "overview": stats,
        "recent_orders": recent_orders
    }), 200


@admin_bp.get("/shops")
@role_required(["admin"])
def get_admin_shops():
    shops = DB.query(
        """
        SELECT s.id, s.name, s.slug, s.description, s.category, s.is_active, s.created_at,
               u.email as owner_email,
               COUNT(m.id) as total_items
        FROM shops s
        LEFT JOIN users u ON u.id = s.owner_user_id
        LEFT JOIN menu_items m ON m.shop_id = s.id
        GROUP BY s.id
        ORDER BY s.id ASC
        """
    )
    return jsonify({"success": True, "shops": shops}), 200


@admin_bp.post("/shops")
@role_required(["admin"])
def add_shop():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    slug = str(data.get("slug") or name.lower().replace(" ", "-")).strip()
    description = str(data.get("description", "")).strip()
    category = str(data.get("category", "Multi-Cuisine")).strip()

    if not name:
        return jsonify({"success": False, "message": "Stall name is required."}), 400

    existing = DB.get_one(
        "SELECT id FROM shops WHERE LOWER(name) = %s OR LOWER(slug) = %s LIMIT 1",
        (name.lower(), slug.lower()),
    )
    if existing:
        return jsonify({
            "success": False,
            "message": f"A stall with name '{name}' or slug '{slug}' already exists."
        }), 409

    shop_id = DB.execute(
        "INSERT INTO shops (name, slug, description, category, is_active) VALUES (%s, %s, %s, %s, 1)",
        (name, slug, description, category),
    )

    return jsonify({"success": True, "message": f"Stall '{name}' created successfully.", "shop_id": shop_id}), 201


@admin_bp.put("/shops/<int:shop_id>")
@role_required(["admin"])
def update_shop(shop_id):
    shop = DB.get_one("SELECT * FROM shops WHERE id = %s", (shop_id,))
    if not shop:
        return jsonify({"success": False, "message": "Shop not found."}), 404

    data = request.get_json(silent=True) or {}
    name = str(data.get("name", shop["name"])).strip()
    slug = str(data.get("slug", shop["slug"])).strip()
    description = str(data.get("description", shop.get("description") or "")).strip()
    category = str(data.get("category", shop.get("category") or "Multi-Cuisine")).strip()

    if not name:
        return jsonify({"success": False, "message": "Stall name cannot be empty."}), 400

    # Check duplicate on another stall
    existing = DB.get_one(
        "SELECT id FROM shops WHERE (LOWER(name) = %s OR LOWER(slug) = %s) AND id != %s LIMIT 1",
        (name.lower(), slug.lower(), shop_id),
    )
    if existing:
        return jsonify({"success": False, "message": "Another stall already uses this name or slug."}), 409

    DB.execute(
        """
        UPDATE shops
        SET name = %s, slug = %s, description = %s, category = %s
        WHERE id = %s
        """,
        (name, slug, description, category, shop_id),
    )

    return jsonify({
        "success": True,
        "message": f"Stall '{name}' updated successfully.",
        "shop": {
            "id": shop_id,
            "name": name,
            "slug": slug,
            "description": description,
            "category": category,
        }
    }), 200


@admin_bp.put("/shops/<int:shop_id>/status")
@role_required(["admin"])
def toggle_shop_status(shop_id):
    shop = DB.get_one("SELECT id, is_active, name FROM shops WHERE id = %s", (shop_id,))
    if not shop:
        return jsonify({"success": False, "message": "Shop not found."}), 404

    data = request.get_json(silent=True) or {}
    if "is_active" in data:
        new_status = 1 if data["is_active"] else 0
    else:
        new_status = 0 if shop["is_active"] == 1 else 1

    DB.execute("UPDATE shops SET is_active = %s WHERE id = %s", (new_status, shop_id))

    status_text = "Activated" if new_status == 1 else "Deactivated"
    return jsonify({"success": True, "message": f"Stall '{shop['name']}' {status_text}.", "is_active": new_status}), 200


@admin_bp.get("/users")
@role_required(["admin"])
def get_admin_users():
    users = DB.query(
        """
        SELECT u.id, u.email, u.role, u.is_active, u.created_at,
               cp.full_name, cp.customer_type, cp.identifier, cp.mobile,
               s.name as shop_name
        FROM users u
        LEFT JOIN customer_profiles cp ON cp.user_id = u.id
        LEFT JOIN shops s ON s.owner_user_id = u.id
        ORDER BY u.id DESC
        LIMIT 100
        """
    )
    return jsonify({"success": True, "users": users}), 200


@admin_bp.put("/users/<int:user_id>/status")
@role_required(["admin"])
def toggle_user_status(user_id):
    user = DB.get_one("SELECT id, is_active, email FROM users WHERE id = %s", (user_id,))
    if not user:
        return jsonify({"success": False, "message": "User not found."}), 404

    data = request.get_json(silent=True) or {}
    if "is_active" in data:
        new_status = 1 if data["is_active"] else 0
    else:
        new_status = 0 if user["is_active"] == 1 else 1

    DB.execute("UPDATE users SET is_active = %s WHERE id = %s", (new_status, user_id))

    return jsonify({"success": True, "message": f"User status updated.", "is_active": new_status}), 200


@admin_bp.post("/vendors")
@role_required(["admin"])
def create_vendor():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", "")).strip()
    shop_id = data.get("shop_id")

    if not email or not password:
        return jsonify({"success": False, "message": "Vendor email and initial password are required."}), 400

    existing = DB.get_one("SELECT id FROM users WHERE LOWER(email) = %s", (email,))
    if existing:
        return jsonify({"success": False, "message": "An account with this email already exists."}), 409

    pwd_hash = generate_password_hash(password)
    user_id = DB.execute(
        "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'vendor', 1)",
        (email, pwd_hash),
    )

    if shop_id:
        target_shop = DB.get_one("SELECT id, is_active FROM shops WHERE id = %s", (shop_id,))
        if not target_shop or not target_shop.get("is_active"):
            return jsonify({"success": False, "message": "Cannot assign vendor to an inactive or non-existent stall."}), 400
        DB.execute("UPDATE shops SET owner_user_id = %s WHERE id = %s", (user_id, shop_id))

    return jsonify({
        "success": True,
        "message": f"Vendor account '{email}' created successfully.",
        "user_id": user_id,
        "assigned_shop_id": shop_id
    }), 201


@admin_bp.put("/vendors/<int:user_id>/shop")
@role_required(["admin"])
def assign_vendor_shop(user_id):
    data = request.get_json(silent=True) or {}
    shop_id = data.get("shop_id")

    vendor = DB.get_one("SELECT id, email, role FROM users WHERE id = %s AND role = 'vendor'", (user_id,))
    if not vendor:
        return jsonify({"success": False, "message": "Vendor user not found."}), 404

    if not shop_id:
        return jsonify({"success": False, "message": "Target shop_id is required."}), 400

    shop = DB.get_one("SELECT id, name, is_active FROM shops WHERE id = %s", (shop_id,))
    if not shop:
        return jsonify({"success": False, "message": "Target shop not found."}), 404

    if not shop.get("is_active"):
        return jsonify({"success": False, "message": "Cannot assign vendor to an inactive stall."}), 400

    # Clear any previous stall ownership for this vendor to ensure 1-to-1 mapping
    DB.execute("UPDATE shops SET owner_user_id = NULL WHERE owner_user_id = %s", (user_id,))
    DB.execute("UPDATE shops SET owner_user_id = %s WHERE id = %s", (user_id, shop_id))

    return jsonify({
        "success": True,
        "message": f"Vendor '{vendor['email']}' successfully assigned to stall '{shop['name']}'.",
        "vendor_id": user_id,
        "shop_id": shop_id,
        "shop_name": shop['name']
    }), 200

