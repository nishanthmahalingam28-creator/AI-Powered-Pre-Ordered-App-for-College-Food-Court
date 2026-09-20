import re
import logging
from decimal import Decimal, InvalidOperation
from flask import Blueprint, jsonify, request, session
from db import DB
from routes.auth import role_required
from services.audit import AuditService

logger = logging.getLogger("food_court.vendor")
vendor_bp = Blueprint("vendor", __name__)

ALLOWED_OPERATIONAL_STATUSES = {"OPEN", "CLOSED", "TEMPORARILY_UNAVAILABLE"}


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
      If stall is deactivated (is_active = 0) or unassigned, returns None.
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


# ============================================================================
# SHOP PROFILE & OPERATIONAL STATUS
# ============================================================================

@vendor_bp.get("/shop")
@role_required(["vendor", "admin"])
def get_vendor_shop():
    """Returns vendor's assigned stall details, status, and operational mode."""
    shop_id = _get_active_shop_id()
    if not shop_id:
        return jsonify({
            "success": False,
            "message": "Forbidden: No active stall assigned to this vendor or stall is currently deactivated."
        }), 403

    shop = DB.get_one("SELECT * FROM shops WHERE id = %s", (shop_id,))
    if not shop:
        return jsonify({"success": False, "message": "Assigned stall not found."}), 404

    return jsonify({
        "success": True,
        "shop": {
            "id": shop["id"],
            "name": shop["name"],
            "slug": shop["slug"],
            "category": shop.get("category") or "Multi-Cuisine",
            "description": shop.get("description") or "",
            "is_active": int(shop.get("is_active", 1)),
            "operational_status": str(shop.get("operational_status") or "OPEN").upper(),
            "created_at": str(shop.get("created_at") or ""),
        }
    }), 200


@vendor_bp.put("/shop/operational-status")
@role_required(["vendor", "admin"])
def update_vendor_operational_status():
    """
    Allows vendor to toggle operational status of their assigned stall
    between OPEN, CLOSED, and TEMPORARILY_UNAVAILABLE.
    Strictly isolated to vendor's own stall.
    """
    shop_id = _get_active_shop_id()
    if not shop_id:
        return jsonify({
            "success": False,
            "message": "Forbidden: No active stall assigned or stall is deactivated."
        }), 403

    shop = DB.get_one("SELECT id, name, operational_status FROM shops WHERE id = %s", (shop_id,))
    if not shop:
        return jsonify({"success": False, "message": "Shop not found."}), 404

    data = request.get_json(silent=True) or {}
    new_status = str(data.get("operational_status") or data.get("status") or "").strip().upper()

    if new_status not in ALLOWED_OPERATIONAL_STATUSES:
        return jsonify({
            "success": False,
            "message": f"Invalid operational status. Must be one of {sorted(list(ALLOWED_OPERATIONAL_STATUSES))}."
        }), 400

    old_status = str(shop.get("operational_status") or "OPEN").upper()
    DB.execute("UPDATE shops SET operational_status = %s WHERE id = %s", (new_status, shop_id))

    actor_id = session.get("user_id")
    AuditService.log_action(
        actor_id=actor_id,
        action="SHOP_OPERATIONAL_STATUS_CHANGED",
        entity_type="shop",
        entity_id=shop_id,
        details={"shop_name": shop["name"], "old_status": old_status, "new_status": new_status, "role": session.get("role")}
    )

    return jsonify({
        "success": True,
        "message": f"Stall '{shop['name']}' status updated to {new_status}.",
        "shop_id": shop_id,
        "operational_status": new_status
    }), 200


# ============================================================================
# VENDOR ANALYTICS
# ============================================================================

@vendor_bp.get("/analytics")
@role_required(["vendor", "admin"])
def get_vendor_analytics():
    """Returns shop-scoped operational metrics plus range-filtered completed sales analytics."""
    shop_id = _get_active_shop_id()
    if not shop_id:
        return jsonify({
            "success": False,
            "message": "No active stall specified or stall is currently deactivated."
        }), 403

    shop = DB.get_one(
        "SELECT id, name, operational_status FROM shops WHERE id = %s",
        (shop_id,),
    )
    if not shop:
        return jsonify({"success": False, "message": "Shop not found."}), 404

    shop_name = shop["name"]
    operational_status = str(shop.get("operational_status") or "OPEN").upper()

    # Existing live operational/inventory telemetry.
    revenue_row = DB.get_one(
        """
        SELECT COALESCE(SUM(total_amount), 0) as total_revenue,
               COUNT(id) as total_orders,
               SUM(CASE WHEN order_status IN ('pending', 'preparing', 'ready') THEN 1 ELSE 0 END) as active_orders,
               SUM(CASE WHEN order_status = 'pending' THEN 1 ELSE 0 END) as pending_orders,
               SUM(CASE WHEN order_status = 'preparing' THEN 1 ELSE 0 END) as preparing_orders,
               SUM(CASE WHEN order_status = 'ready' THEN 1 ELSE 0 END) as ready_orders,
               SUM(CASE WHEN order_status = 'completed' THEN 1 ELSE 0 END) as completed_orders
        FROM orders
        WHERE shop_id = %s
        """,
        (shop_id,),
    ) or {}

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

    # Sales are measured by completed, paid orders. The reporting range is
    # selected in Asia/Kolkata and converted to UTC for the database queries.
    from datetime import datetime, timezone, timedelta
    from zoneinfo import ZoneInfo

    ist = ZoneInfo("Asia/Kolkata")
    now_ist = datetime.now(ist)
    period = str(request.args.get("period") or "daily").strip().lower()
    if period not in {"daily", "weekly", "monthly", "yearly", "custom"}:
        return jsonify({"success": False, "message": "Invalid sales period."}), 400

    def parse_date(value):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return None

    if period == "daily":
        start_date = now_ist.date()
        end_date = start_date
    elif period == "weekly":
        start_date = now_ist.date() - timedelta(days=now_ist.weekday())
        end_date = start_date + timedelta(days=6)
    elif period == "monthly":
        start_date = now_ist.date().replace(day=1)
        next_month = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
        end_date = next_month - timedelta(days=1)
    elif period == "yearly":
        start_date = now_ist.date().replace(month=1, day=1)
        end_date = now_ist.date().replace(month=12, day=31)
    else:
        start_date = parse_date(request.args.get("start_date"))
        end_date = parse_date(request.args.get("end_date"))
        if not start_date or not end_date:
            return jsonify({"success": False, "message": "Custom range requires start_date and end_date in YYYY-MM-DD format."}), 400
        if end_date < start_date:
            return jsonify({"success": False, "message": "End date cannot be before start date."}), 400
        if (end_date - start_date).days > 366:
            return jsonify({"success": False, "message": "Custom sales range cannot exceed 366 days."}), 400

    start_ist = datetime.combine(start_date, datetime.min.time(), tzinfo=ist)
    end_ist = datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=ist)
    start_utc = start_ist.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = end_ist.astimezone(timezone.utc).replace(tzinfo=None)
    range_label = f"{start_date.isoformat()} to {end_date.isoformat()}"

    sales_summary = DB.get_one(
        """
        SELECT COUNT(*) AS total_orders,
               COALESCE(SUM(total_amount), 0) AS total_revenue,
               COALESCE(AVG(total_amount), 0) AS average_order_value
        FROM orders
        WHERE shop_id = %s
          AND order_status = 'completed'
          AND payment_status = 'paid'
          AND completed_time >= %s
          AND completed_time < %s
        """,
        (shop_id, start_utc.strftime("%Y-%m-%d %H:%M:%S"), end_utc.strftime("%Y-%m-%d %H:%M:%S")),
    ) or {}

    food_total = DB.get_one(
        """
        SELECT COALESCE(SUM(oi.quantity), 0) AS total_food_sold
        FROM order_items oi
        INNER JOIN orders o ON o.id = oi.order_id
        WHERE o.shop_id = %s
          AND o.order_status = 'completed'
          AND o.payment_status = 'paid'
          AND o.completed_time >= %s
          AND o.completed_time < %s
        """,
        (shop_id, start_utc.strftime("%Y-%m-%d %H:%M:%S"), end_utc.strftime("%Y-%m-%d %H:%M:%S")),
    ) or {}

    meal_rows = DB.query(
        """
        SELECT
            COALESCE(oi.meal_period, mi.meal_period, 'unknown') AS meal_period,
            COALESCE(SUM(oi.quantity), 0) AS food_sold,
            COUNT(DISTINCT o.id) AS total_orders,
            COALESCE(SUM(oi.subtotal), 0) AS revenue
        FROM order_items oi
        INNER JOIN orders o ON o.id = oi.order_id
        LEFT JOIN menu_items mi ON mi.id = oi.menu_item_id
        WHERE o.shop_id = %s
          AND o.order_status = 'completed'
          AND o.payment_status = 'paid'
          AND o.completed_time >= %s
          AND o.completed_time < %s
        GROUP BY COALESCE(oi.meal_period, mi.meal_period, 'unknown')
        """,
        (shop_id, start_utc.strftime("%Y-%m-%d %H:%M:%S"), end_utc.strftime("%Y-%m-%d %H:%M:%S")),
    )

    meal_map = {str(row.get("meal_period") or "unknown").lower(): row for row in meal_rows}
    meal_periods = []
    for period in ("breakfast", "lunch", "dinner"):
        row = meal_map.get(period, {})
        meal_periods.append({
            "meal_period": period,
            "food_sold": int(row.get("food_sold") or 0),
            "total_orders": int(row.get("total_orders") or 0),
            "revenue": float(row.get("revenue") or 0.0),
        })

    unknown_row = meal_map.get("unknown")
    if unknown_row:
        meal_periods.append({
            "meal_period": "unknown",
            "food_sold": int(unknown_row.get("food_sold") or 0),
            "total_orders": int(unknown_row.get("total_orders") or 0),
            "revenue": float(unknown_row.get("revenue") or 0.0),
        })

    top_rows = DB.query(
        """
        SELECT oi.item_name,
               COALESCE(oi.meal_period, mi.meal_period, 'unknown') AS meal_period,
               COALESCE(SUM(oi.quantity), 0) AS units_sold,
               COALESCE(SUM(oi.subtotal), 0) AS revenue
        FROM order_items oi
        INNER JOIN orders o ON o.id = oi.order_id
        LEFT JOIN menu_items mi ON mi.id = oi.menu_item_id
        WHERE o.shop_id = %s
          AND o.order_status = 'completed'
          AND o.payment_status = 'paid'
          AND o.completed_time >= %s
          AND o.completed_time < %s
        GROUP BY oi.item_name, COALESCE(oi.meal_period, mi.meal_period, 'unknown')
        ORDER BY units_sold DESC, revenue DESC, oi.item_name ASC
        LIMIT 10
        """,
        (shop_id, start_utc.strftime("%Y-%m-%d %H:%M:%S"), end_utc.strftime("%Y-%m-%d %H:%M:%S")),
    )

    hourly_rows_raw = DB.query(
        """
        SELECT o.id, o.completed_time, oi.quantity, oi.subtotal
        FROM orders o
        INNER JOIN order_items oi ON oi.order_id = o.id
        WHERE o.shop_id = %s
          AND o.order_status = 'completed'
          AND o.payment_status = 'paid'
          AND o.completed_time >= %s
          AND o.completed_time < %s
        ORDER BY o.completed_time ASC
        """,
        (shop_id, start_utc.strftime("%Y-%m-%d %H:%M:%S"), end_utc.strftime("%Y-%m-%d %H:%M:%S")),
    )

    hourly_map = {}
    for row in hourly_rows_raw:
        completed = row.get("completed_time")
        if not completed:
            continue
        if hasattr(completed, "hour"):
            if getattr(completed, "tzinfo", None) is None:
                completed = completed.replace(tzinfo=timezone.utc)
            hour = completed.astimezone(ist).hour
        else:
            raw_completed = str(completed).strip()
            try:
                parsed_completed = datetime.strptime(raw_completed[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                hour = parsed_completed.astimezone(ist).hour
            except ValueError:
                hour = int(raw_completed[11:13])
        bucket = hourly_map.setdefault(hour, {"order_ids": set(), "food_sold": 0, "revenue": 0.0})
        bucket["order_ids"].add(row["id"])
        bucket["food_sold"] += int(row.get("quantity") or 0)
        bucket["revenue"] += float(row.get("subtotal") or 0.0)

    hourly_rows = [
        {
            "hour": hour,
            "total_orders": len(bucket["order_ids"]),
            "food_sold": bucket["food_sold"],
            "revenue": bucket["revenue"],
        }
        for hour, bucket in sorted(hourly_map.items())
    ]

    cancelled_row = DB.get_one(
        """
        SELECT COUNT(*) AS cancelled_orders
        FROM orders
        WHERE shop_id = %s
          AND order_status = 'cancelled'
          AND cancellation_time >= %s
          AND cancellation_time < %s
        """,
        (shop_id, start_utc.strftime("%Y-%m-%d %H:%M:%S"), end_utc.strftime("%Y-%m-%d %H:%M:%S")),
    ) or {}

    total_revenue = float(sales_summary.get("total_revenue") or 0.0)
    total_orders = int(sales_summary.get("total_orders") or 0)

    return jsonify({
        "success": True,
        "shop": {
            "id": shop_id,
            "name": shop_name,
            "operational_status": operational_status,
        },
        "analytics": {
            "today_revenue": float(revenue_row.get("total_revenue") or 0.0),
            "total_orders": int(revenue_row.get("total_orders") or 0),
            "active_orders": int(revenue_row.get("active_orders") or 0),
            "pending_orders": int(revenue_row.get("pending_orders") or 0),
            "preparing_orders": int(revenue_row.get("preparing_orders") or 0),
            "ready_orders": int(revenue_row.get("ready_orders") or 0),
            "completed_orders": int(revenue_row.get("completed_orders") or 0),
            "total_dishes": int(menu_stats.get("total_dishes") or 0),
            "available_dishes": int(menu_stats.get("available_dishes") or 0),
            "out_of_stock_dishes": int(menu_stats.get("out_of_stock_dishes") or 0),
            "total_stock": int(menu_stats.get("total_stock") or 0),
            "today_sales": {
                "date": end_date.isoformat() if period == "daily" else range_label,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "period": period,
                "range_label": range_label,
                "timezone": "Asia/Kolkata",
                "total_food_sold": int(food_total.get("total_food_sold") or 0),
                "total_orders": total_orders,
                "total_revenue": total_revenue,
                "average_order_value": float(sales_summary.get("average_order_value") or 0.0),
                "cancelled_orders": int(cancelled_row.get("cancelled_orders") or 0),
                "meal_periods": meal_periods,
                "top_items": [
                    {
                        "item_name": str(r.get("item_name") or "Unknown"),
                        "meal_period": str(r.get("meal_period") or "unknown"),
                        "units_sold": int(r.get("units_sold") or 0),
                        "revenue": float(r.get("revenue") or 0.0),
                    }
                    for r in top_rows
                ],
                "hourly_sales": [
                    {
                        "hour": int(r.get("hour") or 0),
                        "total_orders": int(r.get("total_orders") or 0),
                        "food_sold": int(r.get("food_sold") or 0),
                        "revenue": float(r.get("revenue") or 0.0),
                    }
                    for r in hourly_rows
                ],
            },
        }
    }), 200


# ============================================================================
# KITCHEN ORDER QUEUE
# ============================================================================

@vendor_bp.get("/orders")
@role_required(["vendor", "admin"])
def get_vendor_kitchen_orders():
    """
    Returns live kitchen queue for vendor's authoritative stall.
    Vendors can view and fulfill active in-flight orders even when stall is closed.
    """
    shop_id = _get_active_shop_id()
    if not shop_id:
        return jsonify({
            "success": False,
            "message": "Forbidden: No active stall assigned or stall is deactivated."
        }), 403

    status_filter = request.args.get("status")
    include_all = request.args.get("include_all", "0") in ("1", "true")

    sql = """
        SELECT o.id, o.order_reference, o.customer_id, o.shop_id, o.total_amount,
               o.order_status, o.payment_status, o.payment_method, o.pickup_otp,
               o.created_at, o.payment_time, o.preparing_time, o.ready_time,
               o.completed_time, o.cancellation_time,
               cp.full_name as customer_name, cp.customer_type, cp.identifier, cp.mobile
        FROM orders o
        LEFT JOIN customer_profiles cp ON cp.user_id = o.customer_id
        WHERE o.shop_id = %s
    """
    params = [shop_id]

    if status_filter:
        sql += " AND o.order_status = %s"
        params.append(status_filter.lower())

    if not include_all and session.get("role") == "vendor":
        sql += " AND (o.payment_status = 'paid' OR LOWER(o.payment_method) LIKE '%counter%' OR LOWER(o.payment_method) LIKE '%cash%')"

    sql += """
        ORDER BY CASE o.order_status
            WHEN 'pending' THEN 1
            WHEN 'preparing' THEN 2
            WHEN 'ready' THEN 3
            ELSE 4 END,
            o.id DESC
        LIMIT 100
    """

    orders = DB.query(sql, tuple(params))
    for order in orders:
        order["total_amount"] = float(order.get("total_amount") or 0.0)
        items = DB.query(
            "SELECT item_name, quantity, unit_price, subtotal FROM order_items WHERE order_id = %s",
            (order["id"],),
        )
        order["items"] = items
        order["items_summary"] = ", ".join(f"{i['quantity']}x {i['item_name']}" for i in items)

    return jsonify({"success": True, "orders": orders, "shop_id": shop_id}), 200


# ============================================================================
# MENU & STOCK MANAGEMENT
# ============================================================================

@vendor_bp.post("/menu/item")
@role_required(["vendor", "admin"])
def add_menu_item():
    """Adds a new dish to the vendor's assigned active stall and logs audit action."""
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
    meal_period = str(data.get("meal_period", "lunch")).strip().lower()
    if meal_period not in {"breakfast", "lunch", "dinner"}:
        return jsonify({"success": False, "message": "Meal period must be Breakfast, Lunch, or Dinner."}), 400
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
        INSERT INTO menu_items (shop_id, name, description, price, category, meal_period, quantity, is_available)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (shop_id, name, description, price, category, meal_period, quantity, available),
    )

    actor_id = session.get("user_id")
    AuditService.log_action(
        actor_id=actor_id,
        action="MENU_ITEM_CREATED",
        entity_type="menu_item",
        entity_id=item_id,
        details={"name": name, "price": price, "quantity": quantity, "shop_id": shop_id}
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
            "meal_period": meal_period,
            "quantity": quantity,
            "is_available": available,
        }
    }), 201


@vendor_bp.put("/menu/item/<int:item_id>")
@role_required(["vendor", "admin"])
def update_menu_item(item_id):
    """
    Updates price, stock, category, or availability of a dish.
    Enforces strict stall ownership (IDOR prevention) and logs audit action.
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

    if "meal_period" in data:
        meal_period = str(data.get("meal_period") or "").strip().lower()
        if meal_period not in {"breakfast", "lunch", "dinner"}:
            return jsonify({"success": False, "message": "Meal period must be Breakfast, Lunch, or Dinner."}), 400
    else:
        meal_period = item.get("meal_period") or "lunch"

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
        SET name = %s, description = %s, price = %s, quantity = %s, category = %s, meal_period = %s, is_available = %s
        WHERE id = %s
        """,
        (name, description, price, quantity, category, meal_period, is_available, item_id),
    )

    actor_id = session.get("user_id")
    AuditService.log_action(
        actor_id=actor_id,
        action="MENU_ITEM_UPDATED",
        entity_type="menu_item",
        entity_id=item_id,
        details={"name": name, "price": price, "quantity": quantity, "is_available": is_available}
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
            "meal_period": meal_period,
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
    Logs audit action.
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

    actor_id = session.get("user_id")

    # Check if item exists in historical orders
    historical_order = DB.get_one("SELECT id FROM order_items WHERE menu_item_id = %s LIMIT 1", (item_id,))
    if historical_order:
        # Safe soft-deactivation to preserve order history records
        DB.execute("UPDATE menu_items SET is_available = 0, quantity = 0 WHERE id = %s", (item_id,))
        AuditService.log_action(
            actor_id=actor_id,
            action="MENU_ITEM_ARCHIVED",
            entity_type="menu_item",
            entity_id=item_id,
            details={"name": item["name"], "soft_delete": True}
        )
        return jsonify({
            "success": True,
            "message": f"'{item['name']}' archived and marked unavailable to preserve order history."
        }), 200
    else:
        # No historical orders exist; safe to physically delete
        DB.execute("DELETE FROM menu_items WHERE id = %s", (item_id,))
        AuditService.log_action(
            actor_id=actor_id,
            action="MENU_ITEM_DELETED",
            entity_type="menu_item",
            entity_id=item_id,
            details={"name": item["name"], "physical_delete": True}
        )
        return jsonify({
            "success": True,
            "message": f"'{item['name']}' removed from menu."
        }), 200


# ============================================================================
# DAILY MORNING MENU SURVEY
# ============================================================================

DAILY_MEAL_PERIODS = ("breakfast", "lunch", "dinner")


def _today_str():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")


@vendor_bp.get("/daily-survey/today")
@role_required(["vendor"])
def get_vendor_daily_survey():
    """Returns today's vendor survey plus the shop's menu grouped by meal period."""
    shop_id = _get_active_shop_id()
    vendor_id = session.get("user_id")
    if not shop_id or not vendor_id:
        return jsonify({"success": False, "message": "No active stall is assigned to this vendor."}), 403

    today = _today_str()
    survey = DB.get_one(
        """
        SELECT id, vendor_user_id, shop_id, survey_date, is_serving_today,
               submitted_at, updated_at
        FROM vendor_daily_surveys
        WHERE vendor_user_id = %s AND shop_id = %s AND survey_date = %s
        LIMIT 1
        """,
        (vendor_id, shop_id, today),
    )

    menu_items = DB.query(
        """
        SELECT id, name, description, price, category, meal_period, quantity, is_available
        FROM menu_items
        WHERE shop_id = %s
        ORDER BY FIELD(meal_period, 'breakfast', 'lunch', 'dinner'), category ASC, name ASC
        """,
        (shop_id,),
    )

    daily_rows = []
    if survey:
        daily_rows = DB.query(
            """
            SELECT id, menu_item_id, meal_period, item_name, price, quantity, is_available
            FROM vendor_daily_menu_items
            WHERE survey_id = %s
            ORDER BY FIELD(meal_period, 'breakfast', 'lunch', 'dinner'), item_name ASC
            """,
            (survey["id"],),
        )

    selected = {}
    for row in daily_rows:
        selected.setdefault(row["meal_period"], []).append({
            "id": row["id"],
            "menu_item_id": row["menu_item_id"],
            "item_name": row["item_name"],
            "price": float(row["price"]),
            "quantity": int(row["quantity"]),
            "is_available": bool(row["is_available"]),
        })

    catalog = []
    for item in menu_items:
        catalog.append({
            "id": item["id"],
            "name": item["name"],
            "description": item.get("description") or "",
            "price": float(item["price"]),
            "category": item.get("category") or "Food",
            "meal_period": str(item.get("meal_period") or "lunch").lower(),
            "stock_quantity": int(item.get("quantity") or 0),
            "is_available": bool(item.get("is_available")),
        })

    return jsonify({
        "success": True,
        "date": today,
        "shop": {"id": shop_id},
        "survey": {
            "id": survey["id"] if survey else None,
            "is_serving_today": bool(survey["is_serving_today"]) if survey else True,
            "submitted": bool(survey),
            "submitted_at": str(survey["submitted_at"]) if survey else None,
            "updated_at": str(survey["updated_at"]) if survey else None,
        },
        "meal_periods": DAILY_MEAL_PERIODS,
        "menu_catalog": catalog,
        "selected": selected,
    }), 200



@vendor_bp.get("/daily-survey/user-results")
@role_required(["vendor"])
def get_vendor_user_survey_results():
    """Returns privacy-conscious aggregate customer morning-survey results for today."""
    shop_id = _get_active_shop_id()
    if not shop_id:
        return jsonify({"success": False, "message": "No active stall is assigned to this vendor."}), 403

    today = _today_str()

    summary = DB.get_one(
        """
        SELECT
            COUNT(*) AS total_responses,
            SUM(CASE WHEN plans_to_eat = 1 THEN 1 ELSE 0 END) AS planning_to_eat,
            SUM(CASE WHEN plans_to_eat = 0 THEN 1 ELSE 0 END) AS not_planning_to_eat
        FROM morning_surveys
        WHERE survey_date = %s
        """,
        (today,),
    ) or {}

    meal_rows = DB.query(
        """
        SELECT meal_type, COUNT(*) AS response_count
        FROM morning_surveys
        WHERE survey_date = %s AND plans_to_eat = 1
        GROUP BY meal_type
        ORDER BY response_count DESC
        """,
        (today,),
    )

    preference_rows = DB.query(
        """
        SELECT meal_preference, COUNT(*) AS response_count
        FROM morning_surveys
        WHERE survey_date = %s AND plans_to_eat = 1
        GROUP BY meal_preference
        ORDER BY response_count DESC, meal_preference ASC
        LIMIT 20
        """,
        (today,),
    )

    dietary_rows = DB.query(
        """
        SELECT dietary_preference, COUNT(*) AS response_count
        FROM morning_surveys
        WHERE survey_date = %s AND plans_to_eat = 1
        GROUP BY dietary_preference
        ORDER BY response_count DESC
        """,
        (today,),
    )

    hunger_rows = DB.query(
        """
        SELECT hunger_level, COUNT(*) AS response_count
        FROM morning_surveys
        WHERE survey_date = %s AND plans_to_eat = 1
        GROUP BY hunger_level
        ORDER BY response_count DESC
        """,
        (today,),
    )

    return jsonify({
        "success": True,
        "date": today,
        "shop": {"id": shop_id},
        "summary": {
            "total_responses": int(summary.get("total_responses") or 0),
            "planning_to_eat": int(summary.get("planning_to_eat") or 0),
            "not_planning_to_eat": int(summary.get("not_planning_to_eat") or 0),
        },
        "meal_periods": [
            {"meal_type": str(r.get("meal_type") or "unknown"), "response_count": int(r.get("response_count") or 0)}
            for r in meal_rows
        ],
        "food_preferences": [
            {"meal_preference": str(r.get("meal_preference") or "Not specified"), "response_count": int(r.get("response_count") or 0)}
            for r in preference_rows
        ],
        "dietary_preferences": [
            {"dietary_preference": str(r.get("dietary_preference") or "any"), "response_count": int(r.get("response_count") or 0)}
            for r in dietary_rows
        ],
        "hunger_levels": [
            {"hunger_level": str(r.get("hunger_level") or "unknown"), "response_count": int(r.get("response_count") or 0)}
            for r in hunger_rows
        ],
    }), 200

@vendor_bp.post("/daily-survey")
@role_required(["vendor"])
def save_vendor_daily_survey():
    """
    Saves exactly one daily menu survey per vendor/shop/date.
    Re-submitting updates the same survey and replaces today's meal selections.
    """
    shop_id = _get_active_shop_id()
    vendor_id = session.get("user_id")
    if not shop_id or not vendor_id:
        return jsonify({"success": False, "message": "No active stall is assigned to this vendor."}), 403

    data = request.get_json(silent=True) or {}
    today = _today_str()
    is_serving_today = bool(data.get("is_serving_today", True))
    meals = data.get("meals") or {}

    if not isinstance(meals, dict):
        return jsonify({"success": False, "message": "Invalid meal menu data."}), 400

    normalized = {}
    for period in DAILY_MEAL_PERIODS:
        rows = meals.get(period, [])
        if not isinstance(rows, list):
            return jsonify({"success": False, "message": f"Invalid {period} menu list."}), 400
        normalized[period] = rows

    try:
        with DB.transaction() as tx:
            survey = tx.get_one(
                """
                SELECT id
                FROM vendor_daily_surveys
                WHERE vendor_user_id = %s AND shop_id = %s AND survey_date = %s
                LIMIT 1
                """,
                (vendor_id, shop_id, today),
            )

            if survey:
                survey_id = survey["id"]
                tx.execute(
                    """
                    UPDATE vendor_daily_surveys
                    SET is_serving_today = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (1 if is_serving_today else 0, survey_id),
                )
                tx.execute("DELETE FROM vendor_daily_menu_items WHERE survey_id = %s", (survey_id,))
            else:
                survey_id = tx.execute(
                    """
                    INSERT INTO vendor_daily_surveys
                        (vendor_user_id, shop_id, survey_date, is_serving_today)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (vendor_id, shop_id, today, 1 if is_serving_today else 0),
                )

            if is_serving_today:
                for period in DAILY_MEAL_PERIODS:
                    for row in normalized[period]:
                        try:
                            item_id = int(row.get("menu_item_id"))
                            quantity = int(row.get("quantity", 0))
                        except (TypeError, ValueError):
                            raise ValueError(f"Invalid item or quantity in {period} menu.")

                        if quantity < 0 or quantity > 100000:
                            raise ValueError("Menu quantity must be between 0 and 100000.")

                        item = tx.get_one(
                            """
                            SELECT id, name, price, shop_id, is_available
                            FROM menu_items
                            WHERE id = %s AND shop_id = %s
                            LIMIT 1
                            """,
                            (item_id, shop_id),
                        )
                        if not item:
                            raise PermissionError("One or more selected dishes do not belong to your assigned stall.")

                        tx.execute(
                            """
                            INSERT INTO vendor_daily_menu_items
                                (survey_id, shop_id, menu_item_id, meal_period, item_name, price, quantity, is_available)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                survey_id,
                                shop_id,
                                item_id,
                                period,
                                item["name"],
                                item["price"],
                                quantity,
                                1 if quantity > 0 and item.get("is_available") else 0,
                            ),
                        )

            AuditService.log_action(
                actor_id=vendor_id,
                action="VENDOR_DAILY_MENU_SURVEY_SAVED",
                entity_type="vendor_daily_survey",
                entity_id=survey_id,
                details={
                    "shop_id": shop_id,
                    "survey_date": today,
                    "is_serving_today": is_serving_today,
                    "breakfast_items": len(normalized["breakfast"]),
                    "lunch_items": len(normalized["lunch"]),
                    "dinner_items": len(normalized["dinner"]),
                },
                tx=tx,
            )

        return jsonify({
            "success": True,
            "message": "Today's menu survey saved successfully.",
            "survey_id": survey_id,
            "date": today,
            "is_serving_today": is_serving_today,
        }), 200
    except PermissionError as e:
        logger.warning("Vendor daily survey ownership validation failed: %s", e)
        return jsonify({"success": False, "message": str(e)}), 403
    except ValueError as e:
        logger.warning("Vendor daily survey validation failed: %s", e)
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        logger.exception("Failed to save vendor daily survey: %s", e)
        return jsonify({"success": False, "message": "Unable to save today's menu survey."}), 500


# ============================================================================
# WORKER MANAGEMENT
# ============================================================================

def _worker_shop_or_forbidden():
    shop_id = _get_active_shop_id()
    if not shop_id:
        return None, (jsonify({"success": False, "message": "No active stall assigned."}), 403)
    return shop_id, None


def _validate_worker_name(value):
    name = str(value or "").strip()
    if not name or len(name) > 150 or not re.match(r"^[\w\s.'\-&]+$", name, re.UNICODE):
        return None
    return name


@vendor_bp.get("/workers")
@role_required(["vendor", "admin"])
def list_workers():
    shop_id, error = _worker_shop_or_forbidden()
    if error:
        return error
    workers = DB.query(
        """
        SELECT id, employee_code, full_name, phone, role_title,
               salary_type, salary_amount, joining_date, status
        FROM workers
        WHERE shop_id = %s
        ORDER BY status ASC, full_name ASC
        """,
        (shop_id,),
    )
    from datetime import date as _date
    today = _date.today()
    month_start = today.replace(day=1).isoformat()
    if today.month == 12:
        month_end = _date(today.year + 1, 1, 1).isoformat()
    else:
        month_end = _date(today.year, today.month + 1, 1).isoformat()
    attendance_rows = DB.query(
        """
        SELECT worker_id, status
        FROM worker_attendance
        WHERE attendance_date >= %s AND attendance_date < %s
        """,
        (month_start, month_end),
    )
    attendance_map = {}
    for row in attendance_rows:
        attendance_map[row["worker_id"]] = attendance_map.get(row["worker_id"], 0) + (
            1 if row["status"] == "present" else 0.5 if row["status"] == "half_day" else 0
        )
    for w in workers:
        w["salary_amount"] = float(w.get("salary_amount") or 0)
        w["attendance_days"] = float(attendance_map.get(w["id"], 0))
    return jsonify({"success": True, "workers": workers, "shop_id": shop_id}), 200


@vendor_bp.post("/workers")
@role_required(["vendor", "admin"])
def create_worker():
    shop_id, error = _worker_shop_or_forbidden()
    if error:
        return error
    data = request.get_json(silent=True) or {}
    name = _validate_worker_name(data.get("full_name"))
    if not name:
        return jsonify({"success": False, "message": "Enter a valid worker name."}), 400

    code = str(data.get("employee_code") or "").strip().upper()
    if not code or len(code) > 50 or not re.match(r"^[A-Z0-9_-]+$", code):
        return jsonify({"success": False, "message": "Employee ID can contain only letters, numbers, hyphens and underscores."}), 400

    role_title = str(data.get("role_title") or "Kitchen Staff").strip()
    phone = str(data.get("phone") or "").strip()
    salary_type = str(data.get("salary_type") or "monthly").lower()
    if salary_type not in {"monthly", "daily"}:
        return jsonify({"success": False, "message": "Salary type must be monthly or daily."}), 400

    try:
        salary = Decimal(str(data.get("salary_amount") or "0"))
        if salary < 0 or salary > Decimal("1000000"):
            raise InvalidOperation
        salary = salary.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return jsonify({"success": False, "message": "Enter a valid salary amount."}), 400

    joining_date = str(data.get("joining_date") or "").strip() or None
    if joining_date:
        try:
            from datetime import datetime as _dt
            _dt.strptime(joining_date, "%Y-%m-%d")
        except ValueError:
            return jsonify({"success": False, "message": "Joining date must be YYYY-MM-DD."}), 400

    existing = DB.get_one("SELECT id FROM workers WHERE shop_id = %s AND employee_code = %s", (shop_id, code))
    if existing:
        return jsonify({"success": False, "message": "Employee ID already exists in this stall."}), 409

    worker_id = DB.execute(
        """
        INSERT INTO workers
            (shop_id, employee_code, full_name, phone, role_title, salary_type, salary_amount, joining_date, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'active')
        """,
        (shop_id, code, name, phone or None, role_title, salary_type, salary, joining_date),
    )
    AuditService.log_action(
        actor_id=session.get("user_id"), action="WORKER_CREATED",
        entity_type="worker", entity_id=worker_id,
        details={"shop_id": shop_id, "employee_code": code, "name": name}
    )
    return jsonify({"success": True, "message": "Worker added successfully.", "worker_id": worker_id}), 201


@vendor_bp.put("/workers/<int:worker_id>")
@role_required(["vendor", "admin"])
def update_worker(worker_id):
    shop_id, error = _worker_shop_or_forbidden()
    if error:
        return error
    worker = DB.get_one("SELECT * FROM workers WHERE id = %s AND shop_id = %s", (worker_id, shop_id))
    if not worker:
        return jsonify({"success": False, "message": "Worker not found."}), 404
    data = request.get_json(silent=True) or {}

    name = _validate_worker_name(data.get("full_name", worker["full_name"]))
    if not name:
        return jsonify({"success": False, "message": "Enter a valid worker name."}), 400
    role_title = str(data.get("role_title", worker["role_title"]) or "Kitchen Staff").strip()
    phone = str(data.get("phone", worker["phone"] or "") or "").strip()
    salary_type = str(data.get("salary_type", worker["salary_type"]) or "monthly").lower()
    if salary_type not in {"monthly", "daily"}:
        return jsonify({"success": False, "message": "Salary type must be monthly or daily."}), 400
    try:
        salary = Decimal(str(data.get("salary_amount", worker["salary_amount"]) or "0")).quantize(Decimal("0.01"))
        if salary < 0 or salary > Decimal("1000000"):
            raise InvalidOperation
    except (InvalidOperation, ValueError, TypeError):
        return jsonify({"success": False, "message": "Enter a valid salary amount."}), 400

    DB.execute(
        """
        UPDATE workers
        SET full_name=%s, phone=%s, role_title=%s, salary_type=%s, salary_amount=%s
        WHERE id=%s AND shop_id=%s
        """,
        (name, phone or None, role_title, salary_type, salary, worker_id, shop_id),
    )
    AuditService.log_action(
        actor_id=session.get("user_id"), action="WORKER_UPDATED",
        entity_type="worker", entity_id=worker_id, details={"shop_id": shop_id}
    )
    return jsonify({"success": True, "message": "Worker updated successfully."}), 200


@vendor_bp.delete("/workers/<int:worker_id>")
@role_required(["vendor", "admin"])
def delete_worker(worker_id):
    shop_id, error = _worker_shop_or_forbidden()
    if error:
        return error
    worker = DB.get_one("SELECT id, full_name FROM workers WHERE id=%s AND shop_id=%s", (worker_id, shop_id))
    if not worker:
        return jsonify({"success": False, "message": "Worker not found."}), 404
    DB.execute("DELETE FROM workers WHERE id=%s AND shop_id=%s", (worker_id, shop_id))
    AuditService.log_action(
        actor_id=session.get("user_id"), action="WORKER_DELETED",
        entity_type="worker", entity_id=worker_id, details={"shop_id": shop_id, "name": worker["full_name"]}
    )
    return jsonify({"success": True, "message": "Worker deleted successfully."}), 200


@vendor_bp.get("/workers/attendance")
@role_required(["vendor", "admin"])
def get_worker_attendance():
    shop_id, error = _worker_shop_or_forbidden()
    if error:
        return error
    date_value = request.args.get("date") or __import__("datetime").date.today().isoformat()
    rows = DB.query(
        """
        SELECT w.id AS worker_id, w.employee_code, w.full_name, w.role_title,
               COALESCE(a.status, 'absent') AS attendance_status,
               a.check_in, a.check_out, a.notes
        FROM workers w
        LEFT JOIN worker_attendance a
          ON a.worker_id = w.id AND a.attendance_date = %s
        WHERE w.shop_id=%s AND w.status='active'
        ORDER BY w.full_name
        """,
        (date_value, shop_id),
    )
    return jsonify({"success": True, "date": date_value, "attendance": rows}), 200


@vendor_bp.post("/workers/attendance")
@role_required(["vendor", "admin"])
def save_worker_attendance():
    shop_id, error = _worker_shop_or_forbidden()
    if error:
        return error
    data = request.get_json(silent=True) or {}
    try:
        worker_id = int(data.get("worker_id"))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Worker is required."}), 400
    worker = DB.get_one("SELECT id FROM workers WHERE id=%s AND shop_id=%s", (worker_id, shop_id))
    if not worker:
        return jsonify({"success": False, "message": "Worker not found."}), 404

    status = str(data.get("status") or "present").lower()
    if status not in {"present", "absent", "half_day", "leave"}:
        return jsonify({"success": False, "message": "Invalid attendance status."}), 400
    date_value = str(data.get("attendance_date") or __import__("datetime").date.today().isoformat())
    check_in = str(data.get("check_in") or "").strip() or None
    check_out = str(data.get("check_out") or "").strip() or None
    notes = str(data.get("notes") or "").strip()[:255] or None

    existing = DB.get_one("SELECT id FROM worker_attendance WHERE worker_id=%s AND attendance_date=%s", (worker_id, date_value))
    if existing:
        DB.execute(
            "UPDATE worker_attendance SET status=%s, check_in=%s, check_out=%s, notes=%s WHERE id=%s",
            (status, check_in, check_out, notes, existing["id"]),
        )
    else:
        DB.execute(
            "INSERT INTO worker_attendance (worker_id, attendance_date, status, check_in, check_out, notes) VALUES (%s,%s,%s,%s,%s,%s)",
            (worker_id, date_value, status, check_in, check_out, notes),
        )
    return jsonify({"success": True, "message": "Attendance saved."}), 200


@vendor_bp.get("/workers/salary")
@role_required(["vendor", "admin"])
def get_worker_salary():
    shop_id, error = _worker_shop_or_forbidden()
    if error:
        return error
    month = str(request.args.get("month") or __import__("datetime").date.today().replace(day=1).isoformat())
    rows = DB.query(
        """
        SELECT w.id AS worker_id, w.employee_code, w.full_name, w.role_title,
               w.salary_type, w.salary_amount,
               COALESCE(sp.status,'pending') AS salary_status,
               COALESCE(sp.paid_amount,0) AS paid_amount,
               sp.paid_on
        FROM workers w
        LEFT JOIN worker_salary_payments sp
          ON sp.worker_id=w.id AND sp.salary_month=%s
        WHERE w.shop_id=%s
        ORDER BY w.full_name
        """,
        (month, shop_id),
    )
    from datetime import date as _date
    from datetime import datetime as _dt
    parsed_month = _dt.strptime(month, "%Y-%m-%d").date()
    if parsed_month.month == 12:
        month_end = _date(parsed_month.year + 1, 1, 1).isoformat()
    else:
        month_end = _date(parsed_month.year, parsed_month.month + 1, 1).isoformat()
    attendance_rows = DB.query(
        """
        SELECT worker_id, status
        FROM worker_attendance
        WHERE attendance_date >= %s AND attendance_date < %s
        """,
        (month, month_end),
    )
    attendance_map = {}
    for row in attendance_rows:
        attendance_map[row["worker_id"]] = attendance_map.get(row["worker_id"], 0) + (
            1 if row["status"] == "present" else 0.5 if row["status"] == "half_day" else 0
        )
    for row in rows:
        row["salary_amount"] = float(row.get("salary_amount") or 0)
        row["attendance_days"] = float(attendance_map.get(row["worker_id"], 0))
        row["paid_amount"] = float(row.get("paid_amount") or 0)
    return jsonify({"success": True, "month": month, "salary": rows}), 200


@vendor_bp.post("/workers/<int:worker_id>/salary")
@role_required(["vendor", "admin"])
def save_worker_salary(worker_id):
    shop_id, error = _worker_shop_or_forbidden()
    if error:
        return error
    worker = DB.get_one("SELECT id, salary_type, salary_amount FROM workers WHERE id=%s AND shop_id=%s", (worker_id, shop_id))
    if not worker:
        return jsonify({"success": False, "message": "Worker not found."}), 404
    data = request.get_json(silent=True) or {}
    month = str(data.get("salary_month") or __import__("datetime").date.today().replace(day=1).isoformat())
    try:
        paid_amount = Decimal(str(data.get("paid_amount") if data.get("paid_amount") is not None else worker["salary_amount"])).quantize(Decimal("0.01"))
        if paid_amount < 0 or paid_amount > Decimal("1000000"):
            raise InvalidOperation
    except (InvalidOperation, ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid paid amount."}), 400
    status = str(data.get("status") or "paid").lower()
    if status not in {"pending", "paid"}:
        return jsonify({"success": False, "message": "Salary status must be pending or paid."}), 400
    paid_on = str(data.get("paid_on") or "") or None

    existing = DB.get_one("SELECT id FROM worker_salary_payments WHERE worker_id=%s AND salary_month=%s", (worker_id, month))
    if existing:
        DB.execute(
            "UPDATE worker_salary_payments SET base_salary=%s, paid_amount=%s, status=%s, paid_on=%s, notes=%s WHERE id=%s",
            (worker["salary_amount"], paid_amount, status, paid_on, str(data.get("notes") or "")[:255] or None, existing["id"]),
        )
    else:
        DB.execute(
            """
            INSERT INTO worker_salary_payments
                (worker_id, salary_month, base_salary, attendance_days, paid_amount, status, paid_on, notes)
            SELECT %s, %s, salary_amount,
                   COALESCE((SELECT SUM(CASE WHEN a.status='present' THEN 1 WHEN a.status='half_day' THEN 0.5 ELSE 0 END)
                             FROM worker_attendance a
                             WHERE a.worker_id=%s AND a.attendance_date >= %s AND a.attendance_date < DATE_ADD(%s, INTERVAL 1 MONTH)),0),
                   %s, %s, %s, %s
            FROM workers WHERE id=%s
            """,
            (worker_id, month, worker_id, month, month, paid_amount, status, paid_on, str(data.get("notes") or "")[:255] or None, worker_id),
        )
    return jsonify({"success": True, "message": "Salary record saved."}), 200
