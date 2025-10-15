"""
API Gateway Microservice
-----------------------
Entry point for the API Gateway & Ingestion Service. Sets up FastAPI app, routers, and middleware.

Routers:
    - auth: Authentication endpoints
    - users: User management endpoints
    - v1: Versioned API endpoints (including ingestion)
    - redis_router: Redis health and pub/sub endpoints

Middleware:
    - InMemoryRateLimiter: Local rate limiting (bypassed during tests)

App State:
    - ingestion_manager: Instance of IngestionViewsManager for job and asset management

Health Endpoint:
    - GET /health: Returns service status
"""
import logging
from fastapi import FastAPI

from custom_middleware.logging_middleware import CustomLogger
from custom_middleware.rate_limiting_middleware import InMemoryRateLimiter
from custom_middleware.error_middleware import ErrorMiddleware
from support.constants import LOG_FILE_PATH, APP_NAME
from views.ingestion_views import IngestionViewsManager
from routers import auth_router, users_router, v1_router, redis_router
from routers.users_router import get_current_user


# Logger setup
logging.getLogger().handlers.clear()
logging.basicConfig(
    filename=LOG_FILE_PATH,
    filemode="a",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.DEBUG,
    force=True,
)
logger = logging.getLogger(APP_NAME)
logger.info("Starting API Gateway Microservice...")


# FastAPI app setup
app = FastAPI(title="api-gateway-microservice", version="1.0.0")


# Middleware
app.add_middleware(
    InMemoryRateLimiter, requests_per_minute=60
)  # Local-only rate limiting middleware (fixed window). Bypassed during tests.
app.add_middleware(CustomLogger)
app.add_middleware(ErrorMiddleware)


# Include routers
app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(v1_router.router)
app.include_router(redis_router.router)


"""
Register ingestion manager and expose for tests! app.state is a dynamic attribute 
(using Starlette’s State object)!
"""
app.state.ingestion_manager = IngestionViewsManager(v1_router.router, get_current_user)


# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Health check endpoint for API Gateway service.

    Returns:
        dict: Service status
    """
    return {"status": "ok"}


@app.get("/raise-error")
async def raise_error():
    """Endpoint to intentionally raise an error for testing error middleware (needed in tests)."""
    raise RuntimeError("Intentional error for testing error middleware")
