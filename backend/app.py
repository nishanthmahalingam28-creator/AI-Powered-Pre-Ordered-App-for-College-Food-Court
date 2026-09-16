import os
import secrets
import logging
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

from db import DatabaseConnectionError, DatabaseError
from routes.auth import auth_bp
from routes.menu import menu_bp
from routes.orders import orders_bp
from routes.vendor import vendor_bp
from routes.admin import admin_bp
from routes.recommendations import recommend_bp
from routes.customer import customer_bp
from routes.payments import payments_bp

load_dotenv()

# Determine environment: strictly production by default unless explicitly specified as development/test
flask_env = os.getenv("FLASK_ENV", "production").lower()
is_development = flask_env in ("development", "dev", "test", "testing")

# Production-grade standard logging setup
logging.basicConfig(
    level=logging.INFO if not is_development else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("food_court.app")

app = Flask(__name__)

# Secret key validation:
# - Production: MUST be supplied via environment variable; refuses to start if missing.
# - Development: Reads from .env or generates an ephemeral development key with warning.
secret_key = os.getenv("SECRET_KEY")
if not secret_key:
    if not is_development:
        logger.critical("FATAL: SECRET_KEY environment variable is required in production mode.")
        raise RuntimeError(
            "FATAL: SECRET_KEY environment variable must be set in production mode. "
            "Application refused to start with insecure defaults."
        )
    else:
        logger.warning(
            "DEVELOPMENT WARNING: No SECRET_KEY found in environment. "
            "Generating ephemeral development secret key. Sessions will not persist across server restarts."
        )
        secret_key = secrets.token_hex(32)

app.config["SECRET_KEY"] = secret_key
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Session cookie security:
# In development: default to False to support local HTTP development.
# In production: default to True unless explicitly disabled via COOKIE_SECURE=0.
if is_development:
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("COOKIE_SECURE", "0").lower() in ("1", "true")
else:
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("COOKIE_SECURE", "1").lower() in ("1", "true")

# CORS Origin Configuration:
# Never permit wildcard '*' with credentials in production.
raw_origins = os.getenv("CORS_ORIGINS") or os.getenv("FRONTEND_ORIGINS")
if raw_origins:
    allowed_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
elif is_development:
    allowed_origins = ["http://localhost:5500", "http://127.0.0.1:5500", "http://localhost:3000"]
else:
    logger.warning("CORS_ORIGINS not specified in production. Cross-origin access restricted.")
    allowed_origins = []

if "*" in allowed_origins and not is_development:
    logger.error("Insecure CORS configuration: Wildcard '*' with credentials is forbidden in production.")
    allowed_origins = [o for o in allowed_origins if o != "*"]

CORS(app, resources={r"/api/*": {"origins": allowed_origins}}, supports_credentials=True)

# Register All API Blueprints
app.register_blueprint(auth_bp, url_prefix="/api/auth")
app.register_blueprint(menu_bp, url_prefix="/api")
app.register_blueprint(orders_bp, url_prefix="/api/orders")
app.register_blueprint(vendor_bp, url_prefix="/api/vendor")
app.register_blueprint(admin_bp, url_prefix="/api/admin")
app.register_blueprint(recommend_bp, url_prefix="/api/recommendations")
app.register_blueprint(customer_bp, url_prefix="/api/customer")
app.register_blueprint(payments_bp, url_prefix="/api/payments")


@app.before_request
def log_request_info():
    if request.path != "/api/health":
        logger.debug("Request: %s %s from %s", request.method, request.path, request.remote_addr)


@app.errorhandler(DatabaseConnectionError)
def db_connection_error_handler(e):
    logger.error("Database connection failure during request to %s: %s", request.path, type(e).__name__)
    return jsonify({
        "success": False,
        "message": "Database service temporarily unavailable. Please try again later."
    }), 503


@app.errorhandler(DatabaseError)
def db_error_handler(e):
    logger.error("Database execution error during request to %s: %s", request.path, type(e).__name__)
    return jsonify({
        "success": False,
        "message": "Database query failed. Please try again."
    }), 500


@app.errorhandler(400)
def bad_request_handler(e):
    return jsonify({"success": False, "message": getattr(e, "description", "Bad request.")}), 400


@app.errorhandler(401)
def unauthorized_handler(e):
    return jsonify({"success": False, "message": getattr(e, "description", "Authentication required.")}), 401


@app.errorhandler(403)
def forbidden_handler(e):
    return jsonify({"success": False, "message": getattr(e, "description", "Forbidden: Insufficient privileges.")}), 403


@app.errorhandler(404)
def not_found_handler(e):
    return jsonify({"success": False, "message": "The requested API resource was not found."}), 404


@app.errorhandler(405)
def method_not_allowed_handler(e):
    return jsonify({"success": False, "message": "Method not allowed."}), 405


@app.errorhandler(500)
def server_error_handler(e):
    logger.error("Internal 500 error on %s %s: %s", request.method, request.path, type(e).__name__)
    return jsonify({"success": False, "message": "An internal server error occurred. Please try again."}), 500


@app.errorhandler(Exception)
def unhandled_exception_handler(e):
    logger.error("Unhandled server exception on %s %s: %s", request.method, request.path, type(e).__name__)
    return jsonify({"success": False, "message": "An unexpected error occurred. Please try again."}), 500


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "food-court-api", "version": "2.0.0"})


@app.get("/")
def root():
    return jsonify({
        "name": "AI-Powered Pre-Ordered App for College Food Court",
        "status": "running",
        "health": "/api/health",
        "endpoints": {
            "auth": "/api/auth",
            "shops": "/api/shops",
            "menu": "/api/menu",
            "orders": "/api/orders",
            "vendor": "/api/vendor",
            "admin": "/api/admin",
            "customer": "/api/customer",
            "recommendations": "/api/recommendations"
        }
    })


if __name__ == "__main__":
    # Ensure production strictly runs with debug=False
    debug_mode = False
    if is_development:
        debug_mode = os.getenv("FLASK_DEBUG", "0").lower() in ("1", "true") or flask_env == "development"

    port = int(os.getenv("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=debug_mode)
