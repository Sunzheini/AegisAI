import os
import typing as t

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

load_dotenv()

# Conditional import for shared library usage ----------------------------------------------
USE_SHARED_LIB = os.getenv("USE_SHARED_LIB", False)
if USE_SHARED_LIB:
    from shared_lib.custom_middleware.rate_limiting_middleware import (
        InMemoryRateLimiter,
    )
else:
    from custom_middleware.rate_limiting_middleware import InMemoryRateLimiter
# ------------------------------------------------------------------------------------------


class SetUserNameMiddleware(BaseHTTPMiddleware):
    """Test-only middleware to set request.state.user_name from header X-User.

    We add this middleware OUTERMOST (after adding the rate limiter), so it executes
    first and the rate limiter can read request.state.user_name for identity.
    """

    async def dispatch(self, request: Request, call_next):
        request.state.user_name = request.headers.get("X-User")
        return await call_next(request)


def make_test_app(
    limit: int = 3, testing: bool = False, set_user_mw: bool = False
) -> FastAPI:
    app = FastAPI()

    # Core route to exercise the limiter
    @app.get("/ping")
    async def ping():
        return {"ok": True}

    # Add the rate limiter (inner middleware)
    app.add_middleware(InMemoryRateLimiter, requests_per_minute=limit)

    # Optionally add a middleware that sets request.state.user_name (outermost)
    if set_user_mw:
        app.add_middleware(SetUserNameMiddleware)

    # Control testing bypass flag
    app.state.testing = testing
    return app


def request_many(client: TestClient, n: int, headers: t.Optional[dict] = None):
    last = None
    for _ in range(n):
        last = client.get("/ping", headers=headers or {})
    return last


def test_exceed_limit_returns_429(monkeypatch):
    """When exceeding the fixed-window limit, the middleware should return 429 with Retry-After."""
    app = make_test_app(limit=3, testing=False)

    # Freeze time at a fixed base so all calls are in the same window
    import custom_middleware.rate_limiting_middleware as rl

    base = 1_700_000_000
    monkeypatch.setattr(rl.time, "time", lambda: base)

    with TestClient(app) as client:
        # First three requests should pass
        for i in range(3):
            r = client.get("/ping")
            assert r.status_code == 200
            assert r.json() == {"ok": True}

        # The 4th should be throttled
        r = client.get("/ping")
        assert r.status_code == 429
        assert r.headers.get("Retry-After") is not None
        assert "Rate limit exceeded" in r.json()["detail"]

        # Move to the next window and verify it resets
        monkeypatch.setattr(rl.time, "time", lambda: base + 61)
        r2 = client.get("/ping")
        assert r2.status_code == 200


def test_bypass_when_testing_flag_set():
    """When app.state.testing is True, limiter must be bypassed entirely."""
    app = make_test_app(limit=1, testing=True)
    with TestClient(app) as client:
        # Even with limit=1, multiple requests should succeed under testing bypass
        for _ in range(10):
            r = client.get("/ping")
            assert r.status_code == 200


def test_identity_uses_user_name_over_ip(monkeypatch):
    """Limiter keys by request.state.user_name when present, otherwise IP.

    We set a very small limit (2 req/min) and verify that two different users
    do not affect each other's counters, even from the same IP.
    """
    app = make_test_app(limit=2, testing=False, set_user_mw=True)

    # Keep all calls in the same window
    import custom_middleware.rate_limiting_middleware as rl

    base = 1_700_000_000
    monkeypatch.setattr(rl.time, "time", lambda: base)

    with TestClient(app) as client:
        # User A hits the limit (2 ok, 3rd throttled)
        hdr_a = {"X-User": "alice"}
        assert client.get("/ping", headers=hdr_a).status_code == 200
        assert client.get("/ping", headers=hdr_a).status_code == 200
        r_third_a = client.get("/ping", headers=hdr_a)
        assert r_third_a.status_code == 429

        # User B should have a fresh bucket and succeed twice
        hdr_b = {"X-User": "bob"}
        assert client.get("/ping", headers=hdr_b).status_code == 200
        assert client.get("/ping", headers=hdr_b).status_code == 200

        # Without X-User header, identity falls back to IP and will share the IP bucket
        # Make sure it can still serve within limits after switching to a new window
        monkeypatch.setattr(rl.time, "time", lambda: base + 61)
        assert client.get("/ping").status_code == 200
        assert client.get("/ping").status_code == 200
        assert client.get("/ping").status_code == 429
