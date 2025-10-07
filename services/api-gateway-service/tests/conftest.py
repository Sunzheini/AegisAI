import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from fastapi.testclient import TestClient

from main import app
from models.temp_db import DataBaseManager
from models.models import User
from routers.security import get_password_hash


project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# APP FIXTURES ------------------------------------------------------------------------------------------------
@pytest.fixture
def client():
    """FastAPI test client bound to the application instance."""
    # Indicate testing mode so middleware can relax behaviors (e.g., rate limits)
    app.state.testing = True
    return TestClient(app)


@pytest.fixture
def authenticated_client(client, auth_headers):
    """Test client with authentication headers."""
    client.headers.update(auth_headers)
    return client


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


# REDIS FIXTURES ----------------------------------------------------------------------------------------------
REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/2")


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def redis_client():
    """Redis client connected to database 2."""
    client = Redis.from_url(REDIS_URL, decode_responses=True)

    try:
        await client.ping()
        print(f"✅ Redis test client connected to database 2")
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")

    # Clean test database
    await client.flushdb()

    yield client

    # Cleanup
    await client.flushdb()
    await client.aclose()


@pytest_asyncio.fixture(scope="function")
async def pubsub_client(redis_client):
    """PubSub client for testing."""
    pubsub = redis_client.pubsub()
    yield pubsub
    await pubsub.unsubscribe()
    await pubsub.aclose()
