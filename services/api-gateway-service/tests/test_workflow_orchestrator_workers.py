"""
Unit tests for worker functions
Covers: validate_file, extract_metadata, route_workflow, generate_thumbnails, analyze_image_with_ai, extract_audio, transcribe_audio, generate_video_summary, extract_text, summarize_document
"""

import pytest
from validation_worker_example import validate_file_worker
from media_processing_worker_example import (
    extract_metadata_worker,
    generate_thumbnails_worker,
    extract_audio_worker,
    transcribe_audio_worker,
    generate_video_summary_worker,
)
from ai_worker_example import (
    analyze_image_with_ai_worker,
    extract_text_worker,
    summarize_document_worker,
)
from workflow_orchestrator_example import WorkflowOrchestrator


@pytest.mark.asyncio
async def test_worker_validate_file():
    state = {
        "job_id": "test_job",
        "file_path": "storage/raw/test_job.pdf",
        "content_type": "application/pdf",
        "checksum_sha256": "dummychecksum",
        "submitted_by": "TestUser",
    }
    result = await validate_file_worker(state.copy())
    assert result["status"] == "success"
    assert result["step"] == "validate_file_done"
    assert "updated_at" in result


@pytest.mark.asyncio
async def test_worker_extract_metadata():
    state = {
        "job_id": "test_job",
        "file_path": "storage/raw/test_job.pdf",
        "content_type": "application/pdf",
        "checksum_sha256": "dummychecksum",
        "submitted_by": "TestUser",
    }
    result = await extract_metadata_worker(state.copy())
    assert result["status"] == "metadata_extracted"
    assert result["step"] == "extract_metadata"
    assert "metadata" in result
    assert "updated_at" in result


@pytest.mark.asyncio
async def test_worker_route_workflow():
    orchestrator = WorkflowOrchestrator()
    state = {
        "job_id": "test_job",
        "file_path": "storage/raw/test_job.pdf",
        "content_type": "application/pdf",
        "checksum_sha256": "dummychecksum",
        "submitted_by": "TestUser",
    }
    result = await orchestrator._worker_route_workflow(state.copy())
    assert result["step"] == "route_workflow"
    assert result["branch"] == "pdf_branch"
    assert result["status"] == "routed_to_pdf_branch"
    assert "updated_at" in result


@pytest.mark.asyncio
async def test_worker_generate_thumbnails():
    state = {"job_id": "test_job"}
    result = await generate_thumbnails_worker(state.copy())
    assert result["status"] == "thumbnails_generated"
    assert result["step"] == "generate_thumbnails"
    assert "updated_at" in result


@pytest.mark.asyncio
async def test_worker_analyze_image_with_ai():
    state = {"job_id": "test_job"}
    result = await analyze_image_with_ai_worker(state.copy())
    assert result["status"] == "image_analyzed"
    assert result["step"] == "analyze_image_with_ai"
    assert "updated_at" in result


@pytest.mark.asyncio
async def test_worker_extract_audio():
    state = {"job_id": "test_job"}
    result = await extract_audio_worker(state.copy())
    assert result["status"] == "audio_extracted"
    assert result["step"] == "extract_audio"
    assert "updated_at" in result


@pytest.mark.asyncio
async def test_worker_transcribe_audio():
    state = {"job_id": "test_job"}
    result = await transcribe_audio_worker(state.copy())
    assert result["status"] == "audio_transcribed"
    assert result["step"] == "transcribe_audio"
    assert "updated_at" in result


@pytest.mark.asyncio
async def test_worker_generate_video_summary():
    state = {"job_id": "test_job"}
    result = await generate_video_summary_worker(state.copy())
    assert result["status"] == "video_summary_generated"
    assert result["step"] == "generate_video_summary"
    assert "updated_at" in result


@pytest.mark.asyncio
async def test_worker_extract_text():
    state = {"job_id": "test_job"}
    result = await extract_text_worker(state.copy())
    assert result["status"] == "text_extracted"
    assert result["step"] == "extract_text"
    assert "updated_at" in result


@pytest.mark.asyncio
async def test_worker_summarize_document():
    state = {"job_id": "test_job"}
    result = await summarize_document_worker(state.copy())
    assert result["status"] == "document_summarized"
    assert result["step"] == "summarize_document"
    assert "updated_at" in result
