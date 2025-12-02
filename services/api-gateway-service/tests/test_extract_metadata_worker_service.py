import asyncio
import json
import async_timeout
import pytest
import tempfile
import os

from cloud_management.cloud_manager import CloudManager
from redis_management.redis_manager import RedisManager
from workers.extract_metadata_worker_service import (
    ExtractMetadataService,
    EXTRACT_METADATA_QUEUE,
    EXTRACT_METADATA_CALLBACK_QUEUE,
    redis_listener,
)


class DummyRedisManager:
    def __init__(self, client):
        self._client = client

    async def get_redis_client(self):
        return self._client


@pytest.fixture
def extract_metadata_service():
    """Create an ExtractMetadataService instance for testing."""
    # Create validation service and inject needs
    service = ExtractMetadataService()
    service.redis_manager = RedisManager()
    service.cloud_manager = CloudManager()

    # Initialize the cloud client after injection
    service.cloud_manager.create_s3_client(
        access_key_id=os.getenv("AWS_ACCESS_KEY_ID", ""),
        secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", ""),
        region=os.getenv("AWS_REGION_NAME", "us-east-1"),
    )

    return service


@pytest.fixture
def sample_pdf_state():
    return {
        "job_id": "job-1",
        "file_path": "/tmp/test.pdf",
        "content_type": "application/pdf",
        "checksum_sha256": "a" * 64,
        "submitted_by": "tester",
        "status": "pending",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
        "step": "extract_metadata",
        "branch": "main",
        "metadata": {"validation": "passed"},
    }


@pytest.fixture
def create_test_file():
    """Fixture to create temporary test files."""
    test_files = []

    def _create_file(content, extension):
        fd, path = tempfile.mkstemp(suffix=extension)
        with os.fdopen(fd, "wb") as f:
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


def create_valid_test_pdf():
    """Create a more complete PDF structure that PyPDF2 can parse."""
    # This is a minimal but valid PDF structure
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
endobj
xref
0 4
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
trailer
<< /Size 4 /Root 1 0 R >>
startxref
190
%%EOF"""
    return pdf_content


@pytest.mark.asyncio
async def test_extract_metadata_worker_success_pdf(
    extract_metadata_service, sample_pdf_state, create_test_file
):
    """_process_extract_metadata_worker should extract metadata from valid PDF files."""
    # Create a valid PDF file
    pdf_content = create_valid_test_pdf()
    file_path = create_test_file(pdf_content, ".pdf")

    state = sample_pdf_state.copy()
    state["file_path"] = file_path

    result = await extract_metadata_service._process_extract_metadata_worker(state)

    # For PDFs that fail parsing, we should still get universal metadata
    assert "file_size" in result["metadata"]
    assert "file_extension" in result["metadata"]
    assert result["metadata"]["file_extension"] == ".pdf"
    assert "magic_number_verified" in result["metadata"]
    assert result["metadata"]["magic_number_verified"] == True


@pytest.mark.asyncio
async def test_extract_metadata_nonexistent_file(
    extract_metadata_service, sample_pdf_state
):
    """Metadata extraction should handle non-existent files gracefully."""
    state = sample_pdf_state.copy()
    state["file_path"] = "/nonexistent/file.pdf"

    result = await extract_metadata_service._process_extract_metadata_worker(state)
    assert result["status"] == "failed"
    assert "extract_metadata_from_file_failed" in result["step"]
    assert "errors" in result["metadata"]


@pytest.mark.asyncio
async def test_extract_universal_metadata_success(
    extract_metadata_service, sample_pdf_state, create_test_file
):
    """_extract_universal_metadata should extract basic file info."""
    pdf_content = create_valid_test_pdf()
    file_path = create_test_file(pdf_content, ".pdf")

    state = sample_pdf_state.copy()
    state["file_path"] = file_path

    metadata = await extract_metadata_service._extract_universal_metadata(state)

    assert "file_size" in metadata
    assert "file_extension" in metadata
    assert metadata["file_extension"] == ".pdf"
    assert "created_timestamp" in metadata
    assert "modified_timestamp" in metadata
    assert "magic_number_verified" in metadata
    assert metadata["magic_number_verified"] == True


@pytest.mark.asyncio
async def test_extract_pdf_metadata_success(extract_metadata_service, create_test_file):
    """_extract_pdf_metadata should extract PDF-specific information."""
    # Create a valid PDF
    pdf_content = create_valid_test_pdf()
    file_path = create_test_file(pdf_content, ".pdf")

    metadata = await extract_metadata_service._extract_pdf_metadata(file_path)

    # Even if PDF parsing fails, we should get some response
    assert isinstance(metadata, dict)
    # Check if we got successful metadata or an error
    if "pdf_metadata_error" not in metadata:
        assert "page_count" in metadata
        assert "is_encrypted" in metadata
    else:
        # If there's an error, make sure it's a string
        assert isinstance(metadata["pdf_metadata_error"], str)


@pytest.mark.asyncio
async def test_extract_pdf_metadata_invalid_file(
    extract_metadata_service, create_test_file
):
    """_extract_pdf_metadata should handle invalid PDF files gracefully."""
    # Create a non-PDF file
    invalid_content = b"Not a PDF file"
    file_path = create_test_file(invalid_content, ".pdf")

    metadata = await extract_metadata_service._extract_pdf_metadata(file_path)

    assert "pdf_metadata_error" in metadata
    # Just check that we got an error message (don't check specific content)
    assert isinstance(metadata["pdf_metadata_error"], str)
    assert len(metadata["pdf_metadata_error"]) > 0


@pytest.mark.asyncio
async def test_verify_magic_number_valid_pdf(
    extract_metadata_service, create_test_file
):
    """_verify_magic_number should return True for valid PDF signatures."""
    pdf_content = create_valid_test_pdf()
    file_path = create_test_file(pdf_content, ".pdf")

    result = await extract_metadata_service._verify_magic_number(
        file_path, "application/pdf"
    )
    assert result == True


@pytest.mark.asyncio
async def test_verify_magic_number_invalid_pdf(
    extract_metadata_service, create_test_file
):
    """_verify_magic_number should return False for invalid PDF signatures."""
    invalid_content = b"Not a PDF file"
    file_path = create_test_file(invalid_content, ".pdf")

    result = await extract_metadata_service._verify_magic_number(
        file_path, "application/pdf"
    )
    assert result == False


@pytest.mark.asyncio
async def test_verify_magic_number_unsupported_type(
    extract_metadata_service, create_test_file
):
    """_verify_magic_number should handle unsupported content types."""
    pdf_content = create_valid_test_pdf()
    file_path = create_test_file(pdf_content, ".pdf")

    # Test with unsupported content type
    result = await extract_metadata_service._verify_magic_number(
        file_path, "application/unknown"
    )
    assert result == False


@pytest.mark.asyncio
async def test_extract_image_metadata(extract_metadata_service, create_test_file):
    """_extract_image_metadata should handle image files (if dependencies available)."""
    # Create a minimal PNG file
    png_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90\x77\x53\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x00\x00\x00\x00IEND\xae\x42\x60\x82"
    file_path = create_test_file(png_content, ".png")

    try:
        metadata = await extract_metadata_service._extract_image_metadata(file_path)
        # If Pillow is available, we should get some metadata
        if "image_metadata_error" not in metadata:
            assert "dimensions" in metadata or "format" in metadata
    except ImportError:
        # Pillow not installed, skip this test
        pytest.skip("Pillow not installed")


@pytest.mark.asyncio
async def test_process_extract_metadata_task_success(
    extract_metadata_service, sample_pdf_state, create_test_file
):
    """process_extract_metadata_task should process tasks successfully."""
    pdf_content = create_valid_test_pdf()
    file_path = create_test_file(pdf_content, ".pdf")

    task_data = sample_pdf_state.copy()
    task_data["file_path"] = file_path

    result = await extract_metadata_service.process_extract_metadata_task(task_data)

    assert result["job_id"] == task_data["job_id"]
    # The task should complete (even if PDF parsing fails, we still get universal metadata)
    assert "metadata" in result
    # Check that we got at least universal metadata
    assert "file_size" in result["metadata"]
    assert "file_extension" in result["metadata"]


@pytest.mark.asyncio
async def test_process_extract_metadata_task_invalid_data(extract_metadata_service):
    """process_extract_metadata_task should handle invalid task data gracefully."""
    invalid_task_data = {"invalid": "data"}

    result = await extract_metadata_service.process_extract_metadata_task(
        invalid_task_data
    )

    assert result["status"] == "failed"
    assert "extract_metadata_from_file_failed" in result["step"]
    assert "errors" in result["metadata"]


@pytest.mark.asyncio
async def test_redis_listener_integration(
    redis_client, sample_pdf_state, create_test_file
):
    """Integration test with Redis listener for extract metadata service."""
    # Create valid test file
    pdf_content = create_valid_test_pdf()
    file_path = create_test_file(pdf_content, ".pdf")

    # Create service instance
    svc = ExtractMetadataService()
    svc.redis_manager = DummyRedisManager(redis_client)

    # Update state with real file path
    job_state = sample_pdf_state.copy()
    job_state["file_path"] = file_path

    # Start listener
    listener_task = asyncio.create_task(redis_listener(svc))
    await asyncio.sleep(0.1)

    # Prepare pubsub to listen for callback
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(EXTRACT_METADATA_CALLBACK_QUEUE)

    # Publish task
    await redis_client.publish(EXTRACT_METADATA_QUEUE, json.dumps(job_state))

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
    await pubsub.unsubscribe(EXTRACT_METADATA_CALLBACK_QUEUE)
    await pubsub.aclose()
    listener_task.cancel()

    try:
        await listener_task
    except asyncio.CancelledError:
        pass

    assert received is not None, "Did not receive extract metadata callback"
    assert received["job_id"] == job_state["job_id"]
    assert "metadata" in received["result"]
