import logging
import re
from flask import Blueprint, jsonify, request, session
from db import DB, get_db_connection, release_mysql_connection
from routes.auth import role_required

logger = logging.getLogger("food_court.contact")
contact_bp = Blueprint("contact", __name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _ensure_contact_table():
    """Ensure contact_messages table exists in either MySQL or SQLite environment."""
    db_type, conn = get_db_connection()
    try:
        if db_type == "mysql":
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS contact_messages (
                        id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                        full_name VARCHAR(120) NOT NULL,
                        email VARCHAR(180) NOT NULL,
                        subject VARCHAR(180) NOT NULL,
                        message TEXT NOT NULL,
                        status ENUM('new','read','resolved') NOT NULL DEFAULT 'new',
                        read_at DATETIME NULL,
                        resolved_at DATETIME NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_contact_status_created (status, created_at),
                        INDEX idx_contact_email (email)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
        else:
            cur = conn.cursor()
            try:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS contact_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        full_name TEXT NOT NULL,
                        email TEXT NOT NULL,
                        subject TEXT NOT NULL,
                        message TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'new',
                        read_at TIMESTAMP NULL,
                        resolved_at TIMESTAMP NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
            finally:
                cur.close()
    finally:
        if db_type == "mysql":
            release_mysql_connection(conn)
        else:
            conn.close()


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

    try:
        _ensure_contact_table()
        contact_id = DB.execute(
            """INSERT INTO contact_messages (full_name, email, subject, message, status)
               VALUES (%s, %s, %s, %s, 'new')""",
            (full_name, email, subject, message),
        )
        if not contact_id:
            row = DB.get_one("SELECT id FROM contact_messages WHERE email = %s ORDER BY id DESC LIMIT 1", (email,))
            contact_id = row["id"] if row else 1

        return jsonify({
            "success": True,
            "message": "Your message has been submitted successfully.",
            "contact_id": contact_id,
        }), 201
    except Exception as e:
        logger.error("Failed to insert contact report: %s", e)
        return jsonify({"success": False, "message": "Failed to submit message. Please try again later."}), 500


@contact_bp.get("/admin")
@role_required(["admin"])
def get_contact_messages():
    status = str(request.args.get("status") or "").strip().lower()
    search = str(request.args.get("q") or "").strip().lower()

    try:
        _ensure_contact_table()
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

        rows = DB.query(sql, tuple(params)) or []
        for r in rows:
            if "name" not in r and "full_name" in r:
                r["name"] = r["full_name"]
            elif "full_name" not in r and "name" in r:
                r["full_name"] = r["name"]
            if hasattr(r.get("created_at"), "isoformat"):
                r["created_at"] = r["created_at"].isoformat()
            elif r.get("created_at") is not None:
                r["created_at"] = str(r["created_at"])

        return jsonify({
            "success": True,
            "messages": rows,
            "reports": rows,
        }), 200
    except Exception as e:
        logger.error("Failed to retrieve contact reports: %s", e)
        return jsonify({"success": False, "message": "Failed to retrieve contact reports."}), 500


@contact_bp.put("/admin/<int:message_id>/status")
@role_required(["admin"])
def update_contact_message_status(message_id):
    data = request.get_json(silent=True) or {}
    status = str(data.get("status") or "").strip().lower()
    if status not in {"new", "read", "resolved"}:
        return jsonify({"success": False, "message": "Status must be new, read, or resolved."}), 400

    try:
        _ensure_contact_table()
        row = DB.get_one("SELECT id FROM contact_messages WHERE id = %s", (message_id,))
        if not row:
            return jsonify({"success": False, "message": "Contact message not found."}), 404

        DB.execute("UPDATE contact_messages SET status=%s WHERE id=%s", (status, message_id))
        return jsonify({"success": True, "status": status}), 200
    except Exception as e:
        logger.error("Failed to update contact report status: %s", e)
        return jsonify({"success": False, "message": "Failed to update contact report."}), 500
