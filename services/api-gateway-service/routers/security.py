import hashlib
import secrets


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
