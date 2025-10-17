"""
Validation Worker
-----------------
Handles file validation tasks for ingestion jobs.

Responsibilities:
- Validates file type, size, and integrity.
- Updates job state with validation results.
- Designed to be called by the orchestrator as part of the workflow.

Usage:
    await validate_file_worker(state)

Arguments:
    state_param (WorkflowGraphState): The job state dictionary passed to workers.
Returns:
    WorkflowGraphState: Updated job state after validation.
"""

import asyncio
from datetime import datetime, timezone

import os
import json
import redis.asyncio as aioredis

from contracts.job_schemas import WorkflowGraphState
from typing import Optional


async def validate_file_worker(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Validates the file type, size, and integrity for an ingestion job.
    Updates the job state with validation results.
    Args:
        state (WorkflowGraphState): The job state dictionary containing file metadata and path.
    Returns:
        WorkflowGraphState: Updated job state after validation.
    """
    print(f"[Worker:validate_file] Job {state['job_id']} validating...")
    await asyncio.sleep(0.5)
    errors = []

    # Example validation: file type must be pdf, image, or video
    allowed_types = ["application/pdf", "image/jpeg", "image/png", "video/mp4"]
    if state["content_type"] not in allowed_types:
        errors.append(f"Unsupported file type: {state['content_type']}")

    # Example checksum validation (simulate failure if checksum ends with '0')
    if state["checksum_sha256"].endswith("0"):
        errors.append("Checksum validation failed.")

    if errors:
        state["status"] = "failed"
        state["step"] = "validate_file_failed"
        state["metadata"] = {"errors": errors}

    else:
        state["status"] = "success"
        state["step"] = "validate_file_done"
        state["metadata"] = {"validation": "passed"}

    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    print(f"[Worker:validate_file] Job {state['job_id']} validation done. State: {state}")
    return state


# --- Redis-backed helper: publishes validation request and waits for callback ---
REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/2")
VALIDATION_QUEUE = "validation_queue"
VALIDATION_CALLBACK_QUEUE = "validation_callback_queue"


async def validate_file_worker_redis(state: WorkflowGraphState, redis_client: Optional[aioredis.Redis] = None) -> WorkflowGraphState:
    """
    Publishes validation task to Redis and waits for the validator callback.

    If `redis_client` is provided, it will be reused and not closed by this function.
    Otherwise a temporary client is created and closed when the call finishes.
    """
    local_client = False
    if redis_client is None:
        redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
        local_client = True
    job_id = state["job_id"]

    # Publish validation task
    await redis_client.publish(VALIDATION_QUEUE, json.dumps(state))
    print(f"[Validation Worker] Published validation task for job_id: {job_id}")

    # Listen for callback result
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(VALIDATION_CALLBACK_QUEUE)
    try:
        async for message in pubsub.listen():
            if message.get("type") == "message":
                try:
                    result = json.loads(message["data"])
                except Exception:
                    # ignore malformed messages
                    continue
                if result.get("job_id") == job_id:
                    print(f"[Validation Worker] Received validation result for job_id: {job_id}")
                    # cleanup pubsub and local client if we created it
                    try:
                        await pubsub.unsubscribe(VALIDATION_CALLBACK_QUEUE)
                    except Exception:
                        pass
                    try:
                        await pubsub.close()
                    except Exception:
                        pass
                    if local_client:
                        try:
                            await redis_client.close()
                        except Exception:
                            pass
                    return result.get("result")
    finally:
        # best-effort cleanup
        try:
            await pubsub.unsubscribe(VALIDATION_CALLBACK_QUEUE)
        except Exception:
            pass
        try:
            await pubsub.close()
        except Exception:
            pass
        if local_client:
            try:
                await redis_client.close()
            except Exception:
                pass
