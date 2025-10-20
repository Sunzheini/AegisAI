# """
# Middleware for logging request and response details in FastAPI.
# """
# import time
# import uuid
# import logging
# from typing import Callable
#
# from fastapi import Request, Response
# from starlette.middleware.base import BaseHTTPMiddleware
# from user_agents import parse
#
# from support.constants import APP_NAME
#
#
# logger = logging.getLogger(APP_NAME)
#
#
# class CustomLogger(BaseHTTPMiddleware):
#     """Middleware for logging when each request is received and when the response is sent."""
#
#     async def dispatch(self, request: Request, call_next: Callable) -> Response:
#         # Generate request ID for tracing
#         request_id = str(uuid.uuid4())[:8]
#         request.state.request_id = request_id
#
#         start_time = time.time()
#
#         # Collect request details
#         client_ip = request.client.host if request.client else "unknown"
#         user_agent = request.headers.get("user-agent", "")
#         user_agent_parsed = parse(user_agent)
#
#         # Log request with structured data
#         request_log = {
#             "request_id": request_id,
#             "method": request.method,
#             "url": str(request.url),
#             "client_ip": client_ip,
#             "user_agent": user_agent_parsed.browser.family if user_agent_parsed else "unknown",
#             "user_agent_os": user_agent_parsed.os.family if user_agent_parsed else "unknown",
#             "headers": dict(request.headers),
#         }
#
#         # Remove sensitive headers from logs
#         sensitive_headers = {'authorization', 'cookie', 'proxy-authorization'}
#         for header in sensitive_headers:
#             request_log["headers"].pop(header, None)
#
#         logger.info("Request received", extra={"request_data": request_log})
#
#         try:
#             # Process the request
#             response = await call_next(request)
#             process_time = time.time() - start_time
#
#             # Log response
#             response_log = {
#                 "request_id": request_id,
#                 "status_code": response.status_code,
#                 "process_time": round(process_time, 3),
#                 "response_headers": dict(response.headers),
#             }
#
#             log_level = logging.INFO if response.status_code < 400 else logging.WARNING
#             logger.log(log_level, "Response sent", extra={"response_data": response_log})
#
#             # Add request ID to response headers for client tracing
#             response.headers["X-Request-ID"] = request_id
#             response.headers["X-Process-Time"] = f"{process_time:.3f}"
#
#             return response
#
#         except Exception as e:
#             process_time = time.time() - start_time
#             error_log = {
#                 "request_id": request_id,
#                 "method": request.method,
#                 "url": str(request.url),
#                 "error_type": type(e).__name__,
#                 "error_message": str(e),
#                 "process_time": round(process_time, 3),
#             }
#
#             logger.error(
#                 "Error processing request",
#                 extra={"error_data": error_log},
#                 exc_info=True  # Include stack trace
#             )
#             raise
#
#
# class SlowRequestFilter(logging.Filter):
#     """Filter to highlight slow requests."""
#
#     def __init__(self, slow_threshold: float = 5.0):
#         super().__init__()
#         self.slow_threshold = slow_threshold
#
#     def filter(self, record):
#         if hasattr(record, 'response_data'):
#             process_time = record.response_data.get('process_time', 0)
#             if process_time > self.slow_threshold:
#                 record.msg = f"SLOW REQUEST: {record.msg} (took {process_time}s)"
#         return True


"""
Reusable logging middleware for all FastAPI services.
"""
import time
import logging
from typing import Callable, Dict, Any
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from user_agents import parse


class EnhancedLoggingMiddleware(BaseHTTPMiddleware):
    """Enhanced middleware for structured request/response logging."""

    def __init__(self, app, service_name: str, enable_user_agent: bool = True):
        super().__init__(app)
        self.service_name = service_name
        self.enable_user_agent = enable_user_agent
        self.logger = logging.getLogger(service_name)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID for tracing
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        start_time = time.time()

        # Collect request details
        client_ip = request.client.host if request.client else "unknown"

        request_log = {
            "request_id": request_id,
            "service": self.service_name,
            "method": request.method,
            "url": str(request.url),
            "client_ip": client_ip,
        }

        # Add user agent if enabled
        if self.enable_user_agent:
            user_agent = request.headers.get("user-agent", "")
            user_agent_parsed = parse(user_agent)
            request_log.update({
                "user_agent": user_agent_parsed.browser.family if user_agent_parsed else "unknown",
                "user_agent_os": user_agent_parsed.os.family if user_agent_parsed else "unknown",
            })

        # Log sensitive headers safely
        headers = dict(request.headers)
        sensitive_headers = {'authorization', 'cookie', 'proxy-authorization'}
        for header in sensitive_headers:
            headers.pop(header, None)
        request_log["headers"] = headers

        self.logger.info("Request received", extra={"request_data": request_log})

        try:
            # Process the request
            response = await call_next(request)
            process_time = time.time() - start_time

            # Log response
            response_log = {
                "request_id": request_id,
                "service": self.service_name,
                "status_code": response.status_code,
                "process_time": round(process_time, 3),
            }

            log_level = logging.INFO if response.status_code < 400 else logging.WARNING
            logger_method = self.logger.info if response.status_code < 400 else self.logger.warning
            logger_method("Response sent", extra={"response_data": response_log})

            # Add request ID to response headers for client tracing
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.3f}"
            response.headers["X-Service"] = self.service_name

            return response

        except Exception as e:
            process_time = time.time() - start_time
            error_log = {
                "request_id": request_id,
                "service": self.service_name,
                "method": request.method,
                "url": str(request.url),
                "error_type": type(e).__name__,
                "error_message": str(e),
                "process_time": round(process_time, 3),
            }

            self.logger.error(
                "Error processing request",
                extra={"error_data": error_log},
                exc_info=True
            )
            raise
