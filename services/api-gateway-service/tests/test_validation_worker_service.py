import asyncio
import json
import async_timeout
import pytest
import tempfile
import os

from workers.validation_worker_service import (
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


@pytest.fixture
def validation_service():
    """Create a ValidationService instance for testing."""
    service = ValidationService()
    return service


@pytest.fixture
def sample_pdf_state():
    return {
        "job_id": "job-1",
        "file_path": "/tmp/test.pdf",
        "content_type": "application/pdf",
        "checksum_sha256": "a" * 64,  # Valid SHA256 length
        "submitted_by": "tester",
        "status": "pending",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
        "step": "validate_file",
        "branch": "main",
        "metadata": {},
    }


@pytest.fixture
def create_test_file():
    """Fixture to create temporary test files."""
    test_files = []

    def _create_file(content, extension):
        fd, path = tempfile.mkstemp(suffix=extension)
        with os.fdopen(fd, 'wb') as f:
            f.write(content)
        test_files.append(path)
        return path

    yield _create_file

    # Cleanup
    for path in test_files:
        try:
            os.unlink(path)
        except:
            pass


@pytest.mark.asyncio
async def test_validate_file_worker_success(validation_service, sample_pdf_state, create_test_file):
    """_validate_file_worker should mark state as success for valid files."""
    # Create a simple PDF file
    pdf_content = b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\nxref\ntrailer\n<<>>\nstartxref\n%%EOF'
    file_path = create_test_file(pdf_content, '.pdf')

    state = sample_pdf_state.copy()
    state["file_path"] = file_path

    result = await validation_service._validate_file_worker(state)
    assert result["status"] == "success"
    assert result["step"] == "validate_file_done"


@pytest.mark.asyncio
async def test_validate_file_nonexistent_file(validation_service, sample_pdf_state):
    """Validation should fail for non-existent files."""
    state = sample_pdf_state.copy()
    state["file_path"] = "/nonexistent/file.pdf"

    result = await validation_service._validate_file_worker(state)
    assert result["status"] == "failed"
    assert "does not exist" in result["metadata"]["errors"][0]


# In tests/test_validation_worker_service.py - Keep this test as is
@pytest.mark.asyncio
async def test_validate_file_size_exceeded(validation_service, sample_pdf_state, create_test_file):
    """Validation should fail for files exceeding size limit."""
    # Create a large PNG file (simplified valid PNG structure)
    png_header = b'\x89PNG\r\n\x1a\n'
    png_footer = b'\x00\x00\x00\x00IEND\xae\x42\x60\x82'

    # Create content that exceeds size limit
    large_content = png_header + (b'x' * 120) + png_footer  # Total > 100 bytes

    file_path = create_test_file(large_content, '.png')

    # Temporarily set small max size
    original_max_size = validation_service.MAX_FILE_SIZE
    validation_service.MAX_FILE_SIZE = 100  # 100 bytes

    try:
        state = sample_pdf_state.copy()
        state["file_path"] = file_path
        state["content_type"] = "image/png"  # Use allowed content type

        result = await validation_service._validate_file_worker(state)
        assert result["status"] == "failed"

        # Check all errors for the size message
        errors_text = " ".join(result["metadata"]["errors"])
        assert "exceeds maximum allowed size" in errors_text

    finally:
        validation_service.MAX_FILE_SIZE = original_max_size

@pytest.mark.asyncio
async def test_validate_file_extension_mismatch(validation_service, sample_pdf_state, create_test_file):
    """Validation should fail when file extension doesn't match content type."""
    # Create a .txt file but claim it's PDF
    file_path = create_test_file(b'text content', '.txt')

    state = sample_pdf_state.copy()
    state["file_path"] = file_path

    result = await validation_service._validate_file_worker(state)
    assert result["status"] == "failed"
    assert "does not match content type" in result["metadata"]["errors"][0]


@pytest.mark.asyncio
async def test_validate_invalid_pdf_structure(validation_service, sample_pdf_state, create_test_file):
    """Validation should fail for malformed PDF files."""
    # Create invalid PDF content
    invalid_pdf = b'Not a PDF file'
    file_path = create_test_file(invalid_pdf, '.pdf')

    state = sample_pdf_state.copy()
    state["file_path"] = file_path

    result = await validation_service._validate_file_worker(state)
    assert result["status"] == "failed"
    assert "missing PDF header" in result["metadata"]["errors"][0]


@pytest.mark.asyncio
async def test_validate_security_checks(validation_service, sample_pdf_state):
    """Validation should catch potential security issues."""
    # Test with a suspicious path that doesn't need to exist
    suspicious_path = "/tmp/file;rm -rf /etc/passwd.pdf"

    state = sample_pdf_state.copy()
    state["file_path"] = suspicious_path

    result = await validation_service._validate_file_worker(state)
    assert result["status"] == "failed"

    # Check for the security error about dangerous characters
    errors = " ".join(result["metadata"]["errors"])
    assert "dangerous characters" in errors


@pytest.mark.asyncio
async def test_validate_invalid_checksum_format(validation_service, sample_pdf_state, create_test_file):
    """Validation should fail for invalid checksum format."""
    pdf_content = b'%PDF-1.4\n...'
    file_path = create_test_file(pdf_content, '.pdf')

    state = sample_pdf_state.copy()
    state["file_path"] = file_path
    state["checksum_sha256"] = "short"  # Invalid SHA256 length

    result = await validation_service._validate_file_worker(state)
    assert result["status"] == "failed"
    assert "Invalid checksum format" in result["metadata"]["errors"][0]


@pytest.mark.asyncio
async def test_redis_listener_integration(redis_client, sample_pdf_state, create_test_file):
    """Integration test with Redis listener."""
    # Create valid test file
    pdf_content = b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\nxref\ntrailer\n<<>>\nstartxref\n%%EOF'
    file_path = create_test_file(pdf_content, '.pdf')

    # Create service instance
    svc = ValidationService()
    svc.redis_manager = DummyRedisManager(redis_client)

    # Update state with real file path
    job_state = sample_pdf_state.copy()
    job_state["file_path"] = file_path

    # Start listener
    listener_task = asyncio.create_task(redis_listener(svc))
    await asyncio.sleep(0.1)

    # Prepare pubsub to listen for callback
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(VALIDATION_CALLBACK_QUEUE)

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

    try:
        await asyncio.wait_for(wait_task, timeout=6)
    except asyncio.TimeoutError:
        pass

    # Cleanup
    await pubsub.unsubscribe(VALIDATION_CALLBACK_QUEUE)
    await pubsub.aclose()
    listener_task.cancel()

    try:
        await listener_task
    except asyncio.CancelledError:
        pass

    assert received is not None, "Did not receive validation callback"
    assert received["job_id"] == job_state["job_id"]
    assert received["result"]["status"] == "success"
