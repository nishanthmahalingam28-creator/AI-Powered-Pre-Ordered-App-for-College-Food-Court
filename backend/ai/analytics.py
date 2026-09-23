"""
Sales Analytics and Food Court Intelligence Service.

Computes sales performance, category velocity, peak ordering hours,
and demand trends strictly from valid historical order data.
"""

import logging
from db import DB

logger = logging.getLogger("food_court.ai.analytics")


class FoodCourtAnalytics:
    """Provides stall-level and platform-wide sales analytics and demand insights."""

    @classmethod
    def get_shop_analytics(cls, shop_id: int):
        """
        Calculates operational and demand intelligence for a single stall.
        All read-only analytics queries share one pooled DB connection to reduce
        database round-trips and improve dashboard response time.
        """
        try:
            results = DB.query_many([
                (
                    "SELECT id, name, slug, operational_status, is_active "
                    "FROM shops WHERE id = %s",
                    (shop_id,),
                ),
                (
                    """
                    SELECT COUNT(id) as total_orders,
                           SUM(CASE WHEN order_status = 'completed' THEN 1 ELSE 0 END) as completed_orders,
                           SUM(CASE WHEN order_status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_orders,
                           SUM(CASE WHEN order_status IN ('pending', 'preparing', 'ready') THEN 1 ELSE 0 END) as active_orders
                    FROM orders
                    WHERE shop_id = %s
                    """,
                    (shop_id,),
                ),
                (
                    """
                    SELECT COALESCE(SUM(o.total_amount), 0) as total_revenue,
                           COALESCE(SUM(oi.quantity), 0) as total_units_sold
                    FROM orders o
                    LEFT JOIN order_items oi ON oi.order_id = o.id
                    WHERE o.shop_id = %s
                      AND (o.payment_status = 'paid' OR o.order_status = 'completed')
                      AND o.order_status != 'cancelled'
                      AND o.payment_status != 'failed'
                    """,
                    (shop_id,),
                ),
                (
                    """
                    SELECT oi.menu_item_id, m.name, m.category,
                           SUM(oi.quantity) as units_sold,
                           SUM(oi.subtotal) as item_revenue
                    FROM order_items oi
                    INNER JOIN orders o ON o.id = oi.order_id
                    INNER JOIN menu_items m ON m.id = oi.menu_item_id
                    WHERE o.shop_id = %s
                      AND (o.payment_status = 'paid' OR o.order_status = 'completed')
                      AND o.order_status != 'cancelled'
                      AND o.payment_status != 'failed'
                    GROUP BY oi.menu_item_id
                    ORDER BY units_sold DESC
                    LIMIT 5
                    """,
                    (shop_id,),
                ),
                (
                    """
                    SELECT m.category,
                           SUM(oi.quantity) as units,
                           SUM(oi.subtotal) as revenue
                    FROM order_items oi
                    INNER JOIN orders o ON o.id = oi.order_id
                    INNER JOIN menu_items m ON m.id = oi.menu_item_id
                    WHERE o.shop_id = %s
                      AND (o.payment_status = 'paid' OR o.order_status = 'completed')
                      AND o.order_status != 'cancelled'
                      AND o.payment_status != 'failed'
                    GROUP BY m.category
                    ORDER BY revenue DESC
                    """,
                    (shop_id,),
                ),
                (
                    """
                    SELECT SUBSTR(created_at, 12, 2) as order_hour,
                           COUNT(id) as count
                    FROM orders
                    WHERE shop_id = %s
                      AND (payment_status = 'paid' OR order_status = 'completed')
                      AND order_status != 'cancelled'
                    GROUP BY SUBSTR(created_at, 12, 2)
                    ORDER BY count DESC
                    """,
                    (shop_id,),
                ),
            ])

            shop = (results[0][0] if results[0] else None)
            if not shop:
                return None

            order_counts = (results[1][0] if results[1] else {}) or {}
            sales_summary = (results[2][0] if results[2] else {}) or {}
            top_items_rows = results[3]
            cat_rows = results[4]
            hourly_rows = results[5]

            total_orders = int(order_counts.get("total_orders") or 0)
            completed_orders = int(order_counts.get("completed_orders") or 0)
            cancelled_orders = int(order_counts.get("cancelled_orders") or 0)
            active_orders = int(order_counts.get("active_orders") or 0)
            completion_rate = round((completed_orders / total_orders * 100.0), 1) if total_orders > 0 else 0.0

            total_revenue = float(sales_summary.get("total_revenue") or 0.0)
            total_units_sold = int(sales_summary.get("total_units_sold") or 0)

            top_selling = [
                {
                    "item_id": r["menu_item_id"],
                    "item_name": r["name"],
                    "category": r["category"],
                    "units_sold": int(r["units_sold"]),
                    "revenue": float(r["item_revenue"]),
                }
                for r in top_items_rows
            ]

            categories = [
                {
                    "category": r["category"],
                    "units": int(r["units"]),
                    "revenue": float(r["revenue"]),
                }
                for r in cat_rows
            ]

            peak_hours = [
                {
                    "hour": int(r["order_hour"]) if str(r["order_hour"]).isdigit() else r["order_hour"],
                    "orders_count": int(r["count"])
                }
                for r in hourly_rows if r.get("order_hour")
            ]

            meal_slot_velocity = {
                "Breakfast (06:00-11:00)": 0,
                "Lunch (11:00-15:00)": 0,
                "Evening Snacks (15:00-19:00)": 0,
                "Dinner (19:00-06:00)": 0,
            }
            for ph in peak_hours:
                h = ph["hour"]
                if isinstance(h, int):
                    if 6 <= h < 11:
                        meal_slot_velocity["Breakfast (06:00-11:00)"] += ph["orders_count"]
                    elif 11 <= h < 15:
                        meal_slot_velocity["Lunch (11:00-15:00)"] += ph["orders_count"]
                    elif 15 <= h < 19:
                        meal_slot_velocity["Evening Snacks (15:00-19:00)"] += ph["orders_count"]
                    else:
                        meal_slot_velocity["Dinner (19:00-06:00)"] += ph["orders_count"]

            return {
                "shop_id": shop["id"],
                "shop_name": shop["name"],
                "operational_status": shop["operational_status"],
                "summary": {
                    "total_orders": total_orders,
                    "completed_orders": completed_orders,
                    "cancelled_orders": cancelled_orders,
                    "active_orders": active_orders,
                    "completion_rate_pct": completion_rate,
                    "total_units_sold": total_units_sold,
                    "total_revenue": total_revenue,
                },
                "top_selling_items": top_selling,
                "category_breakdown": categories,
                "peak_hours": peak_hours[:5],
                "meal_slot_demand": meal_slot_velocity,
            }
        except Exception as e:
            logger.error("Error computing shop analytics for shop_id=%s: %s", shop_id, e)
            return None

    @classmethod
    def get_admin_overview_analytics(cls):
        """Calculates platform-wide food court sales intelligence across all stalls."""
        try:
            # Keep all read-only analytics on one pooled connection. The admin
            # analytics endpoint otherwise performs several sequential DB
            # checkouts/returns before it can render the dashboard.
            results = DB.query_many([
                (
                    """
                    SELECT COUNT(id) as total_orders,
                           SUM(CASE WHEN order_status = 'completed' THEN 1 ELSE 0 END) as completed_orders,
                           SUM(CASE WHEN order_status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_orders,
                           SUM(CASE WHEN order_status IN ('pending', 'preparing', 'ready') THEN 1 ELSE 0 END) as active_orders
                    FROM orders
                    """,
                    (),
                ),
                (
                    """
                    SELECT COALESCE(SUM(o.total_amount), 0) as total_revenue,
                           COALESCE(SUM(oi.quantity), 0) as total_units_sold
                    FROM orders o
                    LEFT JOIN order_items oi ON oi.order_id = o.id
                    WHERE (o.payment_status = 'paid' OR o.order_status = 'completed')
                      AND o.order_status != 'cancelled'
                      AND o.payment_status != 'failed'
                    """,
                    (),
                ),
                (
                    """
                    SELECT s.id as shop_id, s.name as shop_name, s.operational_status,
                           COUNT(DISTINCT o.id) as orders_count,
                           COALESCE(SUM(CASE WHEN (o.payment_status = 'paid' OR o.order_status = 'completed') AND o.order_status != 'cancelled' THEN o.total_amount ELSE 0 END), 0) as revenue
                    FROM shops s
                    LEFT JOIN orders o ON o.shop_id = s.id
                    WHERE s.is_active = 1
                    GROUP BY s.id
                    ORDER BY revenue DESC
                    """,
                    (),
                ),
                (
                    """
                    SELECT oi.menu_item_id, m.name, s.name as shop_name, m.category,
                           SUM(oi.quantity) as units_sold,
                           SUM(oi.subtotal) as total_revenue
                    FROM order_items oi
                    INNER JOIN orders o ON o.id = oi.order_id
                    INNER JOIN menu_items m ON m.id = oi.menu_item_id
                    INNER JOIN shops s ON s.id = m.shop_id
                    WHERE (o.payment_status = 'paid' OR o.order_status = 'completed')
                      AND o.order_status != 'cancelled'
                      AND o.payment_status != 'failed'
                    GROUP BY oi.menu_item_id
                    ORDER BY units_sold DESC
                    LIMIT 8
                    """,
                    (),
                ),
                (
                    """
                    SELECT m.category,
                           SUM(oi.quantity) as units,
                           SUM(oi.subtotal) as revenue
                    FROM order_items oi
                    INNER JOIN orders o ON o.id = oi.order_id
                    INNER JOIN menu_items m ON m.id = oi.menu_item_id
                    WHERE (o.payment_status = 'paid' OR o.order_status = 'completed')
                      AND o.order_status != 'cancelled'
                      AND o.payment_status != 'failed'
                    GROUP BY m.category
                    ORDER BY revenue DESC
                    """,
                    (),
                ),
            ])

            order_counts = (results[0][0] if results[0] else {}) or {}
            sales_summary = (results[1][0] if results[1] else {}) or {}
            stall_stats = results[2]
            top_items = results[3]
            cat_rows = results[4]

            stall_performance = [
                {
                    "shop_id": r["shop_id"],
                    "shop_name": r["shop_name"],
                    "operational_status": r["operational_status"],
                    "orders_count": int(r["orders_count"] or 0),
                    "revenue": float(r["revenue"] or 0.0),
                }
                for r in stall_stats
            ]

            top_selling = [
                {
                    "item_id": r["menu_item_id"],
                    "item_name": r["name"],
                    "shop_name": r["shop_name"],
                    "category": r["category"],
                    "units_sold": int(r["units_sold"]),
                    "revenue": float(r["total_revenue"]),
                }
                for r in top_items
            ]

            categories = [
                {
                    "category": r["category"],
                    "units": int(r["units"]),
                    "revenue": float(r["revenue"]),
                }
                for r in cat_rows
            ]

            return {
                "summary": {
                    "total_orders": int(order_counts.get("total_orders") or 0),
                    "completed_orders": int(order_counts.get("completed_orders") or 0),
                    "cancelled_orders": int(order_counts.get("cancelled_orders") or 0),
                    "active_orders": int(order_counts.get("active_orders") or 0),
                    "total_revenue": float(sales_summary.get("total_revenue") or 0.0),
                    "total_units_sold": int(sales_summary.get("total_units_sold") or 0),
                },
                "stalls_performance": stall_performance,
                "top_selling_items": top_selling,
                "category_shares": categories,
            }
        except Exception as e:
            logger.error("Error computing admin overview analytics: %s", e)
            return {
                "summary": {
                    "total_orders": 0,
                    "completed_orders": 0,
                    "cancelled_orders": 0,
                    "active_orders": 0,
                    "total_revenue": 0.0,
                    "total_units_sold": 0,
                },
                "stalls_performance": [],
                "top_selling_items": [],
                "category_shares": [],
            }
