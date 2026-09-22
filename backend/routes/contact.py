import re
from flask import Blueprint, jsonify, request, session
from db import DB
from routes.auth import role_required

contact_bp = Blueprint("contact", __name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@contact_bp.post("")
def submit_contact_message():
    """Public contact form submission stored for Admin review."""
    data = request.get_json(silent=True) or {}
    full_name = str(data.get("full_name") or data.get("name") or "").strip()
    email = str(data.get("email") or "").strip().lower()
    subject = str(data.get("subject") or "").strip()
    message = str(data.get("message") or "").strip()

    if not full_name or len(full_name) > 120:
        return jsonify({"success": False, "message": "Please enter a valid name."}), 400
    if not _EMAIL_RE.match(email) or len(email) > 180:
        return jsonify({"success": False, "message": "Please enter a valid college email address."}), 400
    if not subject or len(subject) > 180:
        return jsonify({"success": False, "message": "Please enter a valid subject."}), 400
    if not message or len(message) > 5000:
        return jsonify({"success": False, "message": "Message must contain between 1 and 5000 characters."}), 400

    contact_id = DB.execute(
        """INSERT INTO contact_messages (full_name, email, subject, message, status)
           VALUES (%s, %s, %s, %s, 'new')""",
        (full_name, email, subject, message),
    )
    return jsonify({
        "success": True,
        "message": "Your message has been submitted successfully.",
        "contact_id": contact_id,
    }), 201


@contact_bp.get("/admin")
@role_required(["admin"])
def get_contact_messages():
    status = str(request.args.get("status") or "").strip().lower()
    search = str(request.args.get("q") or "").strip().lower()
    limit = max(1, min(100, int(request.args.get("limit", 100) or 100)))

    sql = """SELECT id, full_name, email, subject, message, status, created_at, read_at, resolved_at
             FROM contact_messages WHERE 1=1"""
    params = []
    if status in {"new", "read", "resolved"}:
        sql += " AND status = %s"
        params.append(status)
    if search:
        pattern = f"%{search}%"
        sql += " AND (LOWER(full_name) LIKE %s OR LOWER(email) LIKE %s OR LOWER(subject) LIKE %s OR LOWER(message) LIKE %s)"
        params.extend([pattern, pattern, pattern, pattern])
    sql += " ORDER BY id DESC LIMIT %s"
    params.append(limit)

    rows = DB.query(sql, tuple(params))
    return jsonify({"success": True, "messages": rows}), 200


@contact_bp.put("/admin/<int:message_id>/status")
@role_required(["admin"])
def update_contact_message_status(message_id):
    data = request.get_json(silent=True) or {}
    status = str(data.get("status") or "").strip().lower()
    if status not in {"new", "read", "resolved"}:
        return jsonify({"success": False, "message": "Status must be new, read, or resolved."}), 400

    row = DB.get_one("SELECT id FROM contact_messages WHERE id = %s", (message_id,))
    if not row:
        return jsonify({"success": False, "message": "Contact message not found."}), 404

    if status == "new":
        DB.execute("UPDATE contact_messages SET status='new', read_at=NULL, resolved_at=NULL WHERE id=%s", (message_id,))
    elif status == "read":
        DB.execute("UPDATE contact_messages SET status='read', read_at=COALESCE(read_at, CURRENT_TIMESTAMP), resolved_at=NULL WHERE id=%s", (message_id,))
    else:
        DB.execute("UPDATE contact_messages SET status='resolved', read_at=COALESCE(read_at, CURRENT_TIMESTAMP), resolved_at=CURRENT_TIMESTAMP WHERE id=%s", (message_id,))

    return jsonify({"success": True, "status": status}), 200
