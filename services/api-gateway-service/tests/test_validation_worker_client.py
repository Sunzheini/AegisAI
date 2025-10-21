import asyncio
import json
import async_timeout
import pytest

from contracts.job_schemas import WorkflowGraphState
from worker_clients.validation_worker_client import (
    ValidationWorkerClient,
    VALIDATION_QUEUE,
    VALIDATION_CALLBACK_QUEUE,
)


class DummyRedisManager:
    def __init__(self, client):
        self._client = client

    async def get_redis_client(self):
        return self._client


@pytest.mark.asyncio
async def test_validate_file_success(redis_client):
    """ValidationWorkerClient should publish a task and return the callback result."""
    client = ValidationWorkerClient()
    client.redis_manager = DummyRedisManager(redis_client)

    # Sample workflow state
    state: WorkflowGraphState = {
        "job_id": "job-123",
        "file_path": "/tmp/file.pdf",
        "content_type": "application/pdf",
        "checksum_sha256": "abcdef1",
        "submitted_by": "tester",
        "status": "pending",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
        "step": "validate_file",
        "branch": "main",
        "metadata": {},
    }

    async def responder():
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(VALIDATION_QUEUE)
        try:
            async with async_timeout.timeout(3):
                async for message in pubsub.listen():
                    if message.get("type") == "message":
                        data = json.loads(message["data"])
                        # Publish callback with result
                        result = dict(data)
                        result.update({
                            "status": "success",
                            "step": "validate_file_done",
                            "metadata": {"validation": "passed"},
                        })
                        await redis_client.publish(
                            VALIDATION_CALLBACK_QUEUE, json.dumps({"job_id": data["job_id"], "result": result})
                        )
                        return
        finally:
            await pubsub.unsubscribe(VALIDATION_QUEUE)
            await pubsub.close()

    # Start responder
    task = asyncio.create_task(responder())

    # Give responder a moment to subscribe
    await asyncio.sleep(0.05)

    # Call client validate_file which should wait for the callback
    result_state = await client.process_file_by_the_worker(state, timeout=5)

    # Cleanup
    await asyncio.wait_for(task, timeout=1)

    assert result_state["job_id"] == state["job_id"]
    assert result_state["status"] == "success"
    assert result_state["step"] == "validate_file_done"


@pytest.mark.asyncio
async def test_validate_file_timeout(redis_client):
    """If no callback is published within timeout, a TimeoutError should be raised."""
    client = ValidationWorkerClient()
    client.redis_manager = DummyRedisManager(redis_client)

    state: WorkflowGraphState = {
        "job_id": "job-timeout",
        "file_path": "/tmp/file.pdf",
        "content_type": "application/pdf",
        "checksum_sha256": "abcdef1",
        "submitted_by": "tester",
        "status": "pending",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
        "step": "validate_file",
        "branch": "main",
        "metadata": {},
    }

    with pytest.raises(TimeoutError, match=f"Validation service timeout for job {state['job_id']}"):
        await client.process_file_by_the_worker(state, timeout=0.1)  # 100ms timeout
