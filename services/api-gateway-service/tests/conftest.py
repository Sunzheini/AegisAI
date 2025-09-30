import pytest
from fastapi.testclient import TestClient

from main import app
from models.temp_db import DataBaseManager
from models.models import User
from routers.security import get_password_hash


# Shared pytest fixtures for the test suite
# These consolidate common setup used by multiple test modules.


@pytest.fixture
def client():
    """FastAPI test client bound to the application instance."""
    # Indicate testing mode so middleware can relax behaviors (e.g., rate limits)
    app.state.testing = True
    return TestClient(app)


@pytest.fixture
def database():
    """Reset the in-memory database and return the users list reference."""
    DataBaseManager._initialized = False
    db = DataBaseManager()
    return db.users_db


@pytest.fixture
def auth_token(client, database):
    """Create a known test user with a known password and obtain a JWT token."""
    # Ensure clean DB and add a known user with a known password
    database.clear()

    test_user = User(
        id=1,
        name="testuser",
        age=30,
        city="Boston",
        email="test@example.com",
        password_hash=get_password_hash("testpass123"),
    )
    database.append(test_user)

    resp = client.post("/auth/login", data={"username": "testuser", "password": "testpass123"})
    assert resp.status_code == 200, f"Login failed: {resp.json()}"
    return resp.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    """Authorization header for authenticated requests."""
    return {"Authorization": f"Bearer {auth_token}"}
