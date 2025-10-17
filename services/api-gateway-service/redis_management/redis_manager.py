import json
import os

import redis.asyncio as aioredis

from contracts.job_schemas import IngestionJobRequest


REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/2")
USE_REDIS_PUBLISH = os.getenv("USE_REDIS_PUBLISH", "false").lower() == "true"
redis = aioredis.from_url(REDIS_URL, decode_responses=True)


class RedisManager:
    async def publish_message_to_redis(self, job_id: str, job_record: dict, file, current_user):
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

        # Job published to Redis (command_queue channel) as a JSON event (JOB_CREATED).
        await redis.publish(
            "command_queue",
            json.dumps({"event": "JOB_CREATED", **job_request.model_dump()}),
        )
        print(
            f"[upload_media] Published JOB_CREATED event for job_id: {job_id}"
        )
        return {"job_id": job_id, "status": "published_to_redis"}
