"""
Extract Metadata Worker Client for Orchestrator
----------------------------------
Lightweight client that publishes extract metadata tasks to Redis and waits for results.
Used by the workflow orchestrator.
"""

import os
import json
import asyncio

from contracts.job_schemas import WorkflowGraphState
from needs.INeedRedisManager import INeedRedisManagerInterface

# Configuration
EXTRACT_METADATA_QUEUE = os.getenv("EXTRACT_METADATA_QUEUE", "extract_metadata_queue")
EXTRACT_METADATA_CALLBACK_QUEUE = os.getenv("EXTRACT_METADATA_CALLBACK_QUEUE", "extract_metadata_callback_queue")


class ExtractMetadataWorkerClient(INeedRedisManagerInterface):
    """Client for interacting with the extract metadata service."""
    async def extract_metadata_from_file(self, state: WorkflowGraphState, timeout: int = 30) -> WorkflowGraphState:
        """
        Submit extract metadata task to extract metadata service and wait for result.

        Args:
            state: Job state to extract the metadata for
            timeout: Maximum time to wait for response (seconds)

        Returns:
            Updated job state with extract metadata results
        """
        redis_client = await self.redis_manager.get_redis_client()
        job_id = state["job_id"]

        try:
            # Publish validation task
            await redis_client.publish(EXTRACT_METADATA_QUEUE, json.dumps(dict(state)))
            print(f"[ExtractMetadataWorker] Published extract metadata task for job_id: {job_id}")

            # Listen for callback result with timeout
            result = await self._wait_for_extract_metadata_result(redis_client, job_id, timeout)
            return WorkflowGraphState(**result)

        except Exception as e:
            print(f"[ExtractMetadataWorkerClient] Error during extracting metadata for job {job_id}: {e}")
            raise

    @staticmethod
    async def _wait_for_extract_metadata_result(redis_client, job_id: str, timeout: int):
        """Wait for extract metadata result with timeout."""
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(EXTRACT_METADATA_CALLBACK_QUEUE)

        try:
            async with asyncio.timeout(timeout):
                async for message in pubsub.listen():
                    if message.get("type") == "message":
                        try:
                            data = json.loads(message["data"])
                            if data.get("job_id") == job_id:
                                print(f"[ExtractMetadataWorkerClient] Received extract metadata result for job_id: {job_id}")
                                return data["result"]
                        except (json.JSONDecodeError, KeyError) as e:
                            print(f"[ExtractMetadataWorkerClient] Invalid message format: {e}")
                            continue
        except asyncio.TimeoutError:
            raise TimeoutError(f"Extract metadata service timeout for job {job_id}")
        finally:
            await pubsub.unsubscribe(EXTRACT_METADATA_CALLBACK_QUEUE)
            await pubsub.close()


extract_metadata_worker_client = ExtractMetadataWorkerClient()


# Backward compatibility - function used by orchestrator graph
async def extract_metadata_from_file_worker_redis(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Function called by orchestrator workflow graph.
    Delegates to the extract metadata service via Redis.
    """
    return await extract_metadata_worker_client.extract_metadata_from_file(state)
