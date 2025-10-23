"""
Contains the RedisManager class responsible for managing Redis interactions.
"""

import os
import json
from typing import Optional

import redis.asyncio as aioredis

# try:
#     from ..contracts.job_schemas import IngestionJobRequest, WorkflowGraphState
# except:
#     from contracts.job_schemas import IngestionJobRequest, WorkflowGraphState

from contracts.job_schemas import IngestionJobRequest, WorkflowGraphState


class RedisManager:
    """Manages Redis interactions for publishing job events."""

    def __init__(self):
        self.redis_url = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/2")
        self._redis_client = None  # For connection pooling in orchestrator

    # ---------------------------------------------------------------------------------
    # For API Gateway (one-off publishing)
    # ---------------------------------------------------------------------------------
    async def publish_message_to_redis(
        self, job_id: str, job_record: dict, file, current_user
    ):
        """
        Publishes a JOB_CREATED event to Redis for the given job (one-off publishing).
        :param job_id: The unique identifier for the job.
        :param job_record: A dictionary containing job metadata.
        :param file: The uploaded file object.
        :param current_user: The user who submitted the job.
        :return: A dictionary indicating the job ID and publication status.
        """
        print(
            f"[upload_media] Publishing JOB_CREATED event for job_id: {job_id} to Redis"
        )

        job_request = IngestionJobRequest(
            job_id=job_id,
            file_path=file.filename,
            content_type=job_record.get("content_type", "unknown"),
            checksum_sha256=job_record.get("checksum_sha256", "unknown"),
            submitted_by=getattr(current_user, "name", None),
        )

        # aioredis client can be used as async context manager
        async with aioredis.from_url(self.redis_url, decode_responses=True) as redis:
            await redis.publish(
                "command_queue",
                json.dumps({"event": "JOB_CREATED", **job_request.model_dump()}),
            )
            print(f"[upload_media] Published JOB_CREATED event for job_id: {job_id}")
            return {"job_id": job_id, "status": "published_to_redis"}

    # ---------------------------------------------------------------------------------
    # For Orchestrator (state management)
    # ---------------------------------------------------------------------------------
    async def get_redis_client(self) -> aioredis.Redis:
        """Get or create Redis client for orchestrator (connection pooling)."""
        if self._redis_client is None:
            self._redis_client = aioredis.from_url(
                self.redis_url, decode_responses=True
            )
        return self._redis_client

    async def save_job_state_to_redis(
        self, job_id: str, state: WorkflowGraphState
    ) -> None:
        """Persist job state to Redis as JSON."""
        redis_client = await self.get_redis_client()
        await redis_client.set(f"job_state:{job_id}", json.dumps(dict(state)))

    async def load_job_state_from_redis(
        self, job_id: str
    ) -> Optional[WorkflowGraphState]:
        """Load job state from Redis as WorkflowGraphState."""
        redis_client = await self.get_redis_client()
        data = await redis_client.get(f"job_state:{job_id}")
        if data:
            return WorkflowGraphState(**json.loads(data))
        return None

    # For Orchestrator (pub/sub listening)
    async def get_pubsub(self) -> aioredis.client.PubSub:
        """Get pubsub for Redis listening (orchestrator pattern)."""
        redis = await self.get_redis_client()
        return redis.pubsub()

    async def close(self) -> None:
        """Close the Redis connection (for orchestrator cleanup)."""
        if self._redis_client:
            await self._redis_client.close()
            self._redis_client = None
