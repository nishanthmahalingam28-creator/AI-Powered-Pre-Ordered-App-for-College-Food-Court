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
               (SELECT COUNT(m.id)
                FROM menu_items m
                WHERE m.shop_id = s.id AND m.is_available = 1) AS total_items
        FROM shops s
        WHERE s.is_active = 1
        ORDER BY s.id ASC
        """
    )
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


@menu_bp.get("/shops/admin-created")
def get_admin_created_shops():
    """Returns only active shops that were created through the Admin shop-management flow."""
    shops = DB.query(
        """
        SELECT s.id, s.name, s.slug, s.description, s.category, s.image_url, s.is_active,
               s.operational_status, s.created_at, s.updated_at,
               (SELECT COUNT(m.id)
                FROM menu_items m
                WHERE m.shop_id = s.id AND m.is_available = 1) AS total_items
        FROM shops s
        WHERE s.is_active = 1
          AND s.created_by_admin = 1
        ORDER BY s.id ASC
        """
    )
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


@menu_bp.get("/menu/today")
def get_today_daily_menu():
    """
    Returns only food items explicitly published by vendors in today's daily menu survey,
    grouped into breakfast, lunch and dinner. If a shop has not submitted a survey,
    it is omitted rather than exposing an unconfirmed daily menu.
    """
    raw_shop_id = request.args.get("shop_id")
    params = []
    sql = """
        SELECT d.id, d.shop_id, d.menu_item_id, d.meal_period, d.item_name,
               d.price, d.quantity, d.is_available,
               s.name AS shop_name, s.slug AS shop_slug
        FROM vendor_daily_menu_items d
        INNER JOIN vendor_daily_surveys v ON v.id = d.survey_id
        INNER JOIN shops s ON s.id = d.shop_id
        WHERE v.survey_date = CURDATE()
          AND v.is_serving_today = 1
          AND d.is_available = 1
          AND d.quantity > 0
          AND s.is_active = 1
          AND s.operational_status = 'OPEN'
    """
    if raw_shop_id:
        try:
            shop_id = int(raw_shop_id)
            if shop_id <= 0:
                raise ValueError
            sql += " AND d.shop_id = %s"
            params.append(shop_id)
        except (ValueError, TypeError):
            return jsonify({"success": False, "message": "Invalid shop_id format."}), 400

    sql += " ORDER BY s.name ASC, FIELD(d.meal_period, 'breakfast', 'lunch', 'dinner'), d.item_name ASC"
    rows = DB.query(sql, tuple(params))

    grouped = {}
    for row in rows:
        shop_key = str(row["shop_id"])
        if shop_key not in grouped:
            grouped[shop_key] = {
                "shop_id": row["shop_id"],
                "shop_name": row["shop_name"],
                "shop_slug": row["shop_slug"],
                "breakfast": [],
                "lunch": [],
                "dinner": [],
            }
        grouped[shop_key][row["meal_period"]].append({
            "daily_menu_id": row["id"],
            "menu_item_id": row["menu_item_id"],
            "name": row["item_name"],
            "price": float(row["price"]),
            "quantity": int(row["quantity"]),
            "is_available": bool(row["is_available"]),
            "meal_period": row["meal_period"],
        })

    return jsonify({
        "success": True,
        "date": __import__("datetime").datetime.now().strftime("%Y-%m-%d"),
        "shops": list(grouped.values()),
    }), 200
