from unittest.mock import patch
from main import app, logger
from fastapi.testclient import TestClient

client = TestClient(app)


def test_logger_startup(caplog):
    with caplog.at_level("INFO"):
        logger.info("Test startup log")
        assert "Test startup log" in caplog.text


def test_error_middleware_logs_and_returns_500():
    with patch.object(logger, "error") as mock_log_error:
        response = client.get("/raise-error")
        assert response.status_code == 500
        assert response.json() == {
            "error": "Internal server error",
            "detail": "Something went wrong on our end",
        }
        assert mock_log_error.called
