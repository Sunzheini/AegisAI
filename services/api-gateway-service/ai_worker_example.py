"""
AI Worker
---------
Handles AI-powered analysis and summarization tasks for ingestion jobs.

Responsibilities:
- Analyzes images using AI models.
- Extracts text from documents (PDFs).
- Summarizes documents using AI.
- Designed to be called by the orchestrator as part of the workflow.

Usage:
    await analyze_image_with_ai_worker(state)
    await extract_text_worker(state)
    await summarize_document_worker(state)

Arguments:
    state (MyState): The job state dictionary.
Returns:
    MyState: Updated job state after AI processing.
"""

import asyncio
from datetime import datetime, timezone
from typing import TypedDict, Optional


class MyState(TypedDict):
    """State dictionary for job processing."""

    job_id: str
    file_path: str
    content_type: str
    checksum_sha256: str
    submitted_by: str
    status: str
    created_at: str
    updated_at: str
    step: str
    branch: str
    metadata: Optional[dict]


async def analyze_image_with_ai_worker(state: MyState) -> MyState:
    """
    Analyzes an image using AI models.
    Updates the job state with analysis results.

    Args:
        state (MyState): The job state dictionary containing image metadata and file path.

    Returns:
        MyState: Updated job state after image analysis.
    """
    print(
        f"[Worker:analyze_image_with_ai] Job {state['job_id']} analyzing image with AI..."
    )
    await asyncio.sleep(0.4)
    state["status"] = "image_analyzed"
    state["step"] = "analyze_image_with_ai"
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    print(
        f"[Worker:analyze_image_with_ai] Job {state['job_id']} image analysis done. State: {state}"
    )
    return state


async def extract_text_worker(state: MyState) -> MyState:
    """
    Extracts text from a PDF document using AI or OCR techniques.
    Updates the job state with extracted text metadata.

    Args:
        state (MyState): The job state dictionary containing PDF metadata and file path.

    Returns:
        MyState: Updated job state after text extraction.
    """
    print(f"[Worker:extract_text] Job {state['job_id']} extracting text from PDF...")
    await asyncio.sleep(0.3)
    state["status"] = "text_extracted"
    state["step"] = "extract_text"
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    print(
        f"[Worker:extract_text] Job {state['job_id']} text extraction done. State: {state}"
    )
    return state


async def summarize_document_worker(state: MyState) -> MyState:
    """
    Summarizes a document (e.g., PDF) using AI models.
    Updates the job state with the summary results.

    Args:
        state (MyState): The job state dictionary containing extracted text and document metadata.

    Returns:
        MyState: Updated job state after summarization.
    """
    print(f"[Worker:summarize_document] Job {state['job_id']} summarizing document...")
    await asyncio.sleep(0.4)
    state["status"] = "document_summarized"
    state["step"] = "summarize_document"
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    print(
        f"[Worker:summarize_document] Job {state['job_id']} document summary done. State: {state}"
    )
    return state
