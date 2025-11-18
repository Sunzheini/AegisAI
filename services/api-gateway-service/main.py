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
import os
import logging

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

# Conditional import for shared library usage ----------------------------------------------
USE_SHARED_LIB = os.getenv("USE_SHARED_LIB", False)

if USE_SHARED_LIB:
    from shared_lib.support.constants import LOG_FILE_PATH, APP_NAME
    from shared_lib.custom_middleware.rate_limiting_middleware import InMemoryRateLimiter
    from shared_lib.custom_middleware.error_middleware import ErrorMiddleware
    from shared_lib.custom_middleware.logging_middleware import EnhancedLoggingMiddleware
    from shared_lib.logging_management.logging_manager import LoggingManager
else:
    from support.constants import LOG_FILE_PATH, APP_NAME
    from custom_middleware.rate_limiting_middleware import InMemoryRateLimiter
    from custom_middleware.error_middleware import ErrorMiddleware
    from custom_middleware.logging_middleware import EnhancedLoggingMiddleware
    from logging_management.logging_manager import LoggingManager
# ------------------------------------------------------------------------------------------

from views.ingestion_views import IngestionViewsManager
from routers import auth_router, users_router, v1_router, redis_router
from routers.users_router import get_current_user


USE_AWS = os.getenv("USE_AWS", "false").lower() == "true"
if USE_AWS:
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_REGION = os.getenv("AWS_REGION_NAME", "")


logger = LoggingManager.setup_logging(
    service_name=APP_NAME, log_file_path=LOG_FILE_PATH, log_level=logging.DEBUG
)


# FastAPI app setup
app = FastAPI(title="api-gateway-microservice", version="1.0.0")


# Middleware
app.add_middleware(
    InMemoryRateLimiter, requests_per_minute=60
)  # Local-only rate limiting middleware (fixed window). Bypassed during tests.
app.add_middleware(ErrorMiddleware)
app.add_middleware(EnhancedLoggingMiddleware, service_name=APP_NAME)


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

# If using AWS, create S3 client
if USE_AWS:
    app.state.ingestion_manager.cloud_manager.create_s3_client(
            access_key_id=AWS_ACCESS_KEY_ID,
            secret_access_key=AWS_SECRET_ACCESS_KEY,
            region=AWS_REGION,
        )

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
