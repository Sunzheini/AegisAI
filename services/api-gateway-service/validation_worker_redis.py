"""
Redis-based Validation Worker
----------------------------
Listens to 'validation_queue' for validation tasks, processes them, and publishes results to 'validation_callback_queue'.
"""
import os
import json
import asyncio
import redis.asyncio as aioredis
from validation_worker_example import validate_file_worker

REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/2")
VALIDATION_QUEUE = "validation_queue"
CALLBACK_QUEUE = "validation_callback_queue"

async def main():
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(VALIDATION_QUEUE)
    print("[ValidationWorker] Listening for validation tasks...")
    async for message in pubsub.listen():
        if message["type"] == "message":
            task = json.loads(message["data"])
            job_id = task["job_id"]
            print(f"[ValidationWorker] Received validation task for job_id: {job_id}")
            # Call the existing validation logic
            result_state = await validate_file_worker(task)
            # Publish result to callback queue
            await redis_client.publish(CALLBACK_QUEUE, json.dumps({"job_id": job_id, "result": result_state}))
            print(f"[ValidationWorker] Published result for job_id: {job_id}")

if __name__ == "__main__":
    asyncio.run(main())

