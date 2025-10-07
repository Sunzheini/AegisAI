"""
Shared job schemas for API Gateway and Workflow Orchestrator
-----------------------------------------------------------
Defines Pydantic models for ingestion job requests and responses.
Import and use these models in both services to ensure a consistent contract.
"""
from typing import Optional

from pydantic import BaseModel


class IngestionJobRequest(BaseModel):
    """
    Schema for ingestion job requests sent from the API Gateway to the Workflow Orchestrator.
    """
    job_id: str
    file_path: str
    content_type: str
    checksum_sha256: str
    submitted_by: Optional[str] = None


class IngestionJobStatusResponse(BaseModel):
    """
    Schema for job status responses from the Workflow Orchestrator to API Gateway or frontend.
    """
    job_id: str
    status: str
    step: str
    created_at: str
    updated_at: str
    file_path: str
    content_type: str
    checksum_sha256: str
    submitted_by: Optional[str] = None
