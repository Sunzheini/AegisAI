"""
Workflow Orchestrator Example with LangGraph
-------------------------------------------
This service orchestrates ingestion jobs using a workflow graph (LangGraph).
Each job passes through simulated steps: validation, processing, transcoding.

- Modular design for easy migration to a separate project or AWS.
- All workflow logic is encapsulated in the WorkflowOrchestrator class.
- Endpoints: POST /jobs (submit job), GET /jobs/{job_id} (poll status)

To run:
    uvicorn workflow_orchestrator_example:app --reload --port 9000

Future AWS migration:
    - Replace in-memory stores with S3/DynamoDB
    - Replace simulated workers with Lambda/Step Functions
"""


# ToDo: continue
"""
Impelement Redis using the new chat here

When you move test_workflow_orchestrator.py 
to a new project, you do not need to change anything in your current project for it to continue working. The existing 
API Gateway and ingestion tests (test_ingestion.py and others) will remain valid and functional. However, in the new project:
    You must ensure that the new project includes the orchestrator service code (workflow_orchestrator_example.py) and the shared job schema models (contracts/job_schemas.py).
    You may need to update import paths in test_workflow_orchestrator.py to match the new project structure (e.g., how you import the orchestrator app and job schemas).
    If you change the orchestrator API or job schema in the new project, you should update the tests there accordingly.

If you want to move to real workers, you can refactor each worker method to send jobs to 
external services (e.g., via HTTP, message queue, or cloud). The orchestrator is now modular 
and ready for further extension or migration.
"""
import os
import json
from typing import Dict, Any
from datetime import datetime
import asyncio
import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, status, Request

from contracts.job_schemas import IngestionJobRequest, IngestionJobStatusResponse


REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/2")
redis = aioredis.from_url(REDIS_URL, decode_responses=True)


# LangGraph imports (simulate for now)
try:
    from langgraph.graph import StateGraph, WorkflowExecutor
except ImportError:
    StateGraph = None
    WorkflowExecutor = None


USE_REDIS_LISTENER = os.getenv("USE_REDIS_LISTENER", "true").lower() == "true"


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


class WorkflowOrchestrator:
    """
    Orchestrates ingestion jobs using a workflow graph.
    Each step is a simulated async worker.
    Replace with real workers/cloud services for production.

    Attributes:
        jobs (Dict[str, Dict[str, Any]]): In-memory job store.
        logger (logging.Logger): Logger for orchestrator events.
    """
    def __init__(self):
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger("orchestrator")

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
        job_record = {
            "job_id": job.job_id,
            "file_path": job.file_path,
            "content_type": job.content_type,
            "checksum_sha256": job.checksum_sha256,
            "submitted_by": job.submitted_by,
            "status": "queued",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "step": "queued",
        }
        self.jobs[job.job_id] = job_record
        print(f"[Orchestrator] Job {job.job_id} queued.")
        # Start workflow in background
        asyncio.create_task(self._run_workflow(job.job_id))

    async def _run_workflow(self, job_id: str):
        """
        Simulates a workflow with three steps, each as a separate worker function.
        In production, these would be separate services or processes.
        Args:
            job_id (str): The job identifier.
        """
        print(f"[Orchestrator] Starting workflow for job {job_id}.")
        await self._worker_validate(job_id)
        await self._worker_process(job_id)
        await self._worker_transcode(job_id)
        self.jobs[job_id]["status"] = "completed"
        self.jobs[job_id]["step"] = "done"
        self.jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()
        print(f"[Orchestrator] Job {job_id} completed.")

    async def _worker_validate(self, job_id: str):
        """
        Simulated validation worker.
        In production, replace with a real validation service.
        Args:
            job_id (str): The job identifier.
        """
        print(f"[Worker:validate] Job {job_id} validating...")
        await asyncio.sleep(0.5)
        self.jobs[job_id]["status"] = "validate_in_progress"
        self.jobs[job_id]["step"] = "validate"
        self.jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()
        print(f"[Worker:validate] Job {job_id} validation done.")

    async def _worker_process(self, job_id: str):
        """
        Simulated processing worker.
        In production, replace with a real processing service.
        Args:
            job_id (str): The job identifier.
        """
        print(f"[Worker:process] Job {job_id} processing...")
        await asyncio.sleep(0.5)
        self.jobs[job_id]["status"] = "process_in_progress"
        self.jobs[job_id]["step"] = "process"
        self.jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()
        print(f"[Worker:process] Job {job_id} processing done.")

    async def _worker_transcode(self, job_id: str):
        """
        Simulated transcoding worker.
        In production, replace with a real transcoding service.
        Args:
            job_id (str): The job identifier.
        """
        print(f"[Worker:transcode] Job {job_id} transcoding...")
        await asyncio.sleep(0.5)
        self.jobs[job_id]["status"] = "transcode_in_progress"
        self.jobs[job_id]["step"] = "transcode"
        self.jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()
        print(f"[Worker:transcode] Job {job_id} transcoding done.")

    def get_job(self, job_id: str) -> IngestionJobStatusResponse:
        """
        Retrieve job metadata and status as a response model.
        Args:
            job_id (str): The job identifier.
        Returns:
            IngestionJobStatusResponse: Job metadata or None if not found.
        """
        job = self.jobs.get(job_id)
        if not job:
            return None
        return IngestionJobStatusResponse(**job)


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
    return job


# ----------------------------------------------------------------------------------------------
# Redis listener to subscribe to command_queue and process JOB_CREATED events
# ----------------------------------------------------------------------------------------------
async def redis_listener():
    pubsub = redis.pubsub()
    await pubsub.subscribe("command_queue")
    print("[Orchestrator] Listening for JOB_CREATED events on Redis...")
    async for message in pubsub.listen():
        if message["type"] == "message":
            event = json.loads(message["data"])
            if event.get("event") == "JOB_CREATED":
                print(f"[Orchestrator] Received JOB_CREATED event for job_id: {event['job_id']}")
                # Convert event dict to IngestionJobRequest
                job = IngestionJobRequest(
                    job_id=event["job_id"],
                    file_path=event.get("filename", ""),
                    content_type="unknown",  # Adjust if available
                    checksum_sha256="unknown",  # Adjust if available
                    submitted_by=event.get("submitted_by", ""),
                )
                try:
                    await orchestrator.submit_job(job)
                except ValueError:
                    print(f"[Orchestrator] Duplicate job_id {event['job_id']} received from Redis. Skipping.")
