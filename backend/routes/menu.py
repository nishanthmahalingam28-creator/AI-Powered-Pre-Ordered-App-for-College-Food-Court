from flask import Blueprint, jsonify, request
from db import DB

menu_bp = Blueprint("menu", __name__)


@menu_bp.get("/shops")
def get_shops():
    """Returns all active food court stalls for customers."""
    shops = DB.query(
        """
        SELECT s.id, s.name, s.slug, s.description, s.category, s.image_url, s.is_active,
               s.operational_status, s.created_at, s.updated_at,
               COUNT(m.id) as total_items
        FROM shops s
        LEFT JOIN menu_items m ON m.shop_id = s.id AND m.is_available = 1
        INNER JOIN audit_logs al
            ON al.entity_type = 'shop'
           AND al.action = 'SHOP_CREATED'
           AND al.entity_id = CAST(s.id AS CHAR)
        WHERE s.is_active = 1
        GROUP BY s.id
        ORDER BY s.id ASC
        """
    )
    # Ensure sanitized, clean output without internal secrets
    safe_shops = []
    for s in shops:
        safe_shops.append({
            "id": s["id"],
            "name": s["name"],
            "slug": s["slug"],
            "description": s.get("description") or "",
            "category": s.get("category") or "Multi-Cuisine",
            "image_url": s.get("image_url"),
            "is_active": bool(s.get("is_active", 1)),
            "operational_status": str(s.get("operational_status") or "OPEN").upper(),
            "total_items": int(s.get("total_items") or 0),
            "created_at": str(s.get("created_at") or ""),
            "updated_at": str(s.get("updated_at") or ""),
        })
    return jsonify({"success": True, "shops": safe_shops}), 200


@menu_bp.get("/shops/<int:shop_id>")
def get_shop_by_id(shop_id):
    """Returns details for a single active food court stall."""
    shop = DB.get_one(
        """
        SELECT s.id, s.name, s.slug, s.description, s.category, s.image_url, s.is_active,
               s.operational_status, s.created_at, s.updated_at,
               COUNT(m.id) as total_items
        FROM shops s
        LEFT JOIN menu_items m ON m.shop_id = s.id AND m.is_available = 1
        WHERE s.id = %s AND s.is_active = 1
        GROUP BY s.id
        LIMIT 1
        """,
        (shop_id,),
    )
    if not shop:
        return jsonify({"success": False, "message": "Stall not found or currently inactive."}), 404

    return jsonify({
        "success": True,
        "shop": {
            "id": shop["id"],
            "name": shop["name"],
            "slug": shop["slug"],
            "description": shop.get("description") or "",
            "category": shop.get("category") or "Multi-Cuisine",
            "image_url": shop.get("image_url"),
            "is_active": bool(shop.get("is_active", 1)),
            "operational_status": str(shop.get("operational_status") or "OPEN").upper(),
            "total_items": int(shop.get("total_items") or 0),
            "created_at": str(shop.get("created_at") or ""),
            "updated_at": str(shop.get("updated_at") or ""),
        }
    }), 200


@menu_bp.get("/menu")
def get_menu():
    """
    Returns menu catalog.
    Supports filtering by shop_id, shop name, category, and text search query.
    Customers only receive items from active shops.
    """
    raw_shop_id = request.args.get("shop_id")
    shop_name = request.args.get("shop")
    category = request.args.get("category")
    search_q = request.args.get("q", "").strip().lower()

    sql = """
        SELECT m.id, m.shop_id, m.name, m.description, m.price, m.category,
               m.quantity, m.is_available, m.image_url, m.created_at, m.updated_at,
               s.name as shop_name, s.slug as shop_slug
        FROM menu_items m
        INNER JOIN shops s ON s.id = m.shop_id
        WHERE s.is_active = 1
    """
    params = []

    if raw_shop_id:
        try:
            shop_id = int(raw_shop_id)
            if shop_id <= 0:
                return jsonify({"success": False, "message": "Invalid shop_id."}), 400
            sql += " AND m.shop_id = %s"
            params.append(shop_id)
        except (ValueError, TypeError):
            return jsonify({"success": False, "message": "Invalid shop_id format."}), 400
    elif shop_name:
        sql += " AND LOWER(s.name) = %s"
        params.append(shop_name.strip().lower())

    if category and category.lower() != "all":
        sql += " AND LOWER(m.category) = %s"
        params.append(category.strip().lower())

    if search_q:
        sql += " AND (LOWER(m.name) LIKE %s OR LOWER(m.description) LIKE %s OR LOWER(s.name) LIKE %s)"
        pattern = f"%{search_q}%"
        params.extend([pattern, pattern, pattern])

    sql += " ORDER BY m.is_available DESC, m.name ASC"

    raw_items = DB.query(sql, tuple(params))
    items = []
    for item in raw_items:
        items.append({
            "id": item["id"],
            "shop_id": item["shop_id"],
            "shop_name": item["shop_name"],
            "shop_slug": item["shop_slug"],
            "name": item["name"],
            "description": item.get("description") or "",
            "price": float(item["price"]),
            "category": item.get("category") or "General",
            "quantity": int(item.get("quantity") or 0),
            "is_available": int(item.get("is_available") or 0),
            "image_url": item.get("image_url"),
            "created_at": str(item.get("created_at") or ""),
            "updated_at": str(item.get("updated_at") or ""),
        })

    return jsonify({"success": True, "count": len(items), "items": items}), 200


@menu_bp.get("/menu/<int:item_id>")
def get_menu_item(item_id):
    """Returns details for a single food menu item."""
    item = DB.get_one(
        """
        SELECT m.id, m.shop_id, m.name, m.description, m.price, m.category,
               m.quantity, m.is_available, m.image_url, m.created_at, m.updated_at,
               s.name as shop_name, s.is_active as shop_active
        FROM menu_items m
        INNER JOIN shops s ON s.id = m.shop_id
        WHERE m.id = %s
        LIMIT 1
        """,
        (item_id,),
    )
    if not item or not item.get("shop_active"):
        return jsonify({"success": False, "message": "Food item not found or stall is inactive."}), 404

    return jsonify({
        "success": True,
        "item": {
            "id": item["id"],
            "shop_id": item["shop_id"],
            "shop_name": item["shop_name"],
            "name": item["name"],
            "description": item.get("description") or "",
            "price": float(item["price"]),
            "category": item.get("category") or "General",
            "quantity": int(item.get("quantity") or 0),
            "is_available": int(item.get("is_available") or 0),
            "image_url": item.get("image_url"),
            "created_at": str(item.get("created_at") or ""),
            "updated_at": str(item.get("updated_at") or ""),
        }
    }), 200


@menu_bp.get("/categories")
def get_categories():
    """
    Returns available food categories.
    Supports optional shop_id or shop name to scope categories strictly to the requested stall.
    """
    raw_shop_id = request.args.get("shop_id")
    shop_name = request.args.get("shop")

    sql = """
        SELECT DISTINCT m.category
        FROM menu_items m
        INNER JOIN shops s ON s.id = m.shop_id
        WHERE s.is_active = 1 AND m.is_available = 1
    """
    params = []

    if raw_shop_id:
        try:
            shop_id = int(raw_shop_id)
            sql += " AND m.shop_id = %s"
            params.append(shop_id)
        except (ValueError, TypeError):
            return jsonify({"success": False, "message": "Invalid shop_id format."}), 400
    elif shop_name:
        sql += " AND LOWER(s.name) = %s"
        params.append(shop_name.strip().lower())

    sql += " ORDER BY m.category ASC"
    rows = DB.query(sql, tuple(params))
    categories = [r["category"] for r in rows if r.get("category")]
    return jsonify({"success": True, "categories": categories}), 200
