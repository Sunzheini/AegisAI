import asyncio
import json
import async_timeout
import pytest

from validation_worker_service import (
    ValidationService,
    VALIDATION_QUEUE,
    VALIDATION_CALLBACK_QUEUE,
    redis_listener,
)


class DummyRedisManager:
    def __init__(self, client):
        self._client = client

    async def get_redis_client(self):
        return self._client


@pytest.mark.asyncio
async def test_validate_file_worker_success():
    """_validate_file_worker should mark state as success for allowed types and valid checksum."""
    state = {
        "job_id": "job-1",
        "file_path": "/tmp/f.pdf",
        "content_type": "application/pdf",
        "checksum_sha256": "abc123",
        "submitted_by": "tester",
        "status": "pending",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
        "step": "validate_file",
        "branch": "main",
        "metadata": {},
    }

    result = await ValidationService._validate_file_worker(state.copy())
    assert result["status"] == "success"
    assert result["step"] == "validate_file_done"
    assert "updated_at" in result


@pytest.mark.asyncio
async def test_validate_file_worker_failure_cases():
    """Unsupported content type and checksum failure should set failed status and errors."""
    # Unsupported type
    state1 = {
        "job_id": "job-2",
        "file_path": "/tmp/f.bin",
        "content_type": "application/octet-stream",
        "checksum_sha256": "abc123",
        "submitted_by": "tester",
        "status": "pending",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
        "step": "validate_file",
        "branch": "main",
        "metadata": {},
    }

    res1 = await ValidationService._validate_file_worker(state1.copy())
    assert res1["status"] == "failed"
    assert res1["step"] == "validate_file_failed"
    assert "Unsupported file type" in res1["metadata"]["errors"][0]

    # Checksum failure
    state2 = state1.copy()
    state2["content_type"] = "application/pdf"
    state2["checksum_sha256"] = "endswith0"

    res2 = await ValidationService._validate_file_worker(state2.copy())
    assert res2["status"] == "failed"
    assert res2["step"] == "validate_file_failed"
    assert "Checksum validation failed" in res2["metadata"]["errors"][0]


@pytest.mark.asyncio
async def test_process_validation_task_returns_structured_result():
    svc = ValidationService()

    valid = {
        "job_id": "job-3",
        "file_path": "/tmp/f.pdf",
        "content_type": "application/pdf",
        "checksum_sha256": "abc123",
        "submitted_by": "tester",
        "status": "pending",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
        "step": "validate_file",
        "branch": "main",
        "metadata": {},
    }

    result = await svc.process_validation_task(valid)
    assert result["job_id"] == "job-3"
    assert result["status"] in ("success", "failed")
    assert "updated_at" in result


@pytest.mark.asyncio
async def test_redis_listener_integration(redis_client):
    """Start the redis_listener, publish a validation task, and assert we receive a callback."""
    svc = ValidationService()
    svc.redis_manager = DummyRedisManager(redis_client)

    # Start listener
    listener_task = asyncio.create_task(redis_listener(svc))

    # Give listener a moment to subscribe
    await asyncio.sleep(0.05)

    # Prepare pubsub to listen for callback
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(VALIDATION_CALLBACK_QUEUE)

    job_state = {
        "job_id": "job-redis-1",
        "file_path": "/tmp/f.pdf",
        "content_type": "application/pdf",
        "checksum_sha256": "abc123",
        "submitted_by": "tester",
        "status": "pending",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
        "step": "validate_file",
        "branch": "main",
        "metadata": {},
    }

    # Publish task
    await redis_client.publish(VALIDATION_QUEUE, json.dumps(job_state))

    received = None

    async def waiter():
        nonlocal received
        try:
            async with async_timeout.timeout(5):
                async for message in pubsub.listen():
                    if message.get("type") == "message":
                        received = json.loads(message["data"])
                        return
        except asyncio.TimeoutError:
            return

    wait_task = asyncio.create_task(waiter())

    # Wait for callback or timeout
    try:
        await asyncio.wait_for(wait_task, timeout=6)
    except asyncio.TimeoutError:
        pass

    # Cleanup
    await pubsub.unsubscribe(VALIDATION_CALLBACK_QUEUE)
    await pubsub.aclose()

    # Stop listener
    listener_task.cancel()
    try:
        await listener_task
    except asyncio.CancelledError:
        pass

    assert received is not None, "Did not receive validation callback"
    assert received["job_id"] == job_state["job_id"]
    assert "result" in received
    assert received["result"]["job_id"] == job_state["job_id"]
