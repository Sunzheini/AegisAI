import os
import logging

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from main import app, logger

load_dotenv()

# Conditional import for shared library usage ----------------------------------------------
USE_SHARED_LIB = os.getenv("USE_SHARED_LIB", False)
if USE_SHARED_LIB:
    from shared_lib.support.constants import APP_NAME
else:
    from support.constants import APP_NAME
# ------------------------------------------------------------------------------------------


client = TestClient(app)


def test_logger_startup(caplog):
    """Test that logger is properly configured and can log messages."""
    with caplog.at_level("INFO", logger=APP_NAME):
        logger.info("Test startup log")

        # Check that our message was logged
        assert any("Test startup log" in record.message for record in caplog.records)
        # Check that it came from our logger
        assert any(record.name == APP_NAME for record in caplog.records)


def test_error_middleware_logs_and_returns_500(caplog):
    """Test that error middleware properly logs errors and returns 500."""
    # Capture logs from both our app logger and root logger (since error middleware uses root)
    with caplog.at_level("ERROR"):
        response = client.get("/raise-error")

        assert response.status_code == 500
        assert response.json() == {
            "error": "Internal server error",
            "detail": "Something went wrong on our end",
        }

        # Check that the error was logged (could be by root logger or our app logger)
        error_logs = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_logs) > 0

        # Check that our intentional error message is in the logs
        error_messages = [r.getMessage() for r in error_logs]
        assert any(
            "Intentional error for testing error middleware" in msg
            for msg in error_messages
        )


def test_logging_middleware_adds_request_id():
    """Test that logging middleware adds request ID to responses."""
    response = client.get("/health")

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert "X-Process-Time" in response.headers
    assert "X-Service" in response.headers
    assert response.headers["X-Service"] == APP_NAME

    # Request ID should be a non-empty string
    request_id = response.headers["X-Request-ID"]
    assert len(request_id) > 0


def test_logging_middleware_logs_requests(caplog):
    """Test that requests and responses are properly logged."""
    with caplog.at_level("INFO", logger=APP_NAME):
        response = client.get("/health")

        assert response.status_code == 200

        # Check that request was logged by our app logger
        request_logs = [
            r
            for r in caplog.records
            if "request received" in r.getMessage().lower() and r.name == APP_NAME
        ]
        assert len(request_logs) > 0

        # Check that response was logged by our app logger
        response_logs = [
            r
            for r in caplog.records
            if "response sent" in r.getMessage().lower() and r.name == APP_NAME
        ]
        assert len(response_logs) > 0


def test_logging_middleware_handles_errors(caplog):
    """Test that errors are properly logged with stack traces."""
    # Capture all error logs (including from root logger)
    with caplog.at_level("ERROR"):
        response = client.get("/raise-error")

        assert response.status_code == 500

        # Check that error was logged
        error_logs = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_logs) > 0

        # Check that the traceback was logged
        error_messages = [r.getMessage() for r in error_logs]
        traceback_logged = any("Traceback" in msg for msg in error_messages)
        assert traceback_logged, "Expected traceback in error logs"


@pytest.mark.parametrize(
    "endpoint,expected_status",
    [
        ("/health", 200),
        ("/nonexistent", 404),
    ],
)
def test_logging_middleware_different_status_codes(endpoint, expected_status, caplog):
    """Test logging with different HTTP status codes."""
    with caplog.at_level("INFO", logger=APP_NAME):
        response = client.get(endpoint)

        assert response.status_code == expected_status

        # For 404, check that it was logged as warning by our app logger
        if expected_status == 404:
            warning_logs = [
                r
                for r in caplog.records
                if r.levelno == logging.WARNING and r.name == APP_NAME
            ]
            assert len(warning_logs) > 0
        else:
            info_logs = [
                r
                for r in caplog.records
                if r.levelno == logging.INFO and r.name == APP_NAME
            ]
            assert len(info_logs) > 0


def test_logging_middleware_sensitive_headers(caplog):
    """Test that sensitive headers are not logged."""
    with caplog.at_level("INFO", logger=APP_NAME):
        # Make request with sensitive headers
        client.get(
            "/health",
            headers={
                "Authorization": "Bearer secret-token",
                "Cookie": "session=abc123",
                "User-Agent": "Test-Agent",
            },
        )

        # Check that request was logged by our app logger
        request_logs = [
            r
            for r in caplog.records
            if "request received" in r.getMessage().lower() and r.name == APP_NAME
        ]
        assert len(request_logs) > 0

        # Check the log record for structured data
        for record in request_logs:
            if hasattr(record, "request_data"):
                headers = record.request_data.get("headers", {})
                # Sensitive headers should be filtered out
                assert "authorization" not in headers
                assert "cookie" not in headers
                # Non-sensitive headers should be present
                assert "user-agent" in headers
                assert headers["user-agent"] == "Test-Agent"
                break
