"""
Media Processing Worker
----------------------
Handles media processing tasks for ingestion jobs.

Responsibilities:
- Extracts technical and descriptive metadata from files.
- Generates thumbnails for images.
- Extracts audio from videos and transcribes it.
- Generates video summaries.
- Designed to be called by the orchestrator as part of the workflow.

Usage:
    await extract_metadata_worker(state)
    await generate_thumbnails_worker(state)
    await extract_audio_worker(state)
    await transcribe_audio_worker(state)
    await generate_video_summary_worker(state)

Arguments:
    state (MyState): The job state dictionary.
Returns:
    MyState: Updated job state after processing.
"""

import asyncio
from datetime import datetime, timezone
from typing import TypedDict, Optional


class MyState(TypedDict):
    """State dictionary for media processing jobs."""

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


async def extract_metadata_worker(state: MyState) -> MyState:
    """
    Extracts technical and descriptive metadata from the file (image, video, or PDF).
    Updates the job state with extracted metadata.
    Args:
        state (MyState): The job state dictionary containing file metadata and path.
    Returns:
        MyState: Updated job state after metadata extraction.
    """
    print(f"[Worker:extract_metadata] Job {state['job_id']} extracting metadata...")
    await asyncio.sleep(0.5)
    state["status"] = "metadata_extracted"
    state["step"] = "extract_metadata"
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    state["metadata"] = {"dummy": "metadata"}
    print(
        f"[Worker:extract_metadata] Job {state['job_id']} metadata extraction done. State: {state}"
    )
    return state


async def generate_thumbnails_worker(state: MyState) -> MyState:
    """
    Generates thumbnails for image files.
    Updates the job state with thumbnail generation results.
    Args:
        state (MyState): The job state dictionary containing image metadata and path.
    Returns:
        MyState: Updated job state after thumbnail generation.
    """
    print(
        f"[Worker:generate_thumbnails] Job {state['job_id']} generating thumbnails..."
    )
    await asyncio.sleep(0.3)
    state["status"] = "thumbnails_generated"
    state["step"] = "generate_thumbnails"
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    print(
        f"[Worker:generate_thumbnails] Job {state['job_id']} thumbnails done. State: {state}"
    )
    return state


async def extract_audio_worker(state: MyState) -> MyState:
    """
    Extracts audio from video files.
    Updates the job state with audio extraction results.
    Args:
        state (MyState): The job state dictionary containing video metadata and path.
    Returns:
        MyState: Updated job state after audio extraction.
    """
    print(f"[Worker:extract_audio] Job {state['job_id']} extracting audio...")
    await asyncio.sleep(0.3)
    state["status"] = "audio_extracted"
    state["step"] = "extract_audio"
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    print(
        f"[Worker:extract_audio] Job {state['job_id']} audio extraction done. State: {state}"
    )
    return state


async def transcribe_audio_worker(state: MyState) -> MyState:
    """
    Transcribes extracted audio from video files.
    Updates the job state with transcription results.
    Args:
        state (MyState): The job state dictionary containing audio metadata and path.
    Returns:
        MyState: Updated job state after audio transcription.
    """
    print(f"[Worker:transcribe_audio] Job {state['job_id']} transcribing audio...")
    await asyncio.sleep(0.4)
    state["status"] = "audio_transcribed"
    state["step"] = "transcribe_audio"
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    print(
        f"[Worker:transcribe_audio] Job {state['job_id']} audio transcription done. State: {state}"
    )
    return state


async def generate_video_summary_worker(state: MyState) -> MyState:
    """
    Generates a summary for video files using transcribed audio and video metadata.
    Updates the job state with video summary results.
    Args:
        state (MyState): The job state dictionary containing video and audio metadata.
    Returns:
        MyState: Updated job state after video summarization.
    """
    print(
        f"[Worker:generate_video_summary] Job {state['job_id']} generating video summary..."
    )
    await asyncio.sleep(0.4)
    state["status"] = "video_summary_generated"
    state["step"] = "generate_video_summary"
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    print(
        f"[Worker:generate_video_summary] Job {state['job_id']} video summary done. State: {state}"
    )
    return state
