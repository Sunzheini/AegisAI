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
        logger.info(f"Request received: {request.method} {request.url}")

        try:
            # Process the request
            response = await call_next(request)

            # Calculate process time
            process_time = time.time() - start_time

            # Log when the response is sent
            logger.info(
                f"Response sent: {response.status_code} for {request.method} {request.url} "
                f"(took {process_time:.3f}s)"
            )

            return response

        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"Error processing {request.method} {request.url}: {str(e)} "
                f"(took {process_time:.3f}s)"
            )

            raise  # Re-raise the exception so FastAPI can handle it
