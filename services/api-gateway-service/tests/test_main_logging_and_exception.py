from unittest.mock import patch, MagicMock
from main import logger


def test_logger_startup(caplog):
    with caplog.at_level("INFO"):
        logger.info("Test startup log")
        assert "Test startup log" in caplog.text


def test_global_exception_handler_logs_and_returns_500():
    with patch.object(logger, "error") as mock_log_error:
        from main import universal_exception_handler
        from fastapi import Request
        import asyncio

        # Create a mock request
        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url = "http://testserver/test"

        test_exception = ValueError("Test error")

        # Use asyncio.run to execute the async function
        response = asyncio.run(universal_exception_handler(mock_request, test_exception))

        assert response.status_code == 500
        # Update this line to match your actual response:
        assert response.body == b'{"error":"Internal server error","detail":"Something went wrong on our end"}'
        assert mock_log_error.called
