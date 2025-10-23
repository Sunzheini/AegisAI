"""
InMemoryRateLimiter middleware (local-only)

Purpose
- Provide a minimal, self-contained rate limiter for local development to simulate API
Gateway throttling.
- Uses a fixed 60-second window per identity to cap requests.

Identity key
- If a previous auth layer or dependency sets request.state.user_name, it uses that as
the identity.
- Otherwise it falls back to the client IP address (request.client.host).

Behavior
- Default limit is 60 requests per minute (configurable via requests_per_minute).
- When the limit is exceeded within the current window, returns 429 with a Retry-After header.
- During tests, when app.state.testing is True, the middleware is bypassed to avoid flakiness.

Important notes
- Not production-safe: it stores counters in-process memory, per worker. Prefer API Gateway
usage plans or a
  centralized store (e.g., Redis) for real deployments.
- Stateless deployments with multiple workers will each have independent counters.

Usage
    from routers.rate_limit import InMemoryRateLimiter
    app.add_middleware(InMemoryRateLimiter, requests_per_minute=60)

This module documents the middleware and its trade-offs for the local-first phase
described in WORK_PLAN.md.
"""
import os
import time
from typing import Callable, Dict, Tuple

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from shared_lib.support.constants import RATE_LIMIT_PER_MINUTE


class InMemoryRateLimiter(BaseHTTPMiddleware):
    """A tiny fixed-window rate limiter for local development.

    Limits requests per identity (user name if available via request.state.user_name,
    otherwise client IP). Includes a test bypass when app.state.testing is True.
    """

    def __init__(self, app, requests_per_minute: int = RATE_LIMIT_PER_MINUTE):
        super().__init__(app)
        self.limit = int(requests_per_minute)
        self.window_seconds = RATE_LIMIT_PER_MINUTE
        self._buckets: Dict[str, Tuple[int, int]] = (
            {}
        )  # identity -> (window_start_timestamp, count)

    @staticmethod
    def _get_identity(request: Request) -> str:
        """Get a string identity for rate limiting: user name if available, otherwise client IP."""
        # 1. prefer username if available
        user_name = getattr(request.state, "user_name", None)
        if user_name:
            return f"user:{user_name}"

        # 2. fallback to client IP if no username
        client = request.client.host if request.client else "unknown"
        return f"ip:{client}"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Rate limit requests per identity in a fixed time window."""

        # Bypass rate limiting during tests!!!
        app_state = getattr(request.app, "state", None)
        if getattr(app_state, "testing", False):
            return await call_next(request)

        identity = self._get_identity(request)
        now = int(time.time())
        limit_rate_window_start = now - (now % self.window_seconds)

        bucket = self._buckets.get(identity)
        if not bucket or bucket[0] != limit_rate_window_start:
            # new window
            self._buckets[identity] = (limit_rate_window_start, 1)
        else:
            # same window
            count = bucket[1] + 1
            if count > self.limit:
                retry_after = (bucket[0] + self.window_seconds) - now
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Try again later."},
                    headers={"Retry-After": str(max(1, retry_after))},
                )
            self._buckets[identity] = (bucket[0], count)

        response: Response = await call_next(request)
        return response
