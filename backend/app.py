from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os

from routes.auth import auth_bp

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-this-secret-key")

# Frontend runs on a local development server (for example :5500).
# Restrict CORS to configured origins instead of allowing every origin.
allowed_origins = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500").split(",")
    if origin.strip()
]
CORS(app, resources={r"/api/*": {"origins": allowed_origins}}, supports_credentials=True)

app.register_blueprint(auth_bp, url_prefix="/api/auth")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "food-court-api"})


@app.get("/")
def root():
    return jsonify({
        "name": "AI-Powered Pre-Ordered App for College Food Court",
        "status": "running",
        "health": "/api/health",
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=True)
