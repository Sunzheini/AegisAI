"""
Tests for Workflow Orchestrator Service
---------------------------------------
Covers job submission, status polling, error handling, and response model validation.
"""
from fastapi.testclient import TestClient
from main import app
from contracts.job_schemas import IngestionJobStatusResponse
import uuid

client = TestClient(app)

def test_submit_and_poll_job():
    job_id = str(uuid.uuid4())
    payload = {
        "job_id": job_id,
        "file_path": f"storage/raw/{job_id}_test.pdf",
        "content_type": "application/pdf",
        "checksum_sha256": "dummychecksum",
        "submitted_by": "TestUser"
    }
    # Submit job
    resp = client.post("/jobs", json=payload)
    assert resp.status_code == 202
    assert resp.json()["job_id"] == job_id
    # Poll job status
    resp2 = client.get(f"/jobs/{job_id}")
    assert resp2.status_code == 200
    job_status = IngestionJobStatusResponse(**resp2.json())
    assert job_status.job_id == job_id
    assert job_status.status in ["queued", "validate_in_progress", "process_in_progress", "transcode_in_progress", "completed"]
    assert job_status.file_path == payload["file_path"]
    assert job_status.content_type == payload["content_type"]
    assert job_status.submitted_by == payload["submitted_by"]


def test_duplicate_job_submission():
    job_id = str(uuid.uuid4())
    payload = {
        "job_id": job_id,
        "file_path": f"storage/raw/{job_id}_test.pdf",
        "content_type": "application/pdf",
        "checksum_sha256": "dummychecksum",
        "submitted_by": "TestUser"
    }
    resp1 = client.post("/jobs", json=payload)
    assert resp1.status_code == 202
    resp2 = client.post("/jobs", json=payload)
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"]


def test_job_not_found():
    fake_job_id = str(uuid.uuid4())
    resp = client.get(f"/jobs/{fake_job_id}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Job not found"
