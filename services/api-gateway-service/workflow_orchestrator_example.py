"""
Workflow Orchestrator Service
----------------------------
Orchestrates ingestion jobs using a workflow graph (LangGraph).
Supports both direct HTTP job submission and event-driven orchestration via Redis.

Features:
    - Modular design for migration to AWS or other cloud platforms
    - All workflow logic encapsulated in WorkflowOrchestrator class
    - Endpoints: POST /jobs (submit job), GET /jobs/{job_id} (poll status)
    - Redis listener for JOB_CREATED events from API Gateway

Environment Variables:
    - USE_REDIS_LISTENER: Enable Redis event-driven orchestration
    - TEST_REDIS_URL: Redis connection string for tests

To run:
    uvicorn workflow_orchestrator_example:app --reload --port 9000

Migration Notes:
    - Move shared contracts (e.g., contracts/job_schemas.py) to new project
    - Update import paths as needed
    - Ensure both services use the same Redis instance and job schema
    - Replace in-memory stores with S3/DynamoDB for production
    - Replace simulated workers with Lambda/Step Functions for cloud
"""

import os
import json
from typing import Dict, Any, TypedDict
from datetime import datetime
import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Optional

import redis.asyncio as aioredis
from langgraph.graph import StateGraph, END
from fastapi import FastAPI, HTTPException, status, Request

from contracts.job_schemas import IngestionJobRequest, IngestionJobStatusResponse


REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/2")
redis = aioredis.from_url(REDIS_URL, decode_responses=True)
USE_REDIS_LISTENER = os.getenv("USE_REDIS_LISTENER", "true").lower() == "true"


# ToDo: when moving Give the workflow orchestrator direct access to the storage via shared folder, it is better to pass only the file path and metadata in the job request, not the file content itself.


@asynccontextmanager
async def lifespan(app):
    if USE_REDIS_LISTENER:
        print("[Orchestrator] Redis listener mode enabled. Starting Redis listener...")
        task = asyncio.create_task(redis_listener())
        yield
        print("[Orchestrator] Shutting down Redis listener.")
        task.cancel()
    else:
        print("[Orchestrator] Redis listener mode disabled. Only direct HTTP submission will be processed.")
        yield


app = FastAPI(title="Workflow Orchestrator Example", lifespan=lifespan)


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


class WorkflowOrchestrator:
    """
    Orchestrates ingestion jobs using a workflow graph.
    Each step is a simulated async worker.
    Replace with real workers/cloud services for production.
    """
    def __init__(self):
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger("orchestrator")
        # Define workflow graph structure
        self.graph = self._build_graph()

    def _build_graph(self):
        print("[Orchestrator] Building workflow graph...")
        # Use LangGraph StateGraph if available, else use dict
        if StateGraph:
            print("[Orchestrator] Using LangGraph StateGraph with state_schema=MyState.")
            graph = StateGraph(state_schema=MyState)

            # Nodes
            graph.add_node("validate_file", self._worker_validate_file)
            graph.add_node("extract_metadata", self._worker_extract_metadata)
            graph.add_node("route_workflow", self._worker_route_workflow)
            graph.add_node("generate_thumbnails", self._worker_generate_thumbnails)
            graph.add_node("analyze_image_with_ai", self._worker_analyze_image_with_ai)
            graph.add_node("extract_audio", self._worker_extract_audio)
            graph.add_node("transcribe_audio", self._worker_transcribe_audio)
            graph.add_node("generate_video_summary", self._worker_generate_video_summary)
            graph.add_node("extract_text", self._worker_extract_text)
            graph.add_node("summarize_document", self._worker_summarize_document)
            print("[Orchestrator] Added all nodes to graph.")

            # Edges
            graph.add_edge("validate_file", "extract_metadata")
            graph.add_edge("extract_metadata", "route_workflow")
            print("[Orchestrator] Added main edges.")

            # Conditional routing based on content type
            def route_workflow(state: MyState):
                return state["branch"]

            graph.add_conditional_edges(
                "route_workflow",
                route_workflow,
                {
                    "image_branch": "generate_thumbnails",
                    "video_branch": "extract_audio",
                    "pdf_branch": "extract_text"
                }
            )

            # # Explicit edges for all possible branches
            # graph.add_edge("route_workflow", "generate_thumbnails")
            # graph.add_edge("route_workflow", "analyze_image_with_ai")
            # graph.add_edge("route_workflow", "extract_audio")
            # graph.add_edge("route_workflow", "transcribe_audio")
            # graph.add_edge("route_workflow", "generate_video_summary")
            # graph.add_edge("route_workflow", "extract_text")
            # graph.add_edge("route_workflow", "summarize_document")
            # print("[Orchestrator] Added explicit edges for all branches.")

            # Define branch flows
            graph.add_edge("generate_thumbnails", "analyze_image_with_ai")
            graph.add_edge("analyze_image_with_ai", END)

            graph.add_edge("extract_audio", "transcribe_audio")
            graph.add_edge("transcribe_audio", "generate_video_summary")
            graph.add_edge("generate_video_summary", END)

            graph.add_edge("extract_text", "summarize_document")
            graph.add_edge("summarize_document", END)

            graph.set_entry_point("validate_file")
            compiled_graph = graph.compile()

            # Add visualization to see if your graph is built correctly
            try:
                compiled_graph.get_graph().draw_mermaid_png(output_file_path='workflow_graph.png')
                print("[Orchestrator] Workflow graph visualization saved to workflow_graph.png")
            except Exception as e:
                print(f"[Orchestrator] Could not generate graph visualization: {e}")

            return compiled_graph

            # return graph
        else:
            print("[Orchestrator] LangGraph not available, using fallback graph structure.")
            return {
                "nodes": [
                    "validate_file", "extract_metadata", "route_workflow"
                ],
                "branches": {
                    "image": ["generate_thumbnails", "analyze_image_with_ai"],
                    "video": ["extract_audio", "transcribe_audio", "generate_video_summary"],
                    "pdf": ["extract_text", "summarize_document"],
                }
            }

    async def submit_job(self, job: IngestionJobRequest) -> None:
        """
        Submit a new job to the orchestrator.
        Args:
            job (IngestionJobRequest): Job request from API Gateway.
        Raises:
            ValueError: If job_id already exists.
        """
        print(f"[Orchestrator] Received job submission: {job.job_id}")
        if job.job_id in self.jobs:
            print(f"[Orchestrator] Job {job.job_id} already exists!")
            raise ValueError("Job already exists")

        # Initialize all required fields for TypedDict
        state = MyState(
            job_id=job.job_id,
            file_path=job.file_path,
            content_type=job.content_type,
            checksum_sha256=job.checksum_sha256,
            submitted_by=job.submitted_by,
            status="queued",  # ✅ Add default value
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
            step="queued",  # ✅ Add default value
            branch="",  # ✅ Add default value (will be set by route_workflow)
            metadata=None  # ✅ Add default value
        )

        self.jobs[job.job_id] = state
        print(f"[Orchestrator] Job {job.job_id} queued. Initial state: {state}")
        print(f"Jon content type: {job.content_type}")
        # Start workflow in background
        asyncio.create_task(self._run_workflow(job.job_id))


    async def _run_workflow(self, job_id: str):
        try:
            state = self.jobs[job_id]
            print(f"[DEBUG] Before graph.ainvoke: {state}")
            final_state = await self.graph.ainvoke(state)
            self.jobs[job_id] = final_state
        except Exception as e:
            # Get the current state and update it
            state = self.jobs[job_id]
            state["status"] = "failed"
            current_step = state.get("step", "unknown")
            state["step"] = f"failed_at_{current_step}"
            state["updated_at"] = datetime.utcnow().isoformat()  # Add this too
            self.jobs[job_id] = state
            self.logger.error(f"Workflow failed for job {job_id}: {e}")

    async def _worker_validate_file(self, state: MyState) -> MyState:
        """
        Simulated validation worker.
        Receives initial metadata from IngestionJobRequest (job_id, file_path, content_type, checksum_sha256, submitted_by).
        Performs validation on the file (e.g., existence, integrity, format checks).
        In production, replace with a real validation service.
        Args:
            job_id (str): The job identifier.
        """
        print(f"[Worker:validate_file] Job {state['job_id']} validating...")  # ✅ Use dict access
        await asyncio.sleep(0.5)
        state["status"] = "validate_in_progress"  # ✅ Use dict access
        state["step"] = "validate_file"  # ✅ Use dict access
        state["updated_at"] = datetime.utcnow().isoformat()  # ✅ Use dict access
        print(f"[Worker:validate_file] Job {state['job_id']} validation done. State: {state}")  # ✅ Use dict access
        return state

    async def _worker_extract_metadata(self, state: MyState) -> MyState:
        """
        Simulated metadata extraction worker.
        Receives initial metadata from IngestionJobRequest.
        Extracts additional technical/descriptive metadata from the file itself, such as:
            - Images: dimensions, format, EXIF data
            - Videos: duration, resolution, codec info
            - PDFs: number of pages, author, title
        Enriches the job record for downstream processing.
        In production, replace with a real metadata extraction service.
        Args:
            job_id (str): The job identifier.
        """
        print(f"[Worker:extract_metadata] Job {state['job_id']} extracting metadata...")  # ✅ Use dict access
        await asyncio.sleep(0.5)
        state["status"] = "metadata_extracted"  # ✅ Use dict access
        state["step"] = "extract_metadata"  # ✅ Use dict access
        state["updated_at"] = datetime.utcnow().isoformat()  # ✅ Use dict access
        state["metadata"] = {"dummy": "metadata"}  # Simulate extraction  # ✅ Use dict access
        print(
            f"[Worker:extract_metadata] Job {state['job_id']} metadata extraction done. State: {state}")  # ✅ Use dict access
        return state

    async def _worker_route_workflow(self, state: MyState) -> MyState:
        """
        Simulated routing worker.
        Uses content_type from IngestionJobRequest to decide the workflow branch (image, video, pdf).
        In production, replace with a real routing service or logic.
        Args:
            job_id (str): The job identifier.
        Returns:
            str: The selected branch (image, video, pdf).
        """
        print(f"[Worker:route_workflow] Job {state['job_id']} routing workflow...")  # ✅ Use dict access
        await asyncio.sleep(0.2)
        # Simulate branch selection based on content_type
        content_type = state["content_type"]  # ✅ Use dict access
        if "image" in content_type:
            state["branch"] = "image_branch"  # ✅ Use dict access
        elif "video" in content_type:
            state["branch"] = "video_branch"  # ✅ Use dict access
        elif "pdf" in content_type:
            state["branch"] = "pdf_branch"  # ✅ Use dict access
        else:
            state["branch"] = "image_branch"  # ✅ Use dict access

        state["status"] = f"routed_to_{state['branch']}_branch"  # ✅ Use dict access
        state["step"] = "route_workflow"  # ✅ Use dict access
        state["updated_at"] = datetime.utcnow().isoformat()  # ✅ Use dict access
        print(
            f"[Worker:route_workflow] Job {state['job_id']} routed to {state['branch']} branch. State: {state}")  # ✅ Use dict access
        return state

    async def _worker_generate_thumbnails(self, state: MyState) -> MyState:
        """
        Simulated thumbnail generation worker for images.
        Uses enriched metadata (e.g., image dimensions) from previous extraction.
        In production, replace with a real thumbnail generation service.
        Args:
            job_id (str): The job identifier.
        """
        print(f"[Worker:generate_thumbnails] Job {state['job_id']} generating thumbnails...")  # ✅ Use dict access
        await asyncio.sleep(0.3)
        state["status"] = "thumbnails_generated"  # ✅ Use dict access
        state["step"] = "generate_thumbnails"  # ✅ Use dict access
        state["updated_at"] = datetime.utcnow().isoformat()  # ✅ Use dict access
        print(
            f"[Worker:generate_thumbnails] Job {state['job_id']} thumbnails done. State: {state}")  # ✅ Use dict access
        return state

    async def _worker_analyze_image_with_ai(self, state: MyState) -> MyState:
        """
        Simulated image analysis worker using AI for images.
        Uses enriched metadata and image file.
        In production, replace with a real AI image analysis service.
        Args:
            job_id (str): The job identifier.
        """
        print(f"[Worker:analyze_image_with_ai] Job {state['job_id']} analyzing image with AI...")  # ✅ Use dict access
        await asyncio.sleep(0.4)
        state["status"] = "image_analyzed"  # ✅ Use dict access
        state["step"] = "analyze_image_with_ai"  # ✅ Use dict access
        state["updated_at"] = datetime.utcnow().isoformat()  # ✅ Use dict access
        print(
            f"[Worker:analyze_image_with_ai] Job {state['job_id']} image analysis done. State: {state}")  # ✅ Use dict access
        return state

    async def _worker_extract_audio(self, state: MyState) -> MyState:
        """
        Simulated audio extraction worker for videos.
        Uses enriched metadata (e.g., video duration, codec info).
        In production, replace with a real audio extraction service.
        Args:
            job_id (str): The job identifier.
        """
        print(f"[Worker:extract_audio] Job {state['job_id']} extracting audio...")  # ✅ Use dict access
        await asyncio.sleep(0.3)
        state["status"] = "audio_extracted"  # ✅ Use dict access
        state["step"] = "extract_audio"  # ✅ Use dict access
        state["updated_at"] = datetime.utcnow().isoformat()  # ✅ Use dict access
        print(
            f"[Worker:extract_audio] Job {state['job_id']} audio extraction done. State: {state}")  # ✅ Use dict access
        return state

    async def _worker_transcribe_audio(self, state: MyState) -> MyState:
        """
        Simulated audio transcription worker for videos.
        Uses extracted audio from previous step.
        In production, replace with a real audio transcription service.
        Args:
            job_id (str): The job identifier.
        """
        print(f"[Worker:transcribe_audio] Job {state['job_id']} transcribing audio...")  # ✅ Use dict access
        await asyncio.sleep(0.4)
        state["status"] = "audio_transcribed"  # ✅ Use dict access
        state["step"] = "transcribe_audio"  # ✅ Use dict access
        state["updated_at"] = datetime.utcnow().isoformat()  # ✅ Use dict access
        print(
            f"[Worker:transcribe_audio] Job {state['job_id']} audio transcription done. State: {state}")  # ✅ Use dict access
        return state

    async def _worker_generate_video_summary(self, state: MyState) -> MyState:
        """
        Simulated video summary generation worker for videos.
        Uses transcribed audio and video metadata.
        In production, replace with a real video summary generation service.
        Args:
            job_id (str): The job identifier.
        """
        print(f"[Worker:generate_video_summary] Job {state['job_id']} generating video summary...")  # ✅ Use dict access
        await asyncio.sleep(0.4)
        state["status"] = "video_summary_generated"  # ✅ Use dict access
        state["step"] = "generate_video_summary"  # ✅ Use dict access
        state["updated_at"] = datetime.utcnow().isoformat()  # ✅ Use dict access
        print(
            f"[Worker:generate_video_summary] Job {state['job_id']} video summary done. State: {state}")  # ✅ Use dict access
        return state

    async def _worker_extract_text(self, state: MyState) -> MyState:
        """
        Simulated text extraction worker for PDFs.
        Uses enriched metadata (e.g., number of pages, author).
        In production, replace with a real PDF text extraction service.
        Args:
            job_id (str): The job identifier.
        """
        print(f"[Worker:extract_text] Job {state['job_id']} extracting text from PDF...")  # ✅ Use dict access
        await asyncio.sleep(0.3)
        state["status"] = "text_extracted"  # ✅ Use dict access
        state["step"] = "extract_text"  # ✅ Use dict access
        state["updated_at"] = datetime.utcnow().isoformat()  # ✅ Use dict access
        print(f"[Worker:extract_text] Job {state['job_id']} text extraction done. State: {state}")  # ✅ Use dict access
        return state

    async def _worker_summarize_document(self, state: MyState) -> MyState:
        """
        Simulated document summarization worker for PDFs.
        Uses extracted text and PDF metadata.
        In production, replace with a real document summarization service.
        Args:
            job_id (str): The job identifier.
        """
        print(f"[Worker:summarize_document] Job {state['job_id']} summarizing document...")  # ✅ Use dict access
        await asyncio.sleep(0.4)
        state["status"] = "document_summarized"  # ✅ Use dict access
        state["step"] = "summarize_document"  # ✅ Use dict access
        state["updated_at"] = datetime.utcnow().isoformat()  # ✅ Use dict access
        print(
            f"[Worker:summarize_document] Job {state['job_id']} document summary done. State: {state}")  # ✅ Use dict access
        return state

    def get_job(self, job_id: str) -> Optional[MyState]:
        """
        Returns the current state for a job.
        Args:
            job_id (str): The job identifier.
        Returns:
            MyState: Job state if found, else None.
        """
        return self.jobs.get(job_id)


orchestrator = WorkflowOrchestrator()


@app.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def submit_job(job: IngestionJobRequest, request: Request):
    """
    Submit a new job to the orchestrator via HTTP POST.
    Args:
        job (IngestionJobRequest): Job request from API Gateway.
        request (Request): FastAPI request object.
    Returns:
        dict: Job ID and status if accepted.
    Raises:
        HTTPException: If job_id already exists.
    """
    print(f"[Orchestrator] Received direct job submission for job_id: {job.job_id}")
    try:
        await orchestrator.submit_job(job)
    except ValueError as e:
        print(f"[Orchestrator] Duplicate job_id {job.job_id} received via HTTP. Skipping.")
        raise HTTPException(status_code=409, detail=str(e))
    return {"job_id": job.job_id, "status": "queued"}


@app.get("/jobs/{job_id}", status_code=status.HTTP_200_OK)
def get_job_status(job_id: str):
    """
    Returns the current status and metadata for a job.
    Args:
        job_id (str): The job identifier.
    Returns:
        IngestionJobStatusResponse: Job metadata if found.
    Raises:
        HTTPException: If job not found.
    """
    job = orchestrator.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    # Convert MyState (dict) to IngestionJobStatusResponse
    return IngestionJobStatusResponse(
        job_id=job["job_id"],  # ✅ Use dict access
        status=job["status"],  # ✅ Use dict access
        step=job["step"],  # ✅ Use dict access
        created_at=job["created_at"],  # ✅ Use dict access
        updated_at=job["updated_at"],  # ✅ Use dict access
        file_path=job["file_path"],  # ✅ Use dict access
        content_type=job["content_type"],  # ✅ Use dict access
        checksum_sha256=job["checksum_sha256"],  # ✅ Use dict access
        submitted_by=job["submitted_by"]  # ✅ Use dict access
    )


# ----------------------------------------------------------------------------------------------
# Redis listener to subscribe to command_queue and process JOB_CREATED events
# ----------------------------------------------------------------------------------------------
async def redis_listener():
    """
    Redis listener for JOB_CREATED events.
    Subscribes to the 'command_queue' channel and processes new jobs.
    Reconstructs jobs using IngestionJobRequest and submits them to the workflow orchestrator.
    Skips duplicate jobs.
    """
    pubsub = redis.pubsub()
    try:
        await pubsub.subscribe("command_queue")
        print("[Orchestrator] Listening for JOB_CREATED events on Redis...")
        async for message in pubsub.listen():
            if message["type"] == "message":
                event = json.loads(message["data"])
                if event.get("event") == "JOB_CREATED":
                    print(f"[Orchestrator] Received JOB_CREATED event for job_id: {event['job_id']}")
                    # Use IngestionJobRequest to reconstruct job from event
                    job = IngestionJobRequest(**{k: v for k, v in event.items() if k != "event"})
                    try:
                        await orchestrator.submit_job(job)
                    except ValueError:
                        print(f"[Orchestrator] Duplicate job_id {event['job_id']} received from Redis. Skipping.")
    except asyncio.CancelledError:
        await pubsub.unsubscribe("command_queue")
        await pubsub.close()
