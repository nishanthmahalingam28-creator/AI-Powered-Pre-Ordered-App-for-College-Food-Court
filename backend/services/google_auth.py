"""
Authoritative Server-Side Google Identity Services (GIS) Verification Service.

Responsible for:
1. Validating and cryptographically verifying Google ID tokens server-side.
2. Enforcing audience ('aud'), issuer ('iss'), expiration ('exp'), and email_verified flags.
3. Exposing public client configuration without leaking secrets.
"""

import os
import logging
from typing import Optional, Dict, Any

try:
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests
    GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    GOOGLE_AUTH_AVAILABLE = False

import requests

logger = logging.getLogger("food_court.google_auth")


class GoogleAuthError(Exception):
    """Base exception for Google authentication failures."""
    pass


class GoogleTokenVerificationError(GoogleAuthError):
    """Raised when Google ID token fails cryptographic verification."""
    pass


class GoogleAuthService:
    @staticmethod
    def get_client_id() -> str:
        """Returns the configured Google Client ID from environment."""
        return os.getenv("GOOGLE_CLIENT_ID", "").strip()

    @classmethod
    def get_public_config(cls) -> Dict[str, Any]:
        """
        Public configuration safe for frontend delivery.
        NEVER includes client secret.
        """
        client_id = cls.get_client_id()
        is_dev = os.getenv("FLASK_ENV", "production").lower() in ("development", "dev", "test", "testing")
        return {
            "success": True,
            "client_id": client_id,
            "enabled": bool(client_id) or is_dev,
            "environment": "development" if is_dev else "production"
        }

    @classmethod
    def verify_token(cls, token: str) -> Dict[str, Any]:
        """
        Authoritatively verifies Google ID token server-side.

        Validations:
        - Non-empty token string.
        - Cryptographic signature verified against Google's public keys.
        - Issuer ('iss') is accounts.google.com or https://accounts.google.com.
        - Audience ('aud') matches configured GOOGLE_CLIENT_ID (if configured).
        - Token is not expired ('exp').
        - User email is present and email_verified is True.

        Returns:
            Dict containing verified user claims:
            {
                'sub': str,
                'email': str,
                'name': str,
                'picture': Optional[str],
                'email_verified': bool
            }
        """
        if not token or not isinstance(token, str) or not token.strip():
            raise GoogleTokenVerificationError("Google ID token is required and cannot be empty.")

        token = token.strip()
        client_id = cls.get_client_id()
        verified_claims: Optional[Dict[str, Any]] = None

        # 1. Primary: Use google.oauth2.id_token if available
        if GOOGLE_AUTH_AVAILABLE:
            try:
                req = google_requests.Request()
                # If client_id is configured, verify_oauth2_token validates audience
                verified_claims = id_token.verify_oauth2_token(
                    token,
                    req,
                    audience=client_id if client_id else None
                )
            except Exception as e:
                logger.warning("google.oauth2 token verification failed: %s. Attempting tokeninfo fallback.", e)

        # 2. Secondary fallback: Query Google's authoritative tokeninfo endpoint
        if not verified_claims:
            try:
                resp = requests.get(
                    "https://oauth2.googleapis.com/tokeninfo",
                    params={"id_token": token},
                    timeout=5
                )
                if resp.status_code == 200:
                    data = resp.json()
                    # Check for Google error response in JSON
                    if "error" not in data:
                        verified_claims = data
                else:
                    logger.warning("Google tokeninfo returned HTTP %s", resp.status_code)
            except Exception as net_err:
                logger.error("Network error connecting to Google tokeninfo: %s", net_err)

        if not verified_claims:
            raise GoogleTokenVerificationError("Google authentication failed: Invalid, expired, or tampered token.")

        # 3. Explicit Claim Enforcement
        # Issuer verification
        issuer = verified_claims.get("iss", "")
        if issuer not in ("accounts.google.com", "https://accounts.google.com"):
            raise GoogleTokenVerificationError(f"Untrusted token issuer: '{issuer}'")

        # Audience verification (if client_id is set)
        if client_id:
            aud = verified_claims.get("aud")
            if aud != client_id:
                raise GoogleTokenVerificationError("Google token was not issued for this application (audience mismatch).")

        # Email & verification checks
        email = (verified_claims.get("email") or "").strip().lower()
        if not email:
            raise GoogleTokenVerificationError("Google token does not contain a valid email address.")

        email_verified = verified_claims.get("email_verified")
        # In tokeninfo, email_verified can be boolean or string 'true'
        is_verified = (email_verified is True) or (str(email_verified).lower() == "true")
        if not is_verified:
            raise GoogleTokenVerificationError("Google account email is not verified by Google.")

        sub = str(verified_claims.get("sub", "")).strip()
        if not sub:
            raise GoogleTokenVerificationError("Google token missing unique subject identifier ('sub').")

        name = (
            verified_claims.get("name")
            or verified_claims.get("given_name")
            or email.split("@")[0]
        )

        return {
            "sub": sub,
            "email": email,
            "name": name,
            "picture": verified_claims.get("picture"),
            "email_verified": True
        }
