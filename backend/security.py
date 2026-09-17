"""
Security and Cryptographic Utility Module.

Enforces:
1. Standard bcrypt password hashing with automatic per-password salting (cost factor 12).
2. Constant-time password verification preventing timing attacks.
3. Backward compatibility verification for existing legacy hashes.
4. Input sanitization and authentication validation.
"""

import bcrypt
import logging
from werkzeug.security import check_password_hash

logger = logging.getLogger("food_court.security")


def hash_password(password: str) -> str:
    """
    Hashes a plaintext password using bcrypt with a high-work-factor salt.
    Guarantees that plaintext is never stored.
    """
    if not password or not isinstance(password, str):
        raise ValueError("Password must be a non-empty string.")
    
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain password against the stored bcrypt hash.
    Safely rejects empty/invalid inputs.
    Gracefully supports existing Werkzeug hashes during migration.
    """
    if not plain_password or not hashed_password:
        return False

    try:
        # Check if stored hash is a standard bcrypt hash ($2a$, $2b$, or $2y$)
        if hashed_password.startswith(("$2a$", "$2b$", "$2y$")):
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                hashed_password.encode("utf-8")
            )
        
        # Backward-compatibility fallback for pre-migration hashes
        return check_password_hash(hashed_password, plain_password)
    except Exception as e:
        logger.error("Password verification error: %s", type(e).__name__)
        return False
