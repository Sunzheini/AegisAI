"""
Contains the RedisManager class responsible for managing Redis interactions.
"""
import json
import os

import redis.asyncio as aioredis

from contracts.job_schemas import IngestionJobRequest


class RedisManager:
    """Manages Redis interactions for publishing job events."""
    def __init__(self):
        self.redis_url = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/2")

    async def publish_message_to_redis(self, job_id: str, job_record: dict, file, current_user):
        """
        Publishes a JOB_CREATED event to Redis for the given job.
        :param job_id: The unique identifier for the job.
        :param job_record: A dictionary containing job metadata.
        :param file: The uploaded file object.
        :param current_user: The user who submitted the job.
        :return: A dictionary indicating the job ID and publication status.
        """
        print(f"[upload_media] Publishing JOB_CREATED event for job_id: {job_id} to Redis")

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
