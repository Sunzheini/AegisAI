"""
Validation Worker
-----------------
Handles file validation tasks for ingestion jobs.

Responsibilities:
- Validates file type, size, and integrity.
- Updates job state with validation results.
- Designed to be called by the orchestrator as part of the workflow.

Usage:
    await validate_file_worker(state)

Arguments:
    state (MyState): The job state dictionary.
Returns:
    MyState: Updated job state after validation.
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


async def validate_file_worker(state: MyState) -> MyState:
    """
    Validates the file type, size, and integrity for an ingestion job.
    Updates the job state with validation results.
    Args:
        state (MyState): The job state dictionary containing file metadata and path.
    Returns:
        MyState: Updated job state after validation.
    """
    print(f"[Worker:validate_file] Job {state['job_id']} validating...")
    await asyncio.sleep(0.5)
    errors = []

    # Example validation: file type must be pdf, image, or video
    allowed_types = ["application/pdf", "image/jpeg", "image/png", "video/mp4"]
    if state["content_type"] not in allowed_types:
        errors.append(f"Unsupported file type: {state['content_type']}")
    # Example checksum validation (simulate failure if checksum ends with '0')
    if state["checksum_sha256"].endswith("0"):
        errors.append("Checksum validation failed.")
    if errors:
        state["status"] = "failed"
        state["step"] = "validate_file_failed"
        state["metadata"] = {"errors": errors}
    else:
        state["status"] = "success"
        state["step"] = "validate_file_done"
        state["metadata"] = {"validation": "passed"}
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    print(f"[Worker:validate_file] Job {state['job_id']} validation done. State: {state}")
    return state
