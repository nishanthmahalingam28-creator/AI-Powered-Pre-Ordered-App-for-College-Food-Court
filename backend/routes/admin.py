import re
import logging
from datetime import datetime
from flask import Blueprint, jsonify, request, session
from security import hash_password
from db import DB
from routes.auth import role_required
from services.audit import AuditService

logger = logging.getLogger("food_court.admin")
admin_bp = Blueprint("admin", __name__)

ALLOWED_OPERATIONAL_STATUSES = {"OPEN", "CLOSED", "TEMPORARILY_UNAVAILABLE"}


@admin_bp.get("/overview")
@role_required(["admin"])
def get_admin_overview():
    """Returns dashboard metrics using one pooled DB connection for all reads."""
    results = DB.query_many([
        ("""
            SELECT COALESCE(SUM(total_amount), 0) as total_turnover,
                   COUNT(id) as total_orders,
                   SUM(CASE WHEN order_status = 'completed' THEN 1 ELSE 0 END) as completed_orders,
                   SUM(CASE WHEN order_status IN ('pending', 'preparing', 'ready') THEN 1 ELSE 0 END) as active_orders,
                   SUM(CASE WHEN order_status = 'pending' THEN 1 ELSE 0 END) as pending_orders,
                   SUM(CASE WHEN order_status = 'preparing' THEN 1 ELSE 0 END) as preparing_orders,
                   SUM(CASE WHEN order_status = 'ready' THEN 1 ELSE 0 END) as ready_orders,
                   SUM(CASE WHEN order_status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_orders
            FROM orders
        """, ()),
        ("""
            SELECT COUNT(id) as total_shops,
                   SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_shops,
                   SUM(CASE WHEN is_active = 1 AND UPPER(operational_status) = 'OPEN' THEN 1 ELSE 0 END) as open_shops,
                   SUM(CASE WHEN is_active = 1 AND UPPER(operational_status) = 'CLOSED' THEN 1 ELSE 0 END) as closed_shops,
                   SUM(CASE WHEN is_active = 1 AND UPPER(operational_status) = 'TEMPORARILY_UNAVAILABLE' THEN 1 ELSE 0 END) as unavailable_shops
            FROM shops
        """, ()),
        ("""
            SELECT COUNT(id) as total_users,
                   SUM(CASE WHEN role = 'customer' THEN 1 ELSE 0 END) as total_customers,
                   SUM(CASE WHEN role = 'vendor' THEN 1 ELSE 0 END) as total_vendors,
                   SUM(CASE WHEN role = 'admin' THEN 1 ELSE 0 END) as total_admins
            FROM users WHERE is_active = 1
        """, ()),
        ("""
            SELECT COALESCE(SUM(CASE WHEN status = 'successful' THEN amount ELSE 0 END), 0) as total_collected,
                   COALESCE(SUM(CASE WHEN status = 'refunded' THEN amount ELSE 0 END), 0) as total_refunded,
                   SUM(CASE WHEN status = 'successful' THEN 1 ELSE 0 END) as successful_payments,
                   SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_payments,
                   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_payments
            FROM payments
        """, ()),
        ("""
            SELECT o.id, o.order_reference, o.total_amount, o.order_status, o.payment_status,
                   o.payment_method, o.created_at,
                   s.name as shop_name, cp.full_name as customer_name, u.email as customer_email
            FROM orders o
            INNER JOIN shops s ON s.id = o.shop_id
            LEFT JOIN customer_profiles cp ON cp.user_id = o.customer_id
            LEFT JOIN users u ON u.id = o.customer_id
            ORDER BY o.id DESC LIMIT 10
        """, ()),
    ])

    order_stats = (results[0][0] if results[0] else {}) or {}
    shop_stats = (results[1][0] if results[1] else {}) or {}
    user_counts = (results[2][0] if results[2] else {}) or {}
    payment_stats = (results[3][0] if results[3] else {}) or {}
    recent_orders = results[4]

    stats = {
        "total_turnover": float(order_stats.get("total_turnover") or 0.0),
        "total_orders": int(order_stats.get("total_orders") or 0),
        "completed_orders": int(order_stats.get("completed_orders") or 0),
        "active_orders": int(order_stats.get("active_orders") or 0),
        "pending_orders": int(order_stats.get("pending_orders") or 0),
        "preparing_orders": int(order_stats.get("preparing_orders") or 0),
        "ready_orders": int(order_stats.get("ready_orders") or 0),
        "cancelled_orders": int(order_stats.get("cancelled_orders") or 0),
        "total_shops": int(shop_stats.get("total_shops") or 0),
        "active_shops": int(shop_stats.get("active_shops") or 0),
        "open_shops": int(shop_stats.get("open_shops") or 0),
        "closed_shops": int(shop_stats.get("closed_shops") or 0),
        "unavailable_shops": int(shop_stats.get("unavailable_shops") or 0),
        "total_users": int(user_counts.get("total_users") or 0),
        "total_customers": int(user_counts.get("total_customers") or 0),
        "total_vendors": int(user_counts.get("total_vendors") or 0),
        "total_admins": int(user_counts.get("total_admins") or 0),
        "payments": {
            "total_collected": float(payment_stats.get("total_collected") or 0.0),
            "total_refunded": float(payment_stats.get("total_refunded") or 0.0),
            "successful_payments": int(payment_stats.get("successful_payments") or 0),
            "pending_payments": int(payment_stats.get("pending_payments") or 0),
            "failed_payments": int(payment_stats.get("failed_payments") or 0),
        },
    }

    return jsonify({"success": True, "overview": stats, "recent_orders": recent_orders}), 200


# ============================================================================
# SHOP MANAGEMENT
# ============================================================================

@admin_bp.get("/shops")
@role_required(["admin"])
def get_admin_shops():
    """Returns all food court stalls with owner details and operational status."""
    shops = DB.query(
        """
        SELECT s.id, s.name, s.slug, s.description, s.category, s.image_url, s.is_active,
               s.operational_status, s.owner_user_id, s.created_at, s.updated_at,
               u.email as owner_email,
               COUNT(m.id) as total_items
        FROM shops s
        LEFT JOIN users u ON u.id = s.owner_user_id
        LEFT JOIN menu_items m ON m.shop_id = s.id
        GROUP BY s.id
        ORDER BY s.id ASC
        """
    )
    for s in shops:
        s["is_active"] = int(s.get("is_active", 1))
        s["operational_status"] = str(s.get("operational_status") or "OPEN").upper()
        s["total_items"] = int(s.get("total_items") or 0)
    return jsonify({"success": True, "shops": shops}), 200


@admin_bp.post("/shops")
@role_required(["admin"])
def add_shop():
    """Creates a new food court stall in one atomic DB transaction."""
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    slug = str(data.get("slug") or name.lower().replace(" ", "-")).strip()
    description = str(data.get("description", "")).strip()
    category = str(data.get("category", "Multi-Cuisine")).strip()
    operational_status = str(data.get("operational_status", "OPEN")).strip().upper()

    if operational_status not in ALLOWED_OPERATIONAL_STATUSES:
        operational_status = "OPEN"
    if not name:
        return jsonify({"success": False, "message": "Stall name is required."}), 400

    with DB.transaction() as tx:
        existing = tx.get_one(
            "SELECT id FROM shops WHERE LOWER(name) = %s OR LOWER(slug) = %s LIMIT 1",
            (name.lower(), slug.lower()),
        )
        if existing:
            return jsonify({
                "success": False,
                "message": f"A stall with name '{name}' or slug '{slug}' already exists."
            }), 409

        shop_id = tx.execute(
            """INSERT INTO shops (name, slug, description, category, is_active, operational_status, created_by_admin)
               VALUES (%s, %s, %s, %s, 1, %s, 1)""",
            (name, slug, description, category, operational_status),
        )
        AuditService.log_action(
            actor_id=session.get("user_id"),
            action="SHOP_CREATED",
            entity_type="shop",
            entity_id=shop_id,
            details={"name": name, "slug": slug, "category": category, "operational_status": operational_status},
            tx=tx,
        )

    return jsonify({
        "success": True,
        "message": f"Stall '{name}' created successfully.",
        "shop_id": shop_id,
        "shop": {
            "id": shop_id, "name": name, "slug": slug, "description": description,
            "category": category, "is_active": 1, "operational_status": operational_status,
            "owner_user_id": None, "owner_email": None, "total_items": 0,
        },
    }), 201


@admin_bp.put("/shops/<int:shop_id>")
@role_required(["admin"])
def update_shop(shop_id):
    """Updates stall profile details and logs audit action."""
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

    actor_id = session.get("user_id")
    AuditService.log_action(
        actor_id=actor_id,
        action="SHOP_UPDATED",
        entity_type="shop",
        entity_id=shop_id,
        details={"name": name, "slug": slug, "category": category}
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


@admin_bp.delete("/shops/<int:shop_id>")
@role_required(["admin"])
def delete_shop(shop_id):
    """Permanently deletes a stall only when it has no historical orders."""
    with DB.transaction() as tx:
        shop = tx.get_one("SELECT id, name FROM shops WHERE id = %s", (shop_id,))
        if not shop:
            return jsonify({"success": False, "message": "Shop not found."}), 404

        order_count = tx.get_one("SELECT COUNT(id) AS total FROM orders WHERE shop_id = %s", (shop_id,))
        if int((order_count or {}).get("total") or 0) > 0:
            return jsonify({
                "success": False,
                "message": "This stall cannot be permanently deleted because it has order history. Deactivate it instead."
            }), 409

        tx.execute("DELETE FROM shops WHERE id = %s", (shop_id,))
        AuditService.log_action(
            actor_id=session.get("user_id"), action="SHOP_DELETED", entity_type="shop",
            entity_id=shop_id, details={"shop_name": shop["name"]}, tx=tx
        )

    return jsonify({"success": True, "message": f"Stall '{shop['name']}' deleted successfully.",
                    "shop_id": shop_id}), 200


@admin_bp.put("/shops/<int:shop_id>/status")
@role_required(["admin"])
def toggle_shop_status(shop_id):
    """Toggles shop active status atomically."""
    with DB.transaction() as tx:
        shop = tx.get_one("SELECT id, is_active, name FROM shops WHERE id = %s", (shop_id,))
        if not shop:
            return jsonify({"success": False, "message": "Shop not found."}), 404
        data = request.get_json(silent=True) or {}
        new_status = 1 if data["is_active"] else 0 if "is_active" in data else 0 if shop["is_active"] == 1 else 1
        tx.execute("UPDATE shops SET is_active = %s WHERE id = %s", (new_status, shop_id))
        AuditService.log_action(
            actor_id=session.get("user_id"), action="SHOP_STATUS_TOGGLED", entity_type="shop",
            entity_id=shop_id, details={"shop_name": shop["name"], "is_active": new_status}, tx=tx
        )

    status_text = "Activated" if new_status == 1 else "Deactivated"
    return jsonify({"success": True, "message": f"Stall '{shop['name']}' {status_text}.",
                    "shop_id": shop_id, "is_active": new_status}), 200


@admin_bp.put("/shops/<int:shop_id>/operational-status")
@role_required(["admin"])
def update_shop_operational_status(shop_id):
    """Sets shop operational status atomically."""
    data = request.get_json(silent=True) or {}
    new_status = str(data.get("operational_status") or data.get("status") or "").strip().upper()
    if new_status not in ALLOWED_OPERATIONAL_STATUSES:
        return jsonify({
            "success": False,
            "message": f"Invalid operational status. Must be one of {sorted(list(ALLOWED_OPERATIONAL_STATUSES))}."
        }), 400

    with DB.transaction() as tx:
        shop = tx.get_one("SELECT id, name, operational_status FROM shops WHERE id = %s", (shop_id,))
        if not shop:
            return jsonify({"success": False, "message": "Shop not found."}), 404
        old_status = str(shop.get("operational_status") or "OPEN").upper()
        tx.execute("UPDATE shops SET operational_status = %s WHERE id = %s", (new_status, shop_id))
        AuditService.log_action(
            actor_id=session.get("user_id"), action="SHOP_OPERATIONAL_STATUS_CHANGED", entity_type="shop",
            entity_id=shop_id,
            details={"shop_name": shop["name"], "old_status": old_status, "new_status": new_status},
            tx=tx,
        )

    return jsonify({"success": True, "message": f"Stall '{shop['name']}' operational status updated to {new_status}.",
                    "shop_id": shop_id, "operational_status": new_status}), 200


@admin_bp.get("/vendors")
@role_required(["admin"])
def get_admin_vendors():
    """Lists all vendor accounts with their assigned stall."""
    vendors = DB.query(
        """
        SELECT u.id, u.email, u.role, u.is_active, u.created_at,
               s.id as assigned_shop_id, s.name as assigned_shop_name,
               s.is_active as assigned_shop_is_active, s.operational_status as assigned_shop_status
        FROM users u
        LEFT JOIN shops s ON s.owner_user_id = u.id
        WHERE u.role = 'vendor'
        ORDER BY u.id DESC
        """
    )
    for v in vendors:
        v["is_active"] = int(v.get("is_active", 1))
        if v.get("assigned_shop_status"):
            v["assigned_shop_status"] = str(v["assigned_shop_status"]).upper()
    return jsonify({"success": True, "vendors": vendors}), 200


@admin_bp.post("/vendors")
@role_required(["admin"])
def create_vendor():
    """Creates a vendor account atomically, including optional stall assignment."""
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", "")).strip()
    shop_id = data.get("shop_id")

    if not email or not password:
        return jsonify({"success": False, "message": "Vendor email and initial password are required."}), 400
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return jsonify({"success": False, "message": "Invalid email address format."}), 400

    pwd_hash = hash_password(password)

    with DB.transaction() as tx:
        existing = tx.get_one("SELECT id FROM users WHERE LOWER(email) = %s", (email,))
        if existing:
            return jsonify({"success": False, "message": "An account with this email already exists."}), 409

        assigned_shop_name = None
        target_shop = None
        if shop_id:
            target_shop = tx.get_one("SELECT id, name, is_active FROM shops WHERE id = %s", (shop_id,))
            if not target_shop or not target_shop.get("is_active"):
                return jsonify({"success": False, "message": "Cannot assign vendor to an inactive or non-existent stall."}), 400
            assigned_shop_name = target_shop["name"]

        user_id = tx.execute(
            "INSERT INTO users (email, password_hash, role, is_active) VALUES (%s, %s, 'vendor', 1)",
            (email, pwd_hash),
        )

        if shop_id:
            tx.execute("UPDATE shops SET owner_user_id = NULL WHERE owner_user_id = %s", (user_id,))
            tx.execute("UPDATE shops SET owner_user_id = %s WHERE id = %s", (user_id, shop_id))

        AuditService.log_action(
            actor_id=session.get("user_id"), action="VENDOR_CREATED", entity_type="user",
            entity_id=user_id,
            details={"email": email, "assigned_shop_id": shop_id, "assigned_shop_name": assigned_shop_name},
            tx=tx,
        )

    return jsonify({
        "success": True,
        "message": f"Vendor account '{email}' created successfully.",
        "user_id": user_id,
        "assigned_shop_id": shop_id,
        "assigned_shop_name": assigned_shop_name,
        "vendor": {
            "id": user_id, "email": email, "role": "vendor", "is_active": 1,
            "assigned_shop_id": shop_id, "assigned_shop_name": assigned_shop_name,
            "assigned_shop_status": target_shop.get("operational_status") if target_shop else None,
        },
    }), 201


@admin_bp.delete("/vendors/<int:user_id>")
@role_required(["admin"])
def delete_vendor(user_id):
    """Permanently deletes a vendor account and unassigns its stall atomically."""
    with DB.transaction() as tx:
        vendor = tx.get_one("SELECT id, email, role FROM users WHERE id = %s AND role = 'vendor'", (user_id,))
        if not vendor:
            return jsonify({"success": False, "message": "Vendor user not found."}), 404

        assigned_shop = tx.get_one("SELECT id, name FROM shops WHERE owner_user_id = %s LIMIT 1", (user_id,))
        tx.execute("UPDATE shops SET owner_user_id = NULL WHERE owner_user_id = %s", (user_id,))
        tx.execute("DELETE FROM users WHERE id = %s AND role = 'vendor'", (user_id,))
        AuditService.log_action(
            actor_id=session.get("user_id"), action="VENDOR_DELETED", entity_type="user",
            entity_id=user_id,
            details={"vendor_email": vendor["email"],
                     "unassigned_shop_id": assigned_shop["id"] if assigned_shop else None,
                     "unassigned_shop_name": assigned_shop["name"] if assigned_shop else None},
            tx=tx,
        )

    return jsonify({"success": True, "message": f"Vendor '{vendor['email']}' deleted successfully.",
                    "vendor_id": user_id,
                    "unassigned_shop_id": assigned_shop["id"] if assigned_shop else None}), 200


@admin_bp.put("/vendors/<int:user_id>/shop")
@role_required(["admin"])
def assign_vendor_shop(user_id):
    """Assigns or unassigns a vendor to a stall atomically."""
    data = request.get_json(silent=True) or {}
    shop_id = data.get("shop_id")

    with DB.transaction() as tx:
        vendor = tx.get_one("SELECT id, email, role FROM users WHERE id = %s AND role = 'vendor'", (user_id,))
        if not vendor:
            return jsonify({"success": False, "message": "Vendor user not found."}), 404

        actor_id = session.get("user_id")
        if shop_id is None or shop_id == 0 or shop_id == "null":
            tx.execute("UPDATE shops SET owner_user_id = NULL WHERE owner_user_id = %s", (user_id,))
            AuditService.log_action(actor_id=actor_id, action="VENDOR_UNASSIGNED", entity_type="user",
                                    entity_id=user_id, details={"vendor_email": vendor["email"]}, tx=tx)
            return jsonify({"success": True, "message": f"Vendor '{vendor['email']}' unassigned from stall.",
                            "vendor_id": user_id, "shop_id": None}), 200

        shop = tx.get_one("SELECT id, name, is_active, operational_status FROM shops WHERE id = %s", (shop_id,))
        if not shop:
            return jsonify({"success": False, "message": "Target shop not found."}), 404
        if not shop.get("is_active"):
            return jsonify({"success": False, "message": "Cannot assign vendor to an inactive stall."}), 400

        tx.execute("UPDATE shops SET owner_user_id = NULL WHERE owner_user_id = %s", (user_id,))
        tx.execute("UPDATE shops SET owner_user_id = NULL WHERE id = %s", (shop_id,))
        tx.execute("UPDATE shops SET owner_user_id = %s WHERE id = %s", (user_id, shop_id))
        AuditService.log_action(
            actor_id=actor_id, action="VENDOR_ASSIGNED", entity_type="user", entity_id=user_id,
            details={"vendor_email": vendor["email"], "shop_id": shop_id, "shop_name": shop["name"]}, tx=tx
        )

    return jsonify({"success": True, "message": f"Vendor '{vendor['email']}' successfully assigned to stall '{shop['name']}'.",
                    "vendor_id": user_id, "shop_id": shop_id, "shop_name": shop["name"],
                    "assigned_shop_status": shop.get("operational_status")}), 200


@admin_bp.get("/customers")
@role_required(["admin"])
def get_admin_customers():
    """Returns customer list with profile metadata, wallet balance, and order volume."""
    search_q = request.args.get("q", "").strip().lower()

    sql = """
        SELECT u.id, u.email, u.is_active, u.is_temporary, u.account_expires_at, u.created_at,
               cp.full_name, cp.customer_type, cp.identifier, cp.mobile,
               cp.wallet_balance,
               COUNT(o.id) as total_orders,
               COALESCE(SUM(o.total_amount), 0) as total_spent
        FROM users u
        LEFT JOIN customer_profiles cp ON cp.user_id = u.id
        LEFT JOIN orders o ON o.customer_id = u.id
        WHERE u.role = 'customer'
    """
    params = []

    if search_q:
        sql += " AND (LOWER(u.email) LIKE %s OR LOWER(cp.full_name) LIKE %s OR cp.mobile LIKE %s OR cp.identifier LIKE %s)"
        pattern = f"%{search_q}%"
        params.extend([pattern, pattern, pattern, pattern])

    sql += """
        GROUP BY u.id
        ORDER BY u.id DESC
        LIMIT 100
    """

    customers = DB.query(sql, tuple(params))
    for c in customers:
        c["is_active"] = int(c.get("is_active", 1))
        c["is_temporary"] = int(c.get("is_temporary", 0))
        c["wallet_balance"] = float(c.get("wallet_balance") or 0.0)
        c["total_orders"] = int(c.get("total_orders") or 0)
        c["total_spent"] = float(c.get("total_spent") or 0.0)

    return jsonify({"success": True, "customers": customers}), 200


@admin_bp.put("/customers/<int:user_id>/status")
@role_required(["admin"])
def toggle_customer_status(user_id):
    """Activates or suspends a customer account and logs audit action."""
    user = DB.get_one("SELECT id, is_active, email FROM users WHERE id = %s AND role = 'customer'", (user_id,))
    if not user:
        return jsonify({"success": False, "message": "Customer not found."}), 404

    data = request.get_json(silent=True) or {}
    if "is_active" in data:
        new_status = 1 if data["is_active"] else 0
    else:
        new_status = 0 if user["is_active"] == 1 else 1

    DB.execute("UPDATE users SET is_active = %s WHERE id = %s", (new_status, user_id))

    actor_id = session.get("user_id")
    status_text = "activated" if new_status == 1 else "suspended"
    AuditService.log_action(
        actor_id=actor_id,
        action="CUSTOMER_STATUS_TOGGLED",
        entity_type="user",
        entity_id=user_id,
        details={"email": user["email"], "is_active": new_status, "status_text": status_text}
    )

    return jsonify({
        "success": True,
        "message": f"Customer '{user['email']}' {status_text}.",
        "is_active": new_status
    }), 200


# ============================================================================
# TEMPORARY CUSTOMER ACCOUNTS
# ============================================================================

@admin_bp.post("/customers/temporary")
@role_required(["admin"])
def create_temporary_customer():
    """Creates a temporary student/faculty/guest customer account with expiry."""
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", "")).strip()
    customer_type = str(data.get("customer_type", "guest")).strip().lower()
    full_name = str(data.get("full_name", "Temporary User")).strip()
    identifier = str(data.get("identifier", "")).strip() or None
    mobile = str(data.get("mobile", "")).strip() or None
    try:
        duration_hours = int(data.get("duration_hours", 24))
    except (TypeError, ValueError):
        duration_hours = 24
    if customer_type not in {"student", "faculty", "guest"}:
        return jsonify({"success": False, "message": "Customer type must be student, faculty, or guest."}), 400
    if not email or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return jsonify({"success": False, "message": "A valid email address is required."}), 400
    if len(password) < 8:
        return jsonify({"success": False, "message": "Temporary account password must contain at least 8 characters."}), 400
    if not full_name:
        return jsonify({"success": False, "message": "Full name is required."}), 400
    if duration_hours < 1 or duration_hours > 720:
        return jsonify({"success": False, "message": "Duration must be between 1 hour and 30 days."}), 400
    expires_at = datetime.now().replace(microsecond=0) + __import__("datetime").timedelta(hours=duration_hours)
    pwd_hash = hash_password(password)
    with DB.transaction() as tx:
        existing = tx.get_one("SELECT id FROM users WHERE LOWER(email) = %s", (email,))
        if existing:
            return jsonify({"success": False, "message": "An account with this email already exists."}), 409
        user_id = tx.execute(
            """INSERT INTO users (email, password_hash, role, is_active, is_temporary, account_expires_at)
               VALUES (%s, %s, 'customer', 1, 1, %s)""",
            (email, pwd_hash, expires_at.strftime("%Y-%m-%d %H:%M:%S")),
        )
        tx.execute(
            """INSERT INTO customer_profiles (user_id, customer_type, full_name, identifier, mobile)
               VALUES (%s, %s, %s, %s, %s)""",
            (user_id, customer_type, full_name, identifier, mobile),
        )
        AuditService.log_action(actor_id=session.get("user_id"), action="TEMPORARY_CUSTOMER_CREATED", entity_type="user",
                                entity_id=user_id, details={"email": email, "customer_type": customer_type,
                                "expires_at": expires_at.strftime("%Y-%m-%d %H:%M:%S")}, tx=tx)
    return jsonify({"success": True, "message": f"Temporary {customer_type} account created successfully.",
                    "account": {"id": user_id, "email": email, "customer_type": customer_type, "full_name": full_name,
                    "identifier": identifier, "mobile": mobile, "is_active": 1, "is_temporary": 1,
                    "account_expires_at": expires_at.strftime("%Y-%m-%d %H:%M:%S")}}), 201


@admin_bp.delete("/customers/<int:user_id>/temporary")
@role_required(["admin"])
def delete_temporary_customer(user_id):
    """Deletes only temporary customer accounts created by the admin."""
    with DB.transaction() as tx:
        user = tx.get_one("SELECT id, email, is_temporary, role FROM users WHERE id = %s AND role = 'customer'", (user_id,))
        if not user:
            return jsonify({"success": False, "message": "Customer account not found."}), 404
        if not int(user.get("is_temporary") or 0):
            return jsonify({"success": False, "message": "Permanent customer accounts cannot be deleted here."}), 400
        tx.execute("DELETE FROM users WHERE id = %s", (user_id,))
        AuditService.log_action(actor_id=session.get("user_id"), action="TEMPORARY_CUSTOMER_DELETED", entity_type="user",
                                entity_id=user_id, details={"email": user["email"]}, tx=tx)
    return jsonify({"success": True, "message": "Temporary account deleted."}), 200


# Backward-compatible general users endpoint
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
    for u in users:
        u["is_active"] = int(u.get("is_active", 1))
    return jsonify({"success": True, "users": users}), 200


@admin_bp.put("/users/<int:user_id>/status")
@role_required(["admin"])
def toggle_user_status(user_id):
    user = DB.get_one("SELECT id, is_active, email, role FROM users WHERE id = %s", (user_id,))
    if not user:
        return jsonify({"success": False, "message": "User not found."}), 404

    # Superuser protection: cannot suspend another admin or oneself
    current_admin_id = session.get("user_id")
    if user["role"] == "admin" and user["id"] == current_admin_id:
        return jsonify({"success": False, "message": "Administrators cannot suspend their own account."}), 400

    data = request.get_json(silent=True) or {}
    if "is_active" in data:
        new_status = 1 if data["is_active"] else 0
    else:
        new_status = 0 if user["is_active"] == 1 else 1

    DB.execute("UPDATE users SET is_active = %s WHERE id = %s", (new_status, user_id))

    actor_id = session.get("user_id")
    status_text = "activated" if new_status == 1 else "suspended"
    AuditService.log_action(
        actor_id=actor_id,
        action="USER_STATUS_TOGGLED",
        entity_type="user",
        entity_id=user_id,
        details={"email": user["email"], "role": user["role"], "is_active": new_status, "status_text": status_text}
    )

    return jsonify({"success": True, "message": f"User status updated.", "is_active": new_status}), 200


# ============================================================================
# GLOBAL ORDER MONITORING
# ============================================================================

@admin_bp.get("/orders")
@role_required(["admin"])
def get_admin_orders():
    """
    Global order feed across all stalls.
    Supports filtering by status, shop_id, payment_status, date, and text query.
    """
    status_filter = request.args.get("status")
    shop_filter = request.args.get("shop_id")
    payment_filter = request.args.get("payment_status")
    date_filter = request.args.get("date")
    search_q = request.args.get("q", "").strip().lower()

    try:
        limit = max(1, min(100, int(request.args.get("limit", 50))))
        offset = max(0, int(request.args.get("offset", 0)))
    except (ValueError, TypeError):
        limit = 50
        offset = 0

    sql = """
        SELECT o.id, o.order_reference, o.customer_id, o.shop_id, o.total_amount,
               o.order_status, o.payment_status, o.payment_method, o.pickup_otp,
               o.created_at, o.payment_time, o.preparing_time, o.ready_time,
               o.completed_time, o.cancellation_time,
               s.name as shop_name, s.slug as shop_slug,
               cp.full_name as customer_name, cp.customer_type, cp.identifier, cp.mobile,
               u.email as customer_email
        FROM orders o
        INNER JOIN shops s ON s.id = o.shop_id
        LEFT JOIN customer_profiles cp ON cp.user_id = o.customer_id
        LEFT JOIN users u ON u.id = o.customer_id
        WHERE 1=1
    """
    params = []

    if status_filter:
        sql += " AND o.order_status = %s"
        params.append(status_filter.lower())

    if shop_filter and str(shop_filter).isdigit():
        sql += " AND o.shop_id = %s"
        params.append(int(shop_filter))

    if payment_filter:
        sql += " AND o.payment_status = %s"
        params.append(payment_filter.lower())

    if date_filter:
        sql += " AND DATE(o.created_at) = %s"
        params.append(date_filter)

    if search_q:
        sql += " AND (LOWER(o.order_reference) LIKE %s OR LOWER(cp.full_name) LIKE %s OR LOWER(u.email) LIKE %s)"
        pattern = f"%{search_q}%"
        params.extend([pattern, pattern, pattern])

    sql += " ORDER BY o.id DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    orders = DB.query(sql, tuple(params))

    # Fetch order items summaries
    for order in orders:
        order["total_amount"] = float(order.get("total_amount") or 0.0)
        items = DB.query(
            "SELECT item_name, quantity, unit_price, subtotal FROM order_items WHERE order_id = %s",
            (order["id"],),
        )
        order["items"] = items
        order["items_summary"] = ", ".join(f"{i['quantity']}x {i['item_name']}" for i in items)

    return jsonify({"success": True, "orders": orders, "limit": limit, "offset": offset}), 200


# ============================================================================
# GLOBAL PAYMENT MONITORING
# ============================================================================

@admin_bp.get("/payments")
@role_required(["admin"])
def get_admin_payments():
    """
    Global payment monitoring across all transactions.
    Supports filtering by status, provider, method, date, and text query.
    Returns transaction list and aggregate totals.
    """
    status_filter = request.args.get("status")
    provider_filter = request.args.get("provider")
    method_filter = request.args.get("method")
    date_filter = request.args.get("date")
    search_q = request.args.get("q", "").strip().lower()

    try:
        limit = max(1, min(100, int(request.args.get("limit", 50))))
        offset = max(0, int(request.args.get("offset", 0)))
    except (ValueError, TypeError):
        limit = 50
        offset = 0

    sql = """
        SELECT p.id, p.order_id, p.customer_id, p.provider, p.method, p.amount,
               p.currency, p.status, p.transaction_ref, p.gateway_order_id,
               p.gateway_payment_id, p.failure_reason, p.paid_at, p.refunded_at,
               p.created_at, p.updated_at,
               o.order_reference, o.order_status,
               s.name as shop_name,
               u.email as customer_email,
               cp.full_name as customer_name
        FROM payments p
        INNER JOIN orders o ON o.id = p.order_id
        INNER JOIN shops s ON s.id = o.shop_id
        LEFT JOIN users u ON u.id = p.customer_id
        LEFT JOIN customer_profiles cp ON cp.user_id = p.customer_id
        WHERE 1=1
    """
    params = []

    if status_filter:
        sql += " AND p.status = %s"
        params.append(status_filter.lower())

    if provider_filter:
        sql += " AND p.provider = %s"
        params.append(provider_filter.lower())

    if method_filter:
        sql += " AND LOWER(p.method) LIKE %s"
        params.append(f"%{method_filter.lower()}%")

    if date_filter:
        sql += " AND DATE(p.created_at) = %s"
        params.append(date_filter)

    if search_q:
        sql += " AND (LOWER(p.transaction_ref) LIKE %s OR LOWER(o.order_reference) LIKE %s OR LOWER(p.gateway_order_id) LIKE %s OR LOWER(u.email) LIKE %s)"
        pattern = f"%{search_q}%"
        params.extend([pattern, pattern, pattern, pattern])

    sql += " ORDER BY p.id DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    payments = DB.query(sql, tuple(params))
    for p in payments:
        p["amount"] = float(p.get("amount") or 0.0)

    # Aggregated metrics for overview
    summary = DB.get_one(
        """
        SELECT COALESCE(SUM(CASE WHEN status = 'successful' THEN amount ELSE 0 END), 0) as total_collected,
               COALESCE(SUM(CASE WHEN status = 'refunded' THEN amount ELSE 0 END), 0) as total_refunded,
               SUM(CASE WHEN status = 'successful' THEN 1 ELSE 0 END) as success_count,
               SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_count,
               SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_count,
               SUM(CASE WHEN status = 'refunded' THEN 1 ELSE 0 END) as refunded_count,
               COUNT(id) as total_transactions
        FROM payments
        """
    ) or {}

    return jsonify({
        "success": True,
        "payments": payments,
        "summary": {
            "total_collected": float(summary.get("total_collected") or 0.0),
            "total_refunded": float(summary.get("total_refunded") or 0.0),
            "success_count": int(summary.get("success_count") or 0),
            "pending_count": int(summary.get("pending_count") or 0),
            "failed_count": int(summary.get("failed_count") or 0),
            "refunded_count": int(summary.get("refunded_count") or 0),
            "total_transactions": int(summary.get("total_transactions") or 0),
        },
        "limit": limit,
        "offset": offset
    }), 200


# ============================================================================
# AUDIT LOGGING VIEW
# ============================================================================

@admin_bp.get("/audit-logs")
@role_required(["admin"])
def get_audit_logs():
    """
    Returns administrative and operational audit trail with actor details.
    Supports filtering by action, entity_type, actor_id.
    """
    action_filter = request.args.get("action")
    entity_filter = request.args.get("entity_type")
    actor_filter = request.args.get("actor_id")

    try:
        limit = max(1, min(200, int(request.args.get("limit", 100))))
        offset = max(0, int(request.args.get("offset", 0)))
    except (ValueError, TypeError):
        limit = 100
        offset = 0

    sql = """
        SELECT a.id, a.actor_id, a.action, a.entity_type, a.entity_id, a.details, a.created_at,
               u.email as actor_email, u.role as actor_role
        FROM audit_logs a
        LEFT JOIN users u ON u.id = a.actor_id
        WHERE 1=1
    """
    params = []

    if action_filter:
        sql += " AND a.action = %s"
        params.append(action_filter.upper())

    if entity_filter:
        sql += " AND a.entity_type = %s"
        params.append(entity_filter.lower())

    if actor_filter and str(actor_filter).isdigit():
        sql += " AND a.actor_id = %s"
        params.append(int(actor_filter))

    sql += " ORDER BY a.id DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    logs = DB.query(sql, tuple(params))
    return jsonify({"success": True, "audit_logs": logs, "limit": limit, "offset": offset}), 200
