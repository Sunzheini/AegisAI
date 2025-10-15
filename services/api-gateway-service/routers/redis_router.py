"""
Redis router for health checks and publishing messages.
"""

import os

from fastapi import APIRouter, Depends, HTTPException
from redis.asyncio import Redis
from redis.exceptions import RedisError


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/2")

router = APIRouter(
    prefix="/redis",
    tags=["redis"],
)


async def get_redis():
    """Dependency for Redis client."""
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        await redis.ping()  # Test connection immediately
        yield redis
    except RedisError as e:
        raise HTTPException(
            status_code=503, detail=f"Redis unavailable: {str(e)}"
        ) from e
    finally:
        await redis.aclose()


@router.get("/health")
async def redis_health(redis: Redis = Depends(get_redis)):
    """Redis health check endpoint."""
    try:
        client_info = await redis.client_info()
        redis_info = await redis.info()
        return {
            "status": "healthy",
            "redis": "connected",
            "database": client_info["db"],
            "server_version": redis_info["redis_version"],
        }
    except RedisError as e:
        raise HTTPException(
            status_code=503, detail=f"Redis unavailable: {str(e)}"
        ) from e


@router.post("/publish")
async def publish_message(
    channel: str, message: str, redis: Redis = Depends(get_redis)
):
    """Publish a message to a Redis channel."""
    try:
        if not channel or not message:
            raise HTTPException(
                status_code=400, detail="Channel and message are required"
            )

        subscribers = await redis.publish(channel, message)

        return {
            "status": "published",
            "channel": channel,
            "message": message,
            "subscribers": subscribers,
            "database": 2,
        }

    except RedisError as e:
        raise HTTPException(status_code=500, detail=f"Redis error: {str(e)}") from e
