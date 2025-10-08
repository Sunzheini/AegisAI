import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from fastapi.testclient import TestClient

from main import app


project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# APP FIXTURES ------------------------------------------------------------------------------------------------
@pytest.fixture
def client():
    """FastAPI test client bound to the application instance."""
    app.state.testing = True
    return TestClient(app)


@pytest.fixture
def authenticated_client(client, auth_headers):
    """Test client with authentication headers."""
    client.headers.update(auth_headers)
    return client


@pytest.fixture
def auth_headers(auth_token):
    """Authorization header for authenticated requests."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def auth_token():
    """Returns a dummy authentication token for testing purposes."""
    return "dummy-token"


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
