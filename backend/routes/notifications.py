"""
Notification API Endpoints for College Food Court Application.

Enforces server-side authentication, strict ownership validation (IDOR protection),
paginated feeds, and unread counter tracking.
"""

from flask import Blueprint, request, jsonify, session
from routes.auth import role_required
from services.notification import NotificationService
from db import DB

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.get("")
@role_required(["customer", "vendor", "admin"])
def get_user_notifications():
    """
    Returns paginated notifications belonging exclusively to the authenticated user.
    Supports filtering by read state and notification category.
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Authentication required."}), 401

    raw_unread = request.args.get("unread", "").strip().lower()
    unread_only = raw_unread in ("1", "true", "yes")
    type_filter = request.args.get("type", "").strip()

    try:
        page = max(1, int(request.args.get("page", 1)))
        limit = max(1, min(50, int(request.args.get("limit", 20))))
    except (ValueError, TypeError):
        page = 1
        limit = 20

    data = NotificationService.get_notifications(
        user_id=user_id,
        unread_only=unread_only,
        type_filter=type_filter,
        page=page,
        limit=limit
    )

    return jsonify({
        "success": True,
        "notifications": data["notifications"],
        "total": data["total"],
        "unread_count": data["unread_count"],
        "page": data["page"],
        "limit": data["limit"],
        "pages": data["pages"]
    }), 200


@notifications_bp.get("/unread-count")
@role_required(["customer", "vendor", "admin"])
def get_unread_notification_count():
    """Returns the total unread notification count for the authenticated user."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Authentication required."}), 401

    count = NotificationService.get_unread_count(user_id)
    return jsonify({
        "success": True,
        "unread_count": count
    }), 200


@notifications_bp.put("/<int:notif_id>/read")
@role_required(["customer", "vendor", "admin"])
def mark_notification_read(notif_id):
    """
    Marks a single notification as read.
    Enforces strict IDOR protection: only the owner can modify their notification.
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Authentication required."}), 401

    # Check notification existence and ownership
    notif = DB.get_one("SELECT id, user_id FROM notifications WHERE id = %s", (notif_id,))
    if not notif:
        return jsonify({"success": False, "message": "Notification not found."}), 404

    if notif["user_id"] != user_id:
        return jsonify({
            "success": False,
            "message": "Forbidden: You cannot modify notifications belonging to another user."
        }), 403

    success = NotificationService.mark_as_read(notif_id, user_id)
    if not success:
        return jsonify({"success": False, "message": "Unable to update notification."}), 400

    unread_count = NotificationService.get_unread_count(user_id)
    return jsonify({
        "success": True,
        "message": "Notification marked as read.",
        "notification_id": notif_id,
        "unread_count": unread_count
    }), 200


@notifications_bp.put("/read-all")
@role_required(["customer", "vendor", "admin"])
def mark_all_notifications_read():
    """
    Marks all notifications for the authenticated user as read.
    Guarantees no modifications to other users' notifications.
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Authentication required."}), 401

    count = NotificationService.mark_all_as_read(user_id)
    return jsonify({
        "success": True,
        "message": "All notifications marked as read.",
        "marked_count": count,
        "unread_count": 0
    }), 200
