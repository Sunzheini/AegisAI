"""
Base for all worker clients
"""
import os
import json
import asyncio
from abc import abstractmethod

# Conditional import for shared library usage ----------------------------------------------
USE_SHARED_LIB = os.getenv("USE_SHARED_LIB", False)
if USE_SHARED_LIB:
    from shared_lib.contracts.job_schemas import WorkflowGraphState
else:
    from shared_lib.contracts.job_schemas import WorkflowGraphState
# ------------------------------------------------------------------------------------------

from needs.INeedRedisManager import INeedRedisManagerInterface


class BaseWorkerClient(INeedRedisManagerInterface):
    """Client for interacting with a service."""

    @abstractmethod
    def __init__(self):
        """Override in inheriting class."""
        self.worker_name = ""  # e.g., 'ValidationWorker'
        self.task_name = ""  # e.g., 'validation'
        self.worker_queue = None  # e.g., 'validation_queue'
        self.worker_callback_queue = None  # e.g., 'validation_callback_queue'

    async def process_file_by_the_worker(
        self, state: WorkflowGraphState, timeout: int = 30
    ) -> WorkflowGraphState:
        """
        Submit a task to and wait for result.

        Args:
            state: Job state to process
            timeout: Maximum time to wait for response (seconds)

        Returns:
            Updated job state with worker results
        """
        redis_client = await self.redis_manager.get_redis_client()
        job_id = state["job_id"]

        try:
            # Publish a task
            await redis_client.publish(self.worker_queue, json.dumps(dict(state)))
            print(
                f"[{self.worker_name}] Published {self.task_name} task for job_id: {job_id}"
            )

            # Listen for callback result with timeout
            result = await self._wait_for_worker_result(redis_client, job_id, timeout)
            return WorkflowGraphState(**result)

        except Exception as e:
            print(
                f"[{self.worker_name}Client] Error during {self.task_name} for job {job_id}: {e}"
            )
            raise

    async def _wait_for_worker_result(self, redis_client, job_id: str, timeout: int):
        """Wait for worker result with timeout."""
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(self.worker_callback_queue)

        try:
            async with asyncio.timeout(timeout):
                async for message in pubsub.listen():
                    if message.get("type") == "message":
                        try:
                            data = json.loads(message["data"])
                            if data.get("job_id") == job_id:
                                print(
                                    f"[{self.worker_name}Client] Received {self.task_name} result for job_id: {job_id}"
                                )
                                return data["result"]
                        except (json.JSONDecodeError, KeyError) as e:
                            print(
                                f"[{self.worker_name}Client] Invalid message format: {e}"
                            )
                            continue
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"{self.task_name.capitalize()} service timeout for job {job_id}"
            )
        finally:
            await pubsub.unsubscribe(self.worker_callback_queue)
            await pubsub.close()
