"""
Production Configuration Management for College Food Court Backend.

Supports distinct environments:
- DevelopmentConfig: local SQLite/MySQL, debug logging, local CORS.
- TestingConfig: isolated testing DB, ephemeral keys.
- ProductionConfig: strictly requires SECRET_KEY, MySQL, strict CORS, secure cookies.
"""

import os
import re
import secrets
import urllib.parse
from dotenv import load_dotenv

load_dotenv()


class BaseConfig:
    """Base configuration common to all environments."""
    APP_NAME = "AI-Powered Pre-Ordered App for College Food Court"
    VERSION = "2.0.0"
    
    # Flask Core
    PORT = int(os.getenv("PORT", "5000"))
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max payload
    
    # Cookie & Session Defaults
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    
    # Database Settings
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "food_court_db")
    DB_TIMEOUT = int(os.getenv("DB_TIMEOUT", "5"))
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    # Razorpay Payment Gateway
    PAYMENT_PROVIDER = os.getenv("PAYMENT_PROVIDER", "razorpay")
    PAYMENT_ENVIRONMENT = os.getenv("PAYMENT_ENVIRONMENT", "test")
    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
    RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
    
    # Multi-worker & WSGI Tuning
    GUNICORN_WORKERS = int(os.getenv("GUNICORN_WORKERS", "4"))
    GUNICORN_THREADS = int(os.getenv("GUNICORN_THREADS", "2"))
    GUNICORN_TIMEOUT = int(os.getenv("GUNICORN_TIMEOUT", "30"))

    @classmethod
    def get_cors_origins(cls):
        """Parses and returns allowed CORS origins."""
        raw = os.getenv("CORS_ORIGINS") or os.getenv("FRONTEND_ORIGINS")
        if raw:
            return [o.strip() for o in raw.split(",") if o.strip()]
        return []


class DevelopmentConfig(BaseConfig):
    """Development configuration for local workstation execution."""
    ENV = "development"
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "0").lower() in ("1", "true")
    SECRET_KEY = os.getenv("SECRET_KEY") or "dev-insecure-ephemeral-key-replace-in-prod"
    USE_SQLITE = os.getenv("USE_SQLITE", "0").lower() in ("1", "true")

    @classmethod
    def get_cors_origins(cls):
        origins = super().get_cors_origins()
        if not origins:
            return ["http://localhost:5500", "http://127.0.0.1:5500", "http://localhost:3000", "http://127.0.0.1:3000"]
        return origins


class TestingConfig(BaseConfig):
    """Testing configuration for automated unit and integration tests."""
    ENV = "testing"
    DEBUG = False
    TESTING = True
    SESSION_COOKIE_SECURE = False
    SECRET_KEY = os.getenv("SECRET_KEY") or "test-secret-key-32-chars-long-ok-123"
    USE_SQLITE = True

    @classmethod
    def get_cors_origins(cls):
        return ["http://localhost:5500", "http://127.0.0.1:5500"]


class ProductionConfig(BaseConfig):
    """
    Production configuration enforcing strict security invariants:
    - SECRET_KEY must be provided via environment variable; no default is allowed.
    - Database credentials (DB_PASSWORD or DATABASE_URL) are strictly required.
    - Live Razorpay credentials are strictly required; test/placeholder keys are rejected.
    - MySQL is strictly mandatory; SQLite fallback is forbidden.
    - SESSION_COOKIE_SECURE defaults to True.
    - Insecure wildcard '*' in CORS with credentials is forbidden.
    - Debug mode is strictly disabled.
    """
    ENV = "production"
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "1").lower() in ("1", "true")

    def __init__(self):
        super().__init__()
        self.SECRET_KEY = os.getenv("SECRET_KEY")
        if not self.SECRET_KEY or self.SECRET_KEY.startswith("dev-") or len(self.SECRET_KEY) < 16:
            raise RuntimeError(
                "FATAL: A strong SECRET_KEY environment variable is strictly required in production mode. "
                "Application refused to boot with missing or insecure defaults."
            )

        # Database credentials enforcement
        self.DB_PASSWORD = os.getenv("DB_PASSWORD", "").strip()
        self.DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
        if not self.DATABASE_URL and not self.DB_PASSWORD:
            raise RuntimeError(
                "FATAL: Database credentials (DB_PASSWORD or DATABASE_URL) are strictly required in production mode."
            )

        # Razorpay live credentials enforcement
        self.RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "").strip()
        self.RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
        self.RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip()
        if not self.RAZORPAY_KEY_ID or self.RAZORPAY_KEY_ID.startswith("rzp_test_") or "YourKey" in self.RAZORPAY_KEY_ID:
            raise RuntimeError(
                "FATAL: Live RAZORPAY_KEY_ID is strictly required in production mode."
            )
        if not self.RAZORPAY_KEY_SECRET or "Your" in self.RAZORPAY_KEY_SECRET:
            raise RuntimeError(
                "FATAL: RAZORPAY_KEY_SECRET is strictly required in production mode."
            )
        if not self.RAZORPAY_WEBHOOK_SECRET or "Your" in self.RAZORPAY_WEBHOOK_SECRET:
            raise RuntimeError(
                "FATAL: RAZORPAY_WEBHOOK_SECRET is strictly required in production mode."
            )

    @classmethod
    def get_cors_origins(cls):
        origins = super().get_cors_origins()
        # Wildcard with credentials is strictly rejected in production
        if "*" in origins:
            origins = [o for o in origins if o != "*"]
        return origins


def get_config(env_name=None):
    """Factory helper returning appropriate config class by environment name."""
    if not env_name:
        env_name = os.getenv("FLASK_ENV", "production").lower()

    if env_name in ("development", "dev"):
        return DevelopmentConfig
    elif env_name in ("test", "testing"):
        return TestingConfig
    else:
        return ProductionConfig
