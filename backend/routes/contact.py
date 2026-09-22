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

    # Guarantee the storage table exists even if a production deployment
    # started before the Contact Reports migration ran.
    DB.execute("""
        CREATE TABLE IF NOT EXISTS contact_messages (
            id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            full_name VARCHAR(120) NOT NULL,
            email VARCHAR(180) NOT NULL,
            subject VARCHAR(180) NOT NULL,
            message TEXT NOT NULL,
            status ENUM('new','read','resolved') NOT NULL DEFAULT 'new',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_contact_status_created (status, created_at),
            INDEX idx_contact_email (email)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

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
    # Keep this admin list intentionally simple and bounded so Contact Reports
    # cannot become slow because of a large/legacy production table.
    limit = 100

    sql = """SELECT id, full_name, email, subject, message, status, created_at
             FROM contact_messages WHERE 1=1"""
    params = []
    if status in {"new", "read", "resolved"}:
        sql += " AND status = %s"
        params.append(status)
    if search:
        pattern = f"%{search}%"
        sql += " AND (LOWER(full_name) LIKE %s OR LOWER(email) LIKE %s OR LOWER(subject) LIKE %s OR LOWER(message) LIKE %s)"
        params.extend([pattern, pattern, pattern, pattern])
    sql += " ORDER BY id DESC LIMIT 100"

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

    # Status is the core workflow field; keep it compatible with older
    # production contact_messages tables that do not have timestamp columns.
    DB.execute("UPDATE contact_messages SET status=%s WHERE id=%s", (status, message_id))

    return jsonify({"success": True, "status": status}), 200
