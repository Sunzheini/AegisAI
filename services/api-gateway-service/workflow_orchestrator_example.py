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
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import asyncio
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from fastapi import FastAPI, HTTPException, status, Request

BASE_DIR = Path(__file__).resolve().parent

if os.path.exists(os.path.join(BASE_DIR, '.env')):
    load_dotenv()

# Conditional import for shared library usage ----------------------------------------------
USE_SHARED_LIB = os.getenv("USE_SHARED_LIB", False)
if USE_SHARED_LIB:
    from shared_lib.contracts.job_schemas import (
        IngestionJobRequest,
        IngestionJobStatusResponse,
        WorkflowGraphState,
    )
    from shared_lib.needs.INeedRedisManager import INeedRedisManagerInterface
    from shared_lib.needs.ResolveNeedsManager import ResolveNeedsManager
    from shared_lib.support.support_functions import resolve_file_path
    from shared_lib.logging_management.logging_manager import LoggingManager
    from shared_lib.custom_middleware.logging_middleware import EnhancedLoggingMiddleware
    from shared_lib.custom_middleware.error_middleware import ErrorMiddleware
else:
    from contracts.job_schemas import (
        IngestionJobRequest,
        IngestionJobStatusResponse,
        WorkflowGraphState,
    )
    from needs.INeedRedisManager import INeedRedisManagerInterface
    from needs.ResolveNeedsManager import ResolveNeedsManager
    from support.support_functions import resolve_file_path
    from logging_management.logging_manager import LoggingManager
    from custom_middleware.logging_middleware import EnhancedLoggingMiddleware
    from custom_middleware.error_middleware import ErrorMiddleware
# ------------------------------------------------------------------------------------------

from media_processing_worker_example import (
    generate_thumbnails_worker,
    extract_audio_worker,
    transcribe_audio_worker,
    generate_video_summary_worker,
)
from ai_worker_example import (
    analyze_image_with_ai_worker,
)

# Worker clients using Redis
from worker_clients.validation_worker_client import validate_file_worker_redis
from worker_clients.extract_metadata_worker_client import (
    extract_metadata_from_file_worker_redis,
)
from worker_clients.extract_text_worker_client import (
    extract_text_from_file_worker_redis,
)
from worker_clients.ai_worker_client import process_file_by_ai_worker_redis


USE_REDIS_LISTENER = os.getenv("USE_REDIS_LISTENER", "true").lower() == "true"


logger = LoggingManager.setup_logging(
    service_name="workflow-orchestrator",
    log_file_path="logs/workflow_orchestrator.log",
    log_level=logging.INFO,
)


# ToDo: fix load_dotenv() must be everywhere (it gave error in ingestion_views.py!)
# ToDo: Separate orchestrator
# ToDo: When moving Give the workflow orchestrator direct access to the storage via shared
#  folder, it is better to pass only the file path and metadata in the job request, not the
#  file content itself.
# ToDo: Move incl. tests to work there

# ToDo: AI Summarization Worker Service: integration with CustomLLM
# ToDo: Celery?
# ToDo: user stories use jira
# ToDo: pylint / black -> run on other pc -> review

# ToDO: AWS (OpenTelemetry?)


@asynccontextmanager
async def lifespan(app):
    """Lifespan context manager to start/stop Redis listener if enabled."""
    logger.info("Starting Workflow Orchestrator service...")

    # Create RedisManager instance
    from redis_management.redis_manager import RedisManager

    redis_manager = RedisManager()

    # Create orchestrator and inject RedisManager
    orchestrator = WorkflowOrchestrator()
    ResolveNeedsManager.resolve_needs(orchestrator)

    # Resolve ValidationWorkerClient dependency
    from worker_clients.validation_worker_client import validation_worker_client
    from worker_clients.extract_metadata_worker_client import (
        extract_metadata_worker_client,
    )
    from worker_clients.extract_text_worker_client import extract_text_worker_client
    from worker_clients.ai_worker_client import ai_worker_client

    ResolveNeedsManager.resolve_needs(validation_worker_client)
    ResolveNeedsManager.resolve_needs(extract_metadata_worker_client)
    ResolveNeedsManager.resolve_needs(extract_text_worker_client)
    ResolveNeedsManager.resolve_needs(ai_worker_client)

    # Store orchestrator in app.state so routes can access it
    app.state.orchestrator = orchestrator
    app.state.redis_manager = redis_manager
    app.state.validation_worker_client = validation_worker_client
    app.state.extract_metadata_worker_client = extract_metadata_worker_client
    app.state.extract_text_worker_client = extract_text_worker_client
    app.state.ai_worker_client = ai_worker_client

    if USE_REDIS_LISTENER:
        print("[Orchestrator] Redis listener mode enabled. Starting Redis listener...")
        logger.info("Redis listener mode enabled. Starting Redis listener...")
        # Pass orchestrator to redis_listener
        task = asyncio.create_task(redis_listener(orchestrator))
        yield
        print("[Orchestrator] Shutting down Redis listener.")
        logger.info("Shutting down Redis listener.")
        task.cancel()

        # Close RedisManager connection - NOW IT EXISTS!
        await app.state.redis_manager.close()
    else:
        print(
            "[Orchestrator] Redis listener mode disabled. "
            "Only direct HTTP submission will be processed."
        )
        logger.info(
            "Redis listener mode disabled. Only direct HTTP submission will be processed."
        )
        yield


app = FastAPI(title="Workflow Orchestrator Example", lifespan=lifespan)
app.add_middleware(ErrorMiddleware)
app.add_middleware(EnhancedLoggingMiddleware, service_name="workflow-orchestrator")


class WorkflowOrchestrator(INeedRedisManagerInterface):
    """
    Orchestrates ingestion jobs using a workflow graph.
    Each step is a simulated async worker.
    Replace with real workers/cloud services for production.
    """

    def __init__(self):
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger("workflow-orchestrator")
        # Define workflow graph structure
        self.graph = self._build_graph()

    def _build_graph(self):
        print("[Orchestrator] Building workflow graph...")
        # Use LangGraph StateGraph if available, else use dict
        if StateGraph:
            print(
                "[Orchestrator] Using LangGraph StateGraph with state_schema=MyState."
            )
            graph = StateGraph(state_schema=WorkflowGraphState)

            # Nodes
            graph.add_node("validate_file", validate_file_worker_redis)
            graph.add_node("extract_metadata", extract_metadata_from_file_worker_redis)
            graph.add_node("route_workflow", self._worker_route_workflow)

            # Image branch
            graph.add_node(
                "generate_thumbnails", generate_thumbnails_worker
            )  # placeholder
            graph.add_node(
                "analyze_image_with_ai", analyze_image_with_ai_worker
            )  # placeholder

            # Video branch
            graph.add_node("extract_audio", extract_audio_worker)  # placeholder
            graph.add_node("transcribe_audio", transcribe_audio_worker)  # placeholder
            graph.add_node(
                "generate_video_summary", generate_video_summary_worker
            )  # placeholder

            # PDF branch
            graph.add_node("extract_text", extract_text_from_file_worker_redis)
            graph.add_node("summarize_document", process_file_by_ai_worker_redis)
            print("[Orchestrator] Added all nodes to graph.")

            # Conditional edge after validation: if failed, go to END
            def after_validation(state: WorkflowGraphState):
                if state.get("status") == "failed":
                    return "END"
                return "extract_metadata"

            graph.add_conditional_edges(
                "validate_file",
                after_validation,
                {"END": END, "extract_metadata": "extract_metadata"},
            )

            graph.add_edge("extract_metadata", "route_workflow")
            print("[Orchestrator] Added main edges.")

            # Conditional routing based on content type
            def route_workflow(state: WorkflowGraphState):
                return state["branch"]

            graph.add_conditional_edges(
                "route_workflow",
                route_workflow,
                {
                    "image_branch": "generate_thumbnails",
                    "video_branch": "extract_audio",
                    "pdf_branch": "extract_text",
                },
            )

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

            # Add visualization to see graph
            try:
                compiled_graph.get_graph().draw_mermaid_png(
                    output_file_path="workflow_graph.png"
                )
                print(
                    "[Orchestrator] Workflow graph visualization saved to workflow_graph.png"
                )
            # The visualization code could fail for various reasons (e.g., file I/O errors,
            # missing dependencies, graph rendering issues)
            except Exception as e:
                print(f"[Orchestrator] Could not generate graph visualization: {e}")

            return compiled_graph

        else:
            print(
                "[Orchestrator] LangGraph not available, using fallback graph structure."
            )
            return {
                "nodes": ["validate_file", "extract_metadata", "route_workflow"],
                "branches": {
                    "image": ["generate_thumbnails", "analyze_image_with_ai"],
                    "video": [
                        "extract_audio",
                        "transcribe_audio",
                        "generate_video_summary",
                    ],
                    "pdf": ["extract_text", "summarize_document"],
                },
            }

    async def submit_job(self, job: IngestionJobRequest):
        """
        Submit a new job to the orchestrator.
        Args:
            job (IngestionJobRequest): Job request from API Gateway.
        Raises:
            ValueError: If job_id already exists.
        """
        print(f"[Orchestrator] Received job submission: {job.job_id}")
        # Check Redis for existing job
        existing_state = await self.redis_manager.load_job_state_from_redis(job.job_id)
        if existing_state:
            print(f"[Orchestrator] Job {job.job_id} already exists!")
            raise ValueError("Job already exists")

        # Resolve file path once in orchestrator
        resolved_path = await resolve_file_path(job.file_path, job.job_id)

        print('---------------------------------------------------')
        print(f"[Orchestrator] Resolved file path: {resolved_path}")  # storage\raw\ce578975-20e7-43eb-b5f6-8a4cbc2a7c6e_P8052AH.pdf
        print('---------------------------------------------------')

        state = WorkflowGraphState(
            job_id=job.job_id,
            # file_path=job.file_path,
            file_path=resolved_path,
            content_type=job.content_type,
            checksum_sha256=job.checksum_sha256,
            submitted_by=job.submitted_by,
            status="queued",
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            step="queued",
            branch="",  # will be set by route_workflow
            metadata=None,
        )

        self.jobs[job.job_id] = state
        await self.redis_manager.save_job_state_to_redis(job.job_id, state)
        print(f"[Orchestrator] Job {job.job_id} queued. Initial state: {state}")
        print(f"Jon content type: {job.content_type}")

        # Start workflow in background
        asyncio.create_task(self._run_workflow(job.job_id))

    async def _run_workflow(self, job_id: str) -> None:
        """
        Runs the workflow for a given job_id.
        Updates job state in self.jobs and Redis.
        Args:
            job_id (str): The job identifier.
        ️ Note: This runs in the background as a separate task.
        """
        try:
            state = self.jobs[job_id]
            print(f"[DEBUG] Before graph.ainvoke: {state}")
            final_state = await self.graph.ainvoke(state)  # Call the graph
            self.jobs[job_id] = final_state
            await self.redis_manager.save_job_state_to_redis(job_id, final_state)

        # Can raise various exceptions, including those from async workers, graph logic, or deps
        except Exception as e:
            # Get the current state and update it
            state = self.jobs[job_id]
            state["status"] = "failed"
            current_step = state.get("step", "unknown")
            state["step"] = f"failed_at_{current_step}"
            state["updated_at"] = datetime.now(timezone.utc).isoformat()
            self.jobs[job_id] = state
            await self.redis_manager.save_job_state_to_redis(job_id, state)
            self.logger.error("Workflow failed for job %s: %s", job_id, e)

    async def get_job(self, job_id: str) -> Optional[WorkflowGraphState]:
        """Get job state from Redis as MyState."""
        return await self.redis_manager.load_job_state_from_redis(job_id)

    @staticmethod
    async def _worker_route_workflow(state: WorkflowGraphState) -> WorkflowGraphState:
        """
        Simulated routing worker.
        Uses content_type from IngestionJobRequest to decide the workflow branch
        (image, video, pdf).
        In production, replace with a real routing service or logic.
        Args:
            job_id (str): The job identifier.
        Returns:
            str: The selected branch (image, video, pdf).
        """
        print(f"[Worker:route_workflow] Job {state['job_id']} routing workflow...")
        await asyncio.sleep(0.2)

        # Simulate branch selection based on content_type
        content_type = state["content_type"]
        if "image" in content_type:
            state["branch"] = "image_branch"
        elif "video" in content_type:
            state["branch"] = "video_branch"
        elif "pdf" in content_type:
            state["branch"] = "pdf_branch"
        else:
            state["branch"] = "image_branch"

        state["status"] = f"routed_to_{state['branch']}"
        state["step"] = "route_workflow"
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        print(
            f"[Worker:route_workflow] Job {state['job_id']} routed to {state['branch']} "
            f"branch. State: {state}"
        )
        return state


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
    orchestrator = request.app.state.orchestrator  # Get from app.state
    print(f"[Orchestrator] Received direct job submission for job_id: {job.job_id}")
    try:
        await orchestrator.submit_job(job)
    except ValueError as e:
        print(
            f"[Orchestrator] Duplicate job_id {job.job_id} received via HTTP. Skipping."
        )
        raise HTTPException(status_code=409, detail=str(e)) from e
    return {"job_id": job.job_id, "status": "queued"}


@app.get(
    "/jobs/{job_id}",
    status_code=status.HTTP_200_OK,
    response_model=IngestionJobStatusResponse,
)
async def get_job_status(job_id: str, request: Request):
    """
    The frontend polls this endpoint to get job status updates.
    Returns the current status and metadata for a job.
    Args:
        job_id (str): The job identifier.
        request (Request): FastAPI request object.
    Returns:
        IngestionJobStatusResponse: Job metadata if found.
    Raises:
        HTTPException: If job not found.
    """
    orchestrator = request.app.state.orchestrator  # Get from app.state
    job = await orchestrator.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return IngestionJobStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        step=job["step"],
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        file_path=job["file_path"],
        content_type=job["content_type"],
        checksum_sha256=job["checksum_sha256"],
        submitted_by=job.get("submitted_by"),
    )


# ----------------------------------------------------------------------------------------------
# Redis listener to subscribe to command_queue and process JOB_CREATED events
# ----------------------------------------------------------------------------------------------
async def redis_listener(orchestrator_instance):
    """
    Redis listener for JOB_CREATED events.
    Subscribes to the 'command_queue' channel and processes new jobs.
    Reconstructs jobs using IngestionJobRequest and submits them to the workflow orchestrator.
    Skips duplicate jobs.
    """
    pubsub = await orchestrator_instance.redis_manager.get_pubsub()
    try:
        await pubsub.subscribe("command_queue")
        print("[Orchestrator] Listening for JOB_CREATED events on Redis...")
        async for message in pubsub.listen():
            if message["type"] == "message":
                event = json.loads(message["data"])
                if event.get("event") == "JOB_CREATED":
                    print(
                        f"[Orchestrator] Received JOB_CREATED event for job_id: {event['job_id']}"
                    )

                    # Use IngestionJobRequest to reconstruct job from event
                    job = IngestionJobRequest(
                        **{k: v for k, v in event.items() if k != "event"}
                    )
                    try:
                        await orchestrator_instance.submit_job(job)
                    except ValueError:
                        print(
                            f"[Orchestrator] Duplicate job_id {event['job_id']} received from "
                            f"Redis. Skipping."
                        )
    except asyncio.CancelledError:
        await pubsub.unsubscribe("command_queue")
