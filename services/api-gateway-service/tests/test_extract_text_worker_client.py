import asyncio
import json
import async_timeout
import pytest

from shared_lib.contracts.job_schemas import WorkflowGraphState
from worker_clients.extract_text_worker_client import (
    ExtractTextWorkerClient,
    EXTRACT_TEXT_QUEUE,
    EXTRACT_TEXT_CALLBACK_QUEUE,
)


class DummyRedisManager:
    def __init__(self, client):
        self._client = client

    async def get_redis_client(self):
        return self._client


@pytest.mark.asyncio
async def test_extract_text_success(redis_client):
    """ExtractTextWorkerClient should publish a task and return the callback result."""
    client = ExtractTextWorkerClient()
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
        "step": "extract_text",
        "branch": "main",
        "metadata": {
            "validation": "passed",
            "file_size": 3848766,
            "file_extension": ".pdf",
            "page_count": 339,
            "is_encrypted": True,
            "extracting_metadata": "passed",
        },
    }

    async def responder():
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(EXTRACT_TEXT_QUEUE)
        try:
            async with async_timeout.timeout(3):
                async for message in pubsub.listen():
                    if message.get("type") == "message":
                        data = json.loads(message["data"])
                        # Publish callback with result
                        result = dict(data)
                        result.update(
                            {
                                "status": "success",
                                "step": "extract_text_done",
                                "metadata": {
                                    "validation": "passed",
                                    "file_size": 3848766,
                                    "file_extension": ".pdf",
                                    "page_count": 339,
                                    "is_encrypted": True,
                                    "extracting_metadata": "passed",
                                    "text_extraction": {
                                        "success": True,
                                        "extracted_character_count": 15420,
                                        "total_pages": 339,
                                        "pages_with_text": 339,
                                        "text_file_path": "/tmp/job-123_extracted_text.txt",
                                        "file_stats": {
                                            "saved_at": "2025-01-01T00:00:00Z",
                                            "file_size_bytes": 16234,
                                            "character_count": 15420,
                                        },
                                        "content_analysis": {
                                            "word_count": 2450,
                                            "paragraph_count": 89,
                                            "content_categories": [
                                                "technical_document",
                                                "datasheet",
                                            ],
                                        },
                                        "text_preview": "Sample extracted text preview...",
                                    },
                                    "extract_text": "passed",
                                },
                            }
                        )
                        await redis_client.publish(
                            EXTRACT_TEXT_CALLBACK_QUEUE,
                            json.dumps({"job_id": data["job_id"], "result": result}),
                        )
                        return
        finally:
            await pubsub.unsubscribe(EXTRACT_TEXT_QUEUE)
            await pubsub.close()

    # Start responder
    task = asyncio.create_task(responder())

    # Give responder a moment to subscribe
    await asyncio.sleep(0.05)

    # Call client extract_text which should wait for the callback
    result_state = await client.process_file_by_the_worker(state, timeout=5)

    # Cleanup
    await asyncio.wait_for(task, timeout=1)

    assert result_state["job_id"] == state["job_id"]
    assert result_state["status"] == "success"
    assert result_state["step"] == "extract_text_done"
    assert result_state["metadata"]["text_extraction"]["success"] == True
    assert (
        result_state["metadata"]["text_extraction"]["extracted_character_count"]
        == 15420
    )
    assert "text_file_path" in result_state["metadata"]["text_extraction"]


@pytest.mark.asyncio
async def test_extract_text_timeout(redis_client):
    """If no callback is published within timeout, a TimeoutError should be raised."""
    client = ExtractTextWorkerClient()
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
        "step": "extract_text",
        "branch": "main",
        "metadata": {
            "validation": "passed",
            "file_size": 3848766,
            "file_extension": ".pdf",
            "page_count": 339,
            "is_encrypted": True,
            "extracting_metadata": "passed",
        },
    }

    with pytest.raises(
        TimeoutError, match=f"Extract text service timeout for job {state['job_id']}"
    ):
        await client.process_file_by_the_worker(state, timeout=0.1)  # 100ms timeout
