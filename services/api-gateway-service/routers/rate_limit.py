import time
from typing import Callable, Dict, Tuple

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class InMemoryRateLimiter(BaseHTTPMiddleware):
    """
    Very simple in-memory fixed window rate limiter for local development.
    Limits requests per identity (user name if authenticated via Authorization header decoded upstream,
    otherwise by client host). Not production-safe; intended for local use only.
    """

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.limit = int(requests_per_minute)
        self.window_seconds = 60
        # key -> (window_start_ts, count)
        self._buckets: Dict[str, Tuple[int, int]] = {}

    async def dispatch(self, request: Request, call_next: Callable):
        # Bypass rate limiting during tests
        try:
            if getattr(getattr(request.app, "state", object()), "testing", False):
                return await call_next(request)
        except Exception:
            pass

        identity = self._get_identity(request)
        now = int(time.time())
        window_start = now - (now % self.window_seconds)

        bucket = self._buckets.get(identity)
        if not bucket or bucket[0] != window_start:
            # new window
            self._buckets[identity] = (window_start, 1)
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

    def _get_identity(self, request: Request) -> str:
        # If upstream auth placed user into request.state.user_name, use that; otherwise fallback to client host
        user_name = getattr(request.state, "user_name", None)
        if user_name:
            return f"user:{user_name}"
        client = request.client.host if request.client else "unknown"
        return f"ip:{client}"
