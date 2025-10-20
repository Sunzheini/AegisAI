import logging
import os
import sys
import time
from pathlib import Path
import uuid
import glob

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from fastapi.testclient import TestClient

from main import app
from db_management.db_manager import DataBaseManager
from models.models import User
from support.security import get_password_hash
from support.constants import LOG_FILE_PATH, APP_NAME

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
    """Reset the database manager and return the DataBaseManager instance."""
    DataBaseManager._initialized = False
    db = DataBaseManager()
    return db


@pytest.fixture
def auth_token(client, database):
    """Create a unique test user with a known password and obtain a JWT token."""
    unique_str = str(uuid.uuid4())[:8]
    test_user = User(
        name=f"testuser_{unique_str}",
        age=30,
        city="Boston",
        email=f"testuser_{unique_str}@example.com",
        password_hash=get_password_hash("testpassword"),
    )
    created_user = database.create_user(test_user)

    resp = client.post(
        "/auth/login", data={"username": created_user.name, "password": "testpassword"}
    )
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


# Logging ----------------------------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def setup_test_logging():
    """Setup test logging configuration for all tests."""
    # Clear existing handlers
    logging.getLogger().handlers.clear()

    # Setup basic console logging for tests
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)

    # Reduce third-party logging noise
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


@pytest.fixture
def caplog(caplog):
    """Enhanced caplog fixture that works with our structured logging."""
    # Set level for our app logger
    caplog.set_level(logging.DEBUG, logger=APP_NAME)
    return caplog


def get_all_log_files():
    """Get all log files from the project and subdirectories."""
    log_files = []

    # Common log file patterns
    log_patterns = [
        "*.log",
        "logs/*.log",
        "**/*.log",
        "*.txt",
        "logs/*.txt",
        "**/logs/*.log",
        "**/logs/*.txt",
    ]

    # Search for log files in project root and subdirectories
    project_root = Path(__file__).parent.parent

    for pattern in log_patterns:
        found_files = glob.glob(str(project_root / pattern), recursive=True)
        log_files.extend(found_files)

    # Also include the main log file path if it exists
    if os.path.exists(LOG_FILE_PATH):
        log_files.append(LOG_FILE_PATH)

    # Remove duplicates and return
    return list(set(log_files))


def delete_log_files():
    """Delete all log files with retry logic."""
    log_files = get_all_log_files()

    for log_file in log_files:
        if os.path.exists(log_file):
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    os.remove(log_file)
                    print(f"Deleted log file: {log_file}")
                    break
                except PermissionError:
                    if attempt < max_retries - 1:
                        time.sleep(0.5)
                    else:
                        # Try to just clear the content instead
                        try:
                            with open(log_file, "w") as f:
                                f.write("")
                            print(f"Cleared content of locked log file: {log_file}")
                        except Exception as e:
                            print(f"Could not clear log file {log_file}: {e}")


def clear_log_file_content():
    """Clear content of all log files without deleting them."""
    log_files = get_all_log_files()

    for log_file in log_files:
        if os.path.exists(log_file):
            try:
                with open(log_file, "w") as f:
                    f.write("")
                print(f"Cleared log file: {log_file}")
            except Exception as e:
                print(f"Could not clear log file {log_file}: {e}")


def close_all_log_handlers():
    """Close all logging handlers to release file handles."""
    # Close handlers for all loggers
    for logger_name in logging.Logger.manager.loggerDict:
        logger = logging.getLogger(logger_name)
        for handler in logger.handlers[:]:
            if hasattr(handler, "close"):
                handler.close()
            logger.removeHandler(handler)

    # Also close root logger handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        if hasattr(handler, "close"):
            handler.close()
        root_logger.removeHandler(handler)


@pytest.fixture(scope="function", autouse=True)
def cleanup_logs_before_test():
    """Clear log files before each test to ensure clean state."""
    close_all_log_handlers()
    clear_log_file_content()
    yield


@pytest.fixture(scope="session", autouse=True)
def cleanup_all_log_files_after_tests():
    """
    Automatically delete all log files after all tests are completed.
    This runs once at the end of the entire test session.
    """
    yield

    # Final cleanup after all tests
    close_all_log_handlers()
    delete_log_files()


# Service-specific test clients -------------------------------------------------------------------------------
@pytest.fixture
def orchestrator_client():
    """Test client for workflow orchestrator service."""
    try:
        from workflow_orchestrator_example import app as orchestrator_app
        orchestrator_app.state.testing = True
        return TestClient(orchestrator_app)
    except ImportError:
        pytest.skip("Workflow orchestrator service not available")


@pytest.fixture
def validation_client():
    """Test client for validation service."""
    try:
        from validation_service_example import app as validation_app
        validation_app.state.testing = True
        return TestClient(validation_app)
    except ImportError:
        pytest.skip("Validation service not available")
