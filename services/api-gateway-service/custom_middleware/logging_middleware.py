"""
Middleware for logging request and response details in FastAPI.
"""

import time
import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from support.constants import APP_NAME


logger = logging.getLogger(APP_NAME)


class CustomLogger(BaseHTTPMiddleware):
    """Middleware for logging when each request is received and when the response is sent."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request and response details."""
        start_time = time.time()

        # Log when the request is received
        logger.info("Request received: %s %s", request.method, request.url)

        try:
            # Process the request
            response = await call_next(request)

            # Calculate process time
            process_time = time.time() - start_time

            # Log when the response is sent
            logger.info(
                "Response sent: %d for %s %s (took %.3fs)",
                response.status_code,
                request.method,
                request.url,
                process_time,
            )

            return response

        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                "Error processing %s %s: %s (took %.3fs)",
                request.method,
                request.url,
                str(e),
                process_time,
            )

            raise  # Re-raise the exception so FastAPI can handle it
