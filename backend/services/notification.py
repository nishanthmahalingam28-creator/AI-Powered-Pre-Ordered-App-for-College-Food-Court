"""
Centralized Notification Service for College Food Court Platform.

Connects Customer, Order, Vendor, and Admin personas throughout the order lifecycle.
CRITICAL DESIGN PRINCIPLES:
1. Non-Blocking Delivery: Notification failures must NEVER abort or roll back
   underlying order or payment transactions.
2. Idempotency: Redundant webhooks or repeated order-status requests do not generate
   duplicate notifications.
3. Strict Vendor Shop Isolation: Resolves vendor recipient from server-side database
   stall ownership (shops.owner_user_id); never trusts client input.
4. XSS Sanitization: Escapes untrusted input to prevent script injection.
5. No Secret Leakage: No passwords, OTP secrets, card details, or payment secrets.
"""

import html
import logging
from datetime import datetime
from db import DB

logger = logging.getLogger("food_court.notification_service")


class NotificationType:
    ORDER_PLACED = "ORDER_PLACED"
    PAYMENT_SUCCESS = "PAYMENT_SUCCESS"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    ORDER_PREPARING = "ORDER_PREPARING"
    ORDER_READY = "ORDER_READY"
    ORDER_COMPLETED = "ORDER_COMPLETED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    PICKUP_REMINDER = "PICKUP_REMINDER"
    SYSTEM = "SYSTEM"

    ALL_TYPES = {
        ORDER_PLACED,
        PAYMENT_SUCCESS,
        PAYMENT_FAILED,
        ORDER_PREPARING,
        ORDER_READY,
        ORDER_COMPLETED,
        ORDER_CANCELLED,
        PICKUP_REMINDER,
        SYSTEM
    }


class NotificationService:
    @staticmethod
    def sanitize_text(value: str) -> str:
        """Escapes HTML entities to prevent stored XSS attacks."""
        if not value:
            return ""
        return html.escape(str(value).strip(), quote=True)

    @classmethod
    def check_duplicate_notification(cls, user_id: int, order_id: int, notif_type: str, executor=None) -> bool:
        """
        Idempotency guard:
        Returns True if a notification of notif_type for this order_id and user_id
        has already been recorded in the database.
        """
        if not order_id or not user_id:
            return False
        db_exec = executor if executor is not None else DB
        try:
            existing = db_exec.get_one(
                """
                SELECT id FROM notifications
                WHERE user_id = %s AND order_id = %s AND type = %s
                LIMIT 1
                """,
                (user_id, order_id, notif_type)
            )
            return existing is not None
        except Exception as e:
            logger.warning("Failed to check duplicate notification for user=%s order=%s: %s", user_id, order_id, e)
            return False

    @classmethod
    def create_notification(
        cls,
        user_id: int,
        notif_type: str,
        title: str,
        message: str,
        order_id: int = None,
        delivery_status: str = "delivered",
        failure_reason: str = None,
        tx=None,
        check_duplicate: bool = True
    ):
        """
        Persists a notification record in the database.
        Wraps errors safely to protect the caller's transaction.
        """
        if not user_id:
            logger.warning("Attempted to create notification with null user_id.")
            return None

        # Idempotency check if order_id is provided
        if check_duplicate and order_id:
            if cls.check_duplicate_notification(user_id, order_id, notif_type, executor=tx):
                logger.info("Suppressed duplicate notification [%s] for user_id=%s, order_id=%s", notif_type, user_id, order_id)
                return None

        clean_title = cls.sanitize_text(title)
        clean_msg = cls.sanitize_text(message)
        valid_type = notif_type if notif_type in NotificationType.ALL_TYPES else NotificationType.SYSTEM
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        db_exec = tx if tx is not None else DB

        try:
            notif_id = db_exec.execute(
                """
                INSERT INTO notifications (user_id, order_id, type, title, message, is_read,
                                           delivery_status, delivered_at, failure_reason, created_at)
                VALUES (%s, %s, %s, %s, %s, 0, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    order_id,
                    valid_type,
                    clean_title,
                    clean_msg,
                    delivery_status,
                    now_str if delivery_status == "delivered" else None,
                    failure_reason,
                    now_str,
                ),
            )
            logger.debug("Notification created [ID %s, Type %s] for user_id=%s", notif_id, valid_type, user_id)
            return notif_id
        except Exception as e:
            logger.error("Failed to insert notification for user_id=%s: %s", user_id, e)
            # NEVER raise: Notification failure must not disrupt caller
            return None

    @classmethod
    def notify_user(cls, user_id: int, notif_type: str, title: str, message: str, order_id: int = None, tx=None):
        """Convenience alias for notifying a specific user."""
        return cls.create_notification(
            user_id=user_id,
            notif_type=notif_type,
            title=title,
            message=message,
            order_id=order_id,
            tx=tx
        )

    @classmethod
    def notify_customer(cls, customer_id: int, notif_type: str, title: str, message: str, order_id: int = None, tx=None):
        """Dispatches an authoritative notification to a customer."""
        try:
            return cls.create_notification(
                user_id=customer_id,
                notif_type=notif_type,
                title=title,
                message=message,
                order_id=order_id,
                tx=tx
            )
        except Exception as e:
            logger.error("Error in notify_customer (non-fatal): %s", e)
            return None

    @classmethod
    def notify_vendor(cls, shop_id: int, notif_type: str, title: str, message: str, order_id: int = None, tx=None):
        """
        Resolves vendor user assigned to the stall from server-side database ownership.
        Strict isolation: Never trusts client-supplied vendor identity.
        """
        try:
            db_exec = tx if tx is not None else DB
            shop = db_exec.get_one("SELECT owner_user_id, name FROM shops WHERE id = %s", (shop_id,))
            if not shop or not shop.get("owner_user_id"):
                logger.warning("No owner vendor assigned to shop_id=%s; vendor notification skipped.", shop_id)
                return None

            vendor_user_id = shop["owner_user_id"]
            return cls.create_notification(
                user_id=vendor_user_id,
                notif_type=notif_type,
                title=title,
                message=message,
                order_id=order_id,
                tx=tx
            )
        except Exception as e:
            logger.error("Error in notify_vendor (non-fatal) for shop_id=%s: %s", shop_id, e)
            return None

    @classmethod
    def notify_admin(cls, notif_type: str, title: str, message: str, order_id: int = None, tx=None):
        """
        Dispatches a high-priority notification to administrative users.
        Used strictly for critical system or payment governance events.
        """
        try:
            db_exec = tx if tx is not None else DB
            admins = db_exec.query("SELECT id FROM users WHERE role = 'admin' AND is_active = 1")
            notified_ids = []
            for a in admins:
                nid = cls.create_notification(
                    user_id=a["id"],
                    notif_type=notif_type,
                    title=title,
                    message=message,
                    order_id=order_id,
                    tx=tx,
                    check_duplicate=False
                )
                if nid:
                    notified_ids.append(nid)
            return notified_ids
        except Exception as e:
            logger.error("Error in notify_admin (non-fatal): %s", e)
            return []

    @classmethod
    def get_notifications(
        cls,
        user_id: int,
        unread_only: bool = False,
        type_filter: str = None,
        page: int = 1,
        limit: int = 20
    ):
        """
        Returns paginated notifications belonging strictly to the authenticated user.
        Supports unread filtering, type categorization, and total counts.
        """
        if not user_id:
            return {"notifications": [], "total": 0, "unread_count": 0, "page": 1, "limit": limit}

        safe_page = max(1, int(page or 1))
        safe_limit = max(1, min(50, int(limit or 20)))
        offset = (safe_page - 1) * safe_limit

        where_clauses = ["user_id = %s"]
        params = [user_id]

        if unread_only:
            where_clauses.append("is_read = 0")

        if type_filter and type_filter.strip():
            clean_type = type_filter.strip().upper()
            if clean_type == "ORDER":
                where_clauses.append("type LIKE 'ORDER_%'")
            elif clean_type == "PAYMENT":
                where_clauses.append("type LIKE 'PAYMENT_%'")
            elif clean_type in NotificationType.ALL_TYPES:
                where_clauses.append("type = %s")
                params.append(clean_type)

        where_sql = " AND ".join(where_clauses)

        count_sql = f"SELECT COUNT(*) as total FROM notifications WHERE {where_sql}"
        total_row = DB.get_one(count_sql, tuple(params)) or {}
        total = int(total_row.get("total") or 0)

        unread_count = cls.get_unread_count(user_id)

        data_sql = f"""
            SELECT id, user_id, order_id, type, title, message, is_read,
                   delivery_status, delivered_at, failure_reason, read_at, created_at
            FROM notifications
            WHERE {where_sql}
            ORDER BY id DESC
            LIMIT %s OFFSET %s
        """
        data_params = list(params) + [safe_limit, offset]
        rows = DB.query(data_sql, tuple(data_params))

        notifications = []
        for r in rows:
            notifications.append({
                "id": r["id"],
                "user_id": r["user_id"],
                "order_id": r.get("order_id"),
                "type": r["type"],
                "title": r["title"],
                "message": r["message"],
                "is_read": bool(r.get("is_read")),
                "delivery_status": r.get("delivery_status") or "delivered",
                "delivered_at": str(r.get("delivered_at") or ""),
                "failure_reason": r.get("failure_reason"),
                "read_at": str(r.get("read_at") or ""),
                "created_at": str(r.get("created_at") or ""),
            })

        return {
            "notifications": notifications,
            "total": total,
            "unread_count": unread_count,
            "page": safe_page,
            "limit": safe_limit,
            "pages": (total + safe_limit - 1) // safe_limit if total > 0 else 1
        }

    @classmethod
    def get_unread_count(cls, user_id: int) -> int:
        """Returns the total number of unread notifications for a user."""
        if not user_id:
            return 0
        try:
            row = DB.get_one(
                "SELECT COUNT(*) as unread_count FROM notifications WHERE user_id = %s AND is_read = 0",
                (user_id,)
            ) or {}
            return int(row.get("unread_count") or 0)
        except Exception as e:
            logger.warning("Error getting unread count for user_id=%s: %s", user_id, e)
            return 0

    @classmethod
    def mark_as_read(cls, notification_id: int, user_id: int) -> bool:
        """
        Marks a single notification as read.
        Strict IDOR protection: only the owner can mark their notification.
        """
        if not notification_id or not user_id:
            return False
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            affected = DB.execute_update(
                """
                UPDATE notifications
                SET is_read = 1, read_at = %s
                WHERE id = %s AND user_id = %s
                """,
                (now_str, notification_id, user_id)
            )
            return affected > 0
        except Exception as e:
            logger.error("Error marking notification %s as read for user %s: %s", notification_id, user_id, e)
            return False

    @classmethod
    def mark_all_as_read(cls, user_id: int) -> int:
        """
        Marks all unread notifications for the authenticated user as read.
        Returns the number of notifications updated.
        """
        if not user_id:
            return 0
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            affected = DB.execute_update(
                """
                UPDATE notifications
                SET is_read = 1, read_at = %s
                WHERE user_id = %s AND is_read = 0
                """,
                (now_str, user_id)
            )
            return affected
        except Exception as e:
            logger.error("Error marking all notifications read for user %s: %s", user_id, e)
            return 0
