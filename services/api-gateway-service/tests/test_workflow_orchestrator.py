# In your test file
import uuid

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from workflow_orchestrator_example import app, WorkflowOrchestrator


@pytest.fixture
def client():
    # Mock the orchestrator and redis_manager
    mock_orchestrator = AsyncMock(spec=WorkflowOrchestrator)
    mock_orchestrator.submit_job = AsyncMock()
    mock_orchestrator.get_job = AsyncMock()

    # Create test client and patch app.state
    with TestClient(app) as test_client:
        # Patch app.state.orchestrator for the test
        test_client.app.state.orchestrator = mock_orchestrator
        yield test_client


def test_submit_and_poll_job(client):
    job_id = str(uuid.uuid4())
    payload = {
        "job_id": job_id,
        "file_path": f"storage/raw/{job_id}_test.pdf",
        "content_type": "application/pdf",
        "checksum_sha256": "dummychecksum",
        "submitted_by": "TestUser",
    }

    # Mock the orchestrator responses
    client.app.state.orchestrator.submit_job.return_value = None
    client.app.state.orchestrator.get_job.return_value = {
        "job_id": job_id,
        "status": "queued",
        "step": "queued",
        "created_at": "2023-01-01T00:00:00Z",
        "updated_at": "2023-01-01T00:00:00Z",
        "file_path": payload["file_path"],
        "content_type": payload["content_type"],
        "checksum_sha256": payload["checksum_sha256"],
        "submitted_by": payload["submitted_by"],
    }

    # Submit job
    resp = client.post("/jobs", json=payload)
    assert resp.status_code == 202
    assert resp.json()["job_id"] == job_id

    # Verify submit_job was called
    client.app.state.orchestrator.submit_job.assert_called_once()

    # Poll job status
    resp2 = client.get(f"/jobs/{job_id}")
    assert resp2.status_code == 200

    # Verify get_job was called
    client.app.state.orchestrator.get_job.assert_called_once_with(job_id)


def test_duplicate_job_submission(client):
    job_id = str(uuid.uuid4())
    payload = {
        "job_id": job_id,
        "file_path": f"storage/raw/{job_id}_test.pdf",
        "content_type": "application/pdf",
        "checksum_sha256": "dummychecksum",
        "submitted_by": "TestUser",
    }

    # Mock duplicate job error
    from fastapi import HTTPException

    client.app.state.orchestrator.submit_job.side_effect = ValueError(
        "Job already exists"
    )

    resp1 = client.post("/jobs", json=payload)
    assert resp1.status_code == 409
    assert "already exists" in resp1.json()["detail"]


def test_job_not_found(client):
    fake_job_id = str(uuid.uuid4())

    # Mock job not found
    client.app.state.orchestrator.get_job.return_value = None

    resp = client.get(f"/jobs/{fake_job_id}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Job not found"
