"""Security utilities for password hashing and authentication."""

import hashlib
import secrets
from functools import wraps

from fastapi import HTTPException


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash using SHA256"""
    if not hashed_password or len(hashed_password) < 32:
        return False

    # Split the stored hash into salt and hash
    salt = hashed_password[:32]
    stored_hash = hashed_password[32:]

    # Hash the provided password with the same salt
    new_hash = hashlib.sha256((salt + plain_password).encode()).hexdigest()

    return secrets.compare_digest(new_hash, stored_hash)


def get_password_hash(password: str) -> str:
    """Hash a password for storing using SHA256 with salt"""
    # Generate a random salt
    salt = secrets.token_hex(16)

    # Hash password with salt
    password_hash = hashlib.sha256((salt + password).encode()).hexdigest()

    # Return salt + hash for storage
    return salt + password_hash


def auth_required(func):
    """Decorator to ensure the user is authenticated before accessing the endpoint."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        current_user = kwargs.get("current_user")
        if current_user is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return await func(*args, **kwargs)

    return wrapper
