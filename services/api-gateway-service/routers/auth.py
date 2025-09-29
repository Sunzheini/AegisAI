import os
from datetime import timedelta, datetime, timezone
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import jwt, JWTError

from models.temp_db import DataBaseManager
from routers.security import verify_password, get_password_hash

"""
THe flow is as follows:
1. User sends a POST request to /auth/login with username and password.
2. The server verifies the credentials and, if valid, generates a JWT token.
3. The server responds with the JWT token.
4. For protected routes, the client (frontend) includes the JWT token in the 
Authorization header of subsequent requests in the format "Bearer <token>".
5. When a request is made to a protected route, the server extracts the token
from the Authorization header and verifies it (uses the get_current_user dependency).
6. If the token is valid, the server processes the request; otherwise, it
responds with an appropriate error (e.g., 401 Unauthorized).
"""


router = APIRouter(
    prefix='/auth',
    tags=['auth'],
)

# ✅ Get secret key from environment variables (secure)
SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret-for-development-only")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")  # for token authentication


async def get_current_user(
        token: str = Depends(oauth2_scheme      # automatically extracts the token from the request
    )):
    """
    Dependency to get the current authenticated user from the JWT token
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    db = DataBaseManager()
    user = db.get_user_by_username(username)
    if user is None:
        raise credentials_exception

    return user


@router.post("/login")
async def authenticate_user_and_return_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticate user and return JWT token

    Uses standard OAuth2 form format:
    - username: the user identifier
    - password: the user password (if applicable)
    """
    db = DataBaseManager()

    # user must be fetched from the database
    user = db.get_user_by_username(form_data.username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not hasattr(user, 'password_hash') or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        username=user.name,
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


def create_access_token(username: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token

    Args:
        username: The subject of the token
        expires_delta: Optional timedelta for token expiration

    Returns:
        Encoded JWT token
    """
    to_encode: Dict[str, Any] = {"sub": username}

    if expires_delta:
        expires = datetime.now(timezone.utc) + expires_delta
    else:
        expires = datetime.now(timezone.utc) + timedelta(minutes=60)

    to_encode.update({"exp": expires})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# Utility endpoint to create hashed passwords (for initial user setup)
@router.post("/hash-password")
async def hash_password(password: str):
    """
    Utility endpoint to generate hashed passwords for initial user setup
    Use this to create the hashed passwords for test users
    """
    return {"hashed_password": get_password_hash(password)}


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(
        name: str,
        email: str,
        password: str,
        age: int,
        city: str
):
    """
    Register a new user with hashed password
    """
    db = DataBaseManager()

    # Check if user already exists
    existing_user = db.get_user_by_username(name)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )

    # Create new user with hashed password
    hashed_password = get_password_hash(password)

    # This assumes you can create users with a password_hash field
    new_user = {
        "name": name,
        "email": email,
        "age": age,
        "city": city,
        "password_hash": hashed_password
    }

    created_user = db.create_user_with_password(new_user)

    return {
        "message": "User created successfully",
        "username": name,
        "email": email
    }


# not used currently, but could be useful for debugging or token validation
@router.get("/verify-token")
async def verify_token(token: str):
    """
    Verify if a JWT token is valid, e.g. eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9, which is received by login
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
        return {"username": username, "valid": True}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
