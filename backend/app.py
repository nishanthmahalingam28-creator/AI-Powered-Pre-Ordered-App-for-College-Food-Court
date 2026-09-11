from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os

from routes.auth import auth_bp
from routes.menu import menu_bp
from routes.orders import orders_bp
from routes.vendor import vendor_bp
from routes.admin import admin_bp
from routes.recommendations import recommend_bp

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "kpr-food-court-secure-session-key-2026-9f8a3c1e")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

is_development = os.getenv("FLASK_ENV", "production").lower() == "development" or os.getenv("FLASK_DEBUG", "0").lower() in ("1", "true")
if not is_development and os.getenv("COOKIE_SECURE", "0").lower() in ("1", "true"):
    app.config["SESSION_COOKIE_SECURE"] = True

# Frontend runs on local dev ports (e.g. 5500)
allowed_origins = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500,http://localhost:3000").split(",")
    if origin.strip()
]
CORS(app, resources={r"/api/*": {"origins": allowed_origins}}, supports_credentials=True)

# Register All API Blueprints
app.register_blueprint(auth_bp, url_prefix="/api/auth")
app.register_blueprint(menu_bp, url_prefix="/api")
app.register_blueprint(orders_bp, url_prefix="/api/orders")
app.register_blueprint(vendor_bp, url_prefix="/api/vendor")
app.register_blueprint(admin_bp, url_prefix="/api/admin")
app.register_blueprint(recommend_bp, url_prefix="/api/recommendations")


@app.errorhandler(404)
def not_found_handler(e):
    return jsonify({"success": False, "message": "The requested API resource was not found."}), 404


@app.errorhandler(500)
def server_error_handler(e):
    return jsonify({"success": False, "message": "An internal server error occurred. Please try again."}), 500


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
            "recommendations": "/api/recommendations"
        }
    })


if __name__ == "__main__":
    flask_env = os.getenv("FLASK_ENV", "production").lower()
    debug_mode = os.getenv("FLASK_DEBUG", "0").lower() in ("1", "true") or flask_env == "development"
    port = int(os.getenv("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=debug_mode)
