import asyncio
import json
import async_timeout
import pytest
import tempfile
import os

from workers.extract_text_worker_service import ExtractTextService, redis_listener, EXTRACT_TEXT_CALLBACK_QUEUE, \
    EXTRACT_TEXT_QUEUE


class DummyRedisManager:
    def __init__(self, client):
        self._client = client

    async def get_redis_client(self):
        return self._client


@pytest.fixture
def extract_text_service():
    """Create an ExtractTextService instance for testing."""
    service = ExtractTextService()
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
        "step": "extract_text",
        "branch": "main",
        "metadata": {
            "validation": "passed",
            "file_size": 3848766,
            "file_extension": ".pdf",
            "page_count": 339,
            "is_encrypted": True,
            "extracting_metadata": "passed"
        },
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


def create_valid_test_pdf_with_text():
    """Create a PDF with actual text content for testing."""
    pdf_content = b'''%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT /F1 12 Tf 100 700 Td (Hello World from PDF) Tj ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000220 00000 n 
trailer
<< /Size 5 /Root 1 0 R >>
startxref
300
%%EOF'''
    return pdf_content


def create_pdf_with_no_text():
    """Create a PDF with no extractable text."""
    pdf_content = b'''%PDF-1.4
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
%%EOF'''
    return pdf_content


@pytest.mark.asyncio
async def test_extract_text_worker_success_pdf(extract_text_service, sample_pdf_state, create_test_file):
    """_process_extract_text_worker should extract text from valid PDF files."""
    # Create a PDF with text content
    pdf_content = create_valid_test_pdf_with_text()
    file_path = create_test_file(pdf_content, '.pdf')

    state = sample_pdf_state.copy()
    state["file_path"] = file_path

    result = await extract_text_service._process_extract_text_worker(state)

    # Check that text extraction was attempted and metadata was updated
    assert "text_extraction" in result["metadata"]
    assert isinstance(result["metadata"]["text_extraction"], dict)


@pytest.mark.asyncio
async def test_extract_text_nonexistent_file(extract_text_service, sample_pdf_state):
    """Text extraction should handle non-existent files gracefully."""
    state = sample_pdf_state.copy()
    state["file_path"] = "/nonexistent/file.pdf"

    result = await extract_text_service._process_extract_text_worker(state)
    assert result["status"] == "failed"
    assert "extract_text_failed" in result["step"]
    assert "errors" in result["metadata"]


@pytest.mark.asyncio
async def test_extract_text_wrong_content_type(extract_text_service, sample_pdf_state, create_test_file):
    """Text extraction should fail for non-PDF files."""
    # Create a text file but claim it's PDF
    text_content = b"This is a text file, not a PDF"
    file_path = create_test_file(text_content, '.txt')

    state = sample_pdf_state.copy()
    state["file_path"] = file_path
    state["content_type"] = "application/pdf"  # Wrong content type

    result = await extract_text_service._process_extract_text_worker(state)
    assert result["status"] == "failed"
    assert "errors" in result["metadata"]


@pytest.mark.asyncio
async def test_extract_text_from_pdf_success(extract_text_service, create_test_file):
    """_extract_text_from_pdf should extract text from PDF files."""
    # Create a PDF with text content
    pdf_content = create_valid_test_pdf_with_text()
    file_path = create_test_file(pdf_content, '.pdf')

    result = await extract_text_service._extract_text_from_pdf(file_path)

    assert "extracted_text" in result
    assert "character_count" in result
    assert "page_count" in result
    assert "pages_with_text" in result
    assert "extraction_errors" in result

    # Should have extracted some text
    assert result["character_count"] > 0
    assert "Hello World" in result["extracted_text"]


@pytest.mark.asyncio
async def test_extract_text_from_pdf_no_text(extract_text_service, create_test_file):
    """_extract_text_from_pdf should handle PDFs with no text gracefully."""
    # Create a PDF with no text
    pdf_content = create_pdf_with_no_text()
    file_path = create_test_file(pdf_content, '.pdf')

    result = await extract_text_service._extract_text_from_pdf(file_path)

    assert "extracted_text" in result
    assert "character_count" in result
    assert result["character_count"] == 0
    assert result["pages_with_text"] == 0


@pytest.mark.asyncio
async def test_extract_text_from_pdf_invalid_file(extract_text_service, create_test_file):
    """_extract_text_from_pdf should handle invalid PDF files gracefully."""
    # Create a non-PDF file
    invalid_content = b'Not a PDF file'
    file_path = create_test_file(invalid_content, '.pdf')

    result = await extract_text_service._extract_text_from_pdf(file_path)

    assert "extraction_errors" in result
    assert len(result["extraction_errors"]) > 0


@pytest.mark.asyncio
async def test_save_extracted_text_to_file(extract_text_service):
    """_save_extracted_text_to_file should save text to file successfully."""
    job_id = "test-job-123"
    extracted_text = "This is sample extracted text content for testing."
    character_count = len(extracted_text)

    file_path, file_stats = await extract_text_service._save_extracted_text_to_file(
        job_id, extracted_text, character_count
    )

    assert file_path is not None
    assert isinstance(file_path, str)
    assert file_path.endswith(f"{job_id}_extracted_text.txt")

    assert "file_size_bytes" in file_stats
    assert "character_count" in file_stats
    assert "saved_at" in file_stats

    # Verify file was actually created
    assert os.path.exists(file_path)

    # Verify content
    with open(file_path, 'r', encoding='utf-8') as f:
        saved_content = f.read()
    assert saved_content == extracted_text

    # Cleanup
    os.unlink(file_path)


@pytest.mark.asyncio
async def test_analyze_text_content(extract_text_service):
    """_analyze_text_content should analyze text successfully."""
    sample_text = """
    This is a sample technical document about microcontrollers.
    It contains information about voltage requirements and circuit design.

    The datasheet provides detailed specifications for the processor.
    This is another paragraph with more technical information.
    """

    analysis = await extract_text_service._analyze_text_content(sample_text)

    assert "word_count" in analysis
    assert "paragraph_count" in analysis
    assert "content_categories" in analysis

    assert analysis["word_count"] > 0
    assert analysis["paragraph_count"] > 0
    assert "technical_document" in analysis["content_categories"]
    assert "datasheet" in analysis["content_categories"]


@pytest.mark.asyncio
async def test_analyze_text_content_empty(extract_text_service):
    """_analyze_text_content should handle empty text gracefully."""
    analysis = await extract_text_service._analyze_text_content("")

    assert "word_count" in analysis
    assert analysis["word_count"] == 0
    assert "paragraph_count" in analysis
    assert analysis["paragraph_count"] == 0


@pytest.mark.asyncio
async def test_process_extract_text_task_success(extract_text_service, sample_pdf_state, create_test_file):
    """process_extract_text_task should process tasks successfully."""
    pdf_content = create_valid_test_pdf_with_text()
    file_path = create_test_file(pdf_content, '.pdf')

    task_data = sample_pdf_state.copy()
    task_data["file_path"] = file_path

    result = await extract_text_service.process_extract_text_task(task_data)

    assert result["job_id"] == task_data["job_id"]
    assert "metadata" in result
    assert "text_extraction" in result["metadata"]


@pytest.mark.asyncio
async def test_process_extract_text_task_invalid_data(extract_text_service):
    """process_extract_text_task should handle invalid task data gracefully."""
    invalid_task_data = {"invalid": "data"}

    result = await extract_text_service.process_extract_text_task(invalid_task_data)

    assert result["status"] == "failed"
    assert "extract_text_from_file_failed" in result["step"]
    assert "errors" in result["metadata"]


@pytest.mark.asyncio
async def test_redis_listener_integration(redis_client, sample_pdf_state, create_test_file):
    """Integration test with Redis listener for extract text service."""
    # Create valid test file
    pdf_content = create_valid_test_pdf_with_text()
    file_path = create_test_file(pdf_content, '.pdf')

    # Create service instance
    svc = ExtractTextService()
    svc.redis_manager = DummyRedisManager(redis_client)

    # Update state with real file path
    job_state = sample_pdf_state.copy()
    job_state["file_path"] = file_path

    # Start listener
    listener_task = asyncio.create_task(redis_listener(svc))
    await asyncio.sleep(0.1)

    # Prepare pubsub to listen for callback
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(EXTRACT_TEXT_CALLBACK_QUEUE)

    # Publish task
    await redis_client.publish(EXTRACT_TEXT_QUEUE, json.dumps(job_state))

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
    await pubsub.unsubscribe(EXTRACT_TEXT_CALLBACK_QUEUE)
    await pubsub.aclose()
    listener_task.cancel()

    try:
        await listener_task
    except asyncio.CancelledError:
        pass

    assert received is not None, "Did not receive extract text callback"
    assert received["job_id"] == job_state["job_id"]
    assert "metadata" in received["result"]
