from fastapi import FastAPI

from routers import auth, users, v1
from routers.rate_limit import InMemoryRateLimiter
from views.ingestion_views import IngestionViewsManager
from routers.users import get_current_user
from routers import redis_router


app = FastAPI(title="api-gateway-microservice", version="1.0.0")

# Local-only rate limiting middleware (fixed window). Bypassed during tests.
app.add_middleware(InMemoryRateLimiter, requests_per_minute=60)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(v1.router)
app.include_router(redis_router.router)

# Register ingestion manager and expose for tests! app.state is a dynamic attribute (using Starlette’s State object)!
app.state.ingestion_manager = IngestionViewsManager(v1.router, get_current_user)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
