"""
Media Processing Worker Client for Orchestrator
----------------------------------
Lightweight client that publishes media processing tasks to Redis and waits for results.
Used by the workflow orchestrator.
"""

import os
import json
import asyncio

from contracts.job_schemas import WorkflowGraphState
from needs.INeedRedisManager import INeedRedisManagerInterface

# Configuration
MEDIA_PROCESSING_QUEUE = os.getenv("MEDIA_PROCESSING_QUEUE", "media_processing_queue")
MEDIA_PROCESSING_CALLBACK_QUEUE = os.getenv("MEDIA_PROCESSING_CALLBACK_QUEUE", "media_processing_callback_queue")


class MediaProcessingWorkerClient(INeedRedisManagerInterface):
    """Client for interacting with the media processing service."""
    async def media_process_file(self, state: WorkflowGraphState, timeout: int = 30) -> WorkflowGraphState:
        """
        Submit media processing task to media processing service and wait for result.

        Args:
            state: Job state to process the media
            timeout: Maximum time to wait for response (seconds)

        Returns:
            Updated job state with media processing results
        """
        redis_client = await self.redis_manager.get_redis_client()
        job_id = state["job_id"]

        try:
            # Publish validation task
            await redis_client.publish(MEDIA_PROCESSING_QUEUE, json.dumps(dict(state)))
            print(f"[MediaProcessingWorker] Published media processing task for job_id: {job_id}")

            # Listen for callback result with timeout
            result = await self._wait_for_media_processing_result(redis_client, job_id, timeout)
            return WorkflowGraphState(**result)

        except Exception as e:
            print(f"[MediaProcessingWorkerClient] Error during media processing for job {job_id}: {e}")
            raise

    @staticmethod
    async def _wait_for_media_processing_result(redis_client, job_id: str, timeout: int):
        """Wait for media processing result with timeout."""
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(MEDIA_PROCESSING_CALLBACK_QUEUE)

        try:
            async with asyncio.timeout(timeout):
                async for message in pubsub.listen():
                    if message.get("type") == "message":
                        try:
                            data = json.loads(message["data"])
                            if data.get("job_id") == job_id:
                                print(f"[MediaProcessingWorkerClient] Received media processing result for job_id: {job_id}")
                                return data["result"]
                        except (json.JSONDecodeError, KeyError) as e:
                            print(f"[MediaProcessingWorkerClient] Invalid message format: {e}")
                            continue
        except asyncio.TimeoutError:
            raise TimeoutError(f"Media processing service timeout for job {job_id}")
        finally:
            await pubsub.unsubscribe(MEDIA_PROCESSING_CALLBACK_QUEUE)
            await pubsub.close()


media_processing_worker_client = MediaProcessingWorkerClient()


# Backward compatibility - function used by orchestrator graph
async def media_process_file_worker_redis(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Function called by orchestrator workflow graph.
    Delegates to the media processing service via Redis.
    """
    return await media_processing_worker_client.media_process_file(state)
