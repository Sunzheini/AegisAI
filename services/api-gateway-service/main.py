from fastapi import FastAPI

from routers import auth, users, v1
from routers.rate_limit import InMemoryRateLimiter


app = FastAPI(title="api-gateway-microservice", version="1.0.0")

# Local-only rate limiting middleware (fixed window). Bypassed during tests.
app.add_middleware(InMemoryRateLimiter, requests_per_minute=60)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(v1.router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
