"""
Validation Worker for Orchestrator
----------------------------------
Lightweight client that publishes validation tasks to Redis and waits for results.
Used by the workflow orchestrator.

This replaces the old validate_file_worker_redis function.
"""

import os
import json
import asyncio

from contracts.job_schemas import WorkflowGraphState
from needs.INeedRedisManager import INeedRedisManagerInterface


# Configuration
VALIDATION_QUEUE = os.getenv("VALIDATION_QUEUE", "validation_queue")
VALIDATION_CALLBACK_QUEUE = os.getenv("VALIDATION_CALLBACK_QUEUE", "validation_callback_queue")


class ValidationWorkerClient(INeedRedisManagerInterface):
    """Client for interacting with the validation service."""
    async def validate_file(self, state: WorkflowGraphState, timeout: int = 30) -> WorkflowGraphState:
        """
        Submit validation task to validation service and wait for result.

        Args:
            state: Job state to validate
            timeout: Maximum time to wait for response (seconds)

        Returns:
            Updated job state with validation results
        """
        redis_client = await self.redis_manager.get_redis_client()
        job_id = state["job_id"]

        try:
            # Publish validation task
            await redis_client.publish(VALIDATION_QUEUE, json.dumps(dict(state)))
            print(f"[ValidationWorker] Published validation task for job_id: {job_id}")

            # Listen for callback result with timeout
            result = await self._wait_for_validation_result(redis_client, job_id, timeout)
            return WorkflowGraphState(**result)

        except Exception as e:
            print(f"[ValidationWorkerClient] Error during validation for job {job_id}: {e}")
            raise

    @staticmethod
    async def _wait_for_validation_result(redis_client, job_id: str, timeout: int):
        """Wait for validation result with timeout."""
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(VALIDATION_CALLBACK_QUEUE)

        try:
            async with asyncio.timeout(timeout):
                async for message in pubsub.listen():
                    if message.get("type") == "message":
                        try:
                            data = json.loads(message["data"])
                            if data.get("job_id") == job_id:
                                print(f"[ValidationWorkerClient] Received validation result for job_id: {job_id}")
                                return data["result"]
                        except (json.JSONDecodeError, KeyError) as e:
                            print(f"[ValidationWorkerClient] Invalid message format: {e}")
                            continue
        except asyncio.TimeoutError:
            raise TimeoutError(f"Validation service timeout for job {job_id}")
        finally:
            await pubsub.unsubscribe(VALIDATION_CALLBACK_QUEUE)
            await pubsub.close()


validation_worker_client = ValidationWorkerClient()


# Backward compatibility - function used by orchestrator graph
async def validate_file_worker_redis(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Function called by orchestrator workflow graph.
    Delegates to the validation service via Redis.
    """
    return await validation_worker_client.validate_file(state)
