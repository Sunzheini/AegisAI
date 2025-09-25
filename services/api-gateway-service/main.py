from fastapi import FastAPI

from routers import auth, users


app = FastAPI(title="api-gateway-microservice", version="1.0.0")
app.include_router(auth.router)
app.include_router(users.router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
