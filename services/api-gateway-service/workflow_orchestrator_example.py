"""
Example Workflow Orchestrator Service
-------------------------------------
This is a minimal FastAPI-based service that simulates a workflow orchestrator for ingestion jobs.

- Receives job requests from the API Gateway (via POST /jobs)
- Stores jobs in memory and simulates processing
- Intended for local development and integration testing

To run:
    uvicorn workflow_orchestrator_example:app --reload --port 9000

In production, this service would:
    - Manage job state and orchestration
    - Trigger processing steps (e.g., transcoding, analysis)
    - Integrate with cloud services (S3, Lambda, etc.)
"""

from fastapi import FastAPI, HTTPException, status, Request
from contracts.job_schemas import IngestionJobRequest
from typing import Dict, Any
from datetime import datetime
import asyncio

app = FastAPI(title="Workflow Orchestrator Example")

# In-memory job store for demonstration
jobs: Dict[str, Dict[str, Any]] = {}

@app.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def submit_job(job: IngestionJobRequest, request: Request):
    """
    Accepts a new ingestion job from the API Gateway and simulates orchestration.
    Expects a payload matching support.job_schemas.IngestionJobRequest.
    """
    if job.job_id in jobs:
        raise HTTPException(status_code=409, detail="Job already exists")

    jobs[job.job_id] = {
        "job_id": job.job_id,
        "file_path": job.file_path,
        "content_type": job.content_type,
        "checksum_sha256": job.checksum_sha256,
        "submitted_by": job.submitted_by,
        "status": "queued",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }

    # Simulate async orchestration (e.g., start workflow in background)
    asyncio.create_task(simulate_processing(job.job_id))
    return {"job_id": job.job_id, "status": "queued"}

@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """
    Returns the status of a submitted job.
    """
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

async def simulate_processing(job_id: str):
    """
    Simulates job processing by updating job status after a delay.
    """
    await asyncio.sleep(1.0)  # Simulate processing time
    if job_id in jobs:
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()
