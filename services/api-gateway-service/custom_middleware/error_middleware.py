"""
Custom error handling middleware for FastAPI apps.
Catches unhandled exceptions, logs them, and returns a consistent JSON error response.
"""
import logging
import traceback
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from support.constants import APP_NAME


logger = logging.getLogger(APP_NAME)


class ErrorMiddleware(BaseHTTPMiddleware):
    """Middleware to catch unhandled exceptions and return 500 JSON response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Catch exceptions and return JSON error response."""
        try:
            return await call_next(request)
        except Exception as e:
            # Log the error with traceback using your app logger
            logger.error("Unhandled error: %s", str(e))
            logger.error("Traceback: %s", traceback.format_exc())

            # Return JSON error response
            return Response(
                content='{"error": "Internal server error", "detail": "Something went wrong on our end"}',
                status_code=500,
                media_type="application/json",
            )
