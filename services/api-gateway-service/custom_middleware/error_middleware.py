"""
Custom error handling middleware for FastAPI apps.
Catches unhandled exceptions, logs them, and returns a consistent JSON error response.
"""

import logging
import traceback
from fastapi import Request, HTTPException, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class ErrorMiddleware(BaseHTTPMiddleware):
    """Middleware to catch unhandled exceptions and return JSON error responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            return await call_next(request)
        except HTTPException as exc:
            # Let FastAPI handle HTTPExceptions as usual
            raise exc
        except Exception as exc:
            logger = logging.getLogger()
            logger.error("Unhandled error: %s", exc, exc_info=True)
            logger.error("Traceback: %s", traceback.format_exc())
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "detail": "Something went wrong on our end",
                },
            )
