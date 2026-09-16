from flask import Blueprint, jsonify, request
from db import DB

menu_bp = Blueprint("menu", __name__)


@menu_bp.get("/shops")
def get_shops():
    shops = DB.query(
        """
        SELECT s.id, s.name, s.slug, s.description, s.category, s.image_url, s.is_active,
               COUNT(m.id) as total_items
        FROM shops s
        LEFT JOIN menu_items m ON m.shop_id = s.id AND m.is_available = 1
        WHERE s.is_active = 1
        GROUP BY s.id
        ORDER BY s.id ASC
        """
    )
    return jsonify({"success": True, "shops": shops}), 200


@menu_bp.get("/menu")
def get_menu():
    shop_id = request.args.get("shop_id")
    shop_name = request.args.get("shop")
    category = request.args.get("category")
    search_q = request.args.get("q", "").strip().lower()

    sql = """
        SELECT m.id, m.shop_id, m.name, m.description, m.price, m.category,
               m.quantity, m.is_available, m.image_url, s.name as shop_name, s.slug as shop_slug
        FROM menu_items m
        INNER JOIN shops s ON s.id = m.shop_id
        WHERE s.is_active = 1
    """
    params = []

    if shop_id:
        sql += " AND m.shop_id = %s"
        params.append(shop_id)
    elif shop_name:
        sql += " AND LOWER(s.name) = %s"
        params.append(shop_name.lower())

    if category and category.lower() != "all":
        sql += " AND LOWER(m.category) = %s"
        params.append(category.lower())

    if search_q:
        sql += " AND (LOWER(m.name) LIKE %s OR LOWER(m.description) LIKE %s OR LOWER(s.name) LIKE %s)"
        pattern = f"%{search_q}%"
        params.extend([pattern, pattern, pattern])

    sql += " ORDER BY m.is_available DESC, m.name ASC"

    items = DB.query(sql, tuple(params))
    return jsonify({"success": True, "count": len(items), "items": items}), 200


@menu_bp.get("/menu/<int:item_id>")
def get_menu_item(item_id):
    item = DB.get_one(
        """
        SELECT m.*, s.name as shop_name
        FROM menu_items m
        INNER JOIN shops s ON s.id = m.shop_id
        WHERE m.id = %s
        """,
        (item_id,),
    )
    if not item:
        return jsonify({"success": False, "message": "Food item not found."}), 404
    return jsonify({"success": True, "item": item}), 200


@menu_bp.get("/categories")
def get_categories():
    rows = DB.query("SELECT DISTINCT category FROM menu_items WHERE is_available = 1 ORDER BY category ASC")
    categories = [r["category"] for r in rows if r.get("category")]
    return jsonify({"success": True, "categories": categories}), 200
