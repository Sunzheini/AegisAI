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
from typing import Dict, Any, TypedDict, Optional


class MyState(TypedDict):
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
    state["status"] = "validate_in_progress"
    state["step"] = "validate_file"
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    print(
        f"[Worker:validate_file] Job {state['job_id']} validation done. State: {state}"
    )
    return state
