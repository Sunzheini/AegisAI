import io
import os
import time
import uuid
import threading
from typing import List, Tuple
import pytest
import requests
from unittest.mock import patch

from views.ingestion_views import IngestionViewsManager as IVM


def _cleanup_storage():
    """Remove all files from storage subdirectories."""
    storage_root = os.path.abspath(os.path.join(os.getcwd(), "storage"))
    for sub in ("raw", "processed", "transcoded"):
        d = os.path.join(storage_root, sub)
        if os.path.isdir(d):
            for name in os.listdir(d):
                try:
                    os.remove(os.path.join(d, name))
                except OSError:
                    pass


@pytest.fixture(autouse=True)
def clean_ingestion_state(tmp_path):
    """Clear in-memory stores and storage files between tests."""
    IVM.jobs_store.clear()
    IVM.assets_store.clear()
    _cleanup_storage()
    yield
    _cleanup_storage()


@pytest.fixture
def orchestrator_env(monkeypatch):
    """Set environment variables for orchestrator mode."""
    monkeypatch.setenv("USE_ORCHESTRATOR", "true")
    monkeypatch.setenv("ORCHESTRATOR_URL", "http://testserver/orchestrator/jobs")
    yield
    monkeypatch.delenv("USE_ORCHESTRATOR", raising=False)
    monkeypatch.delenv("ORCHESTRATOR_URL", raising=False)


def test_upload_and_processing_success(client, auth_headers):
    """Test successful upload and processing of a valid PNG file."""
    content = b"\x89PNG\r\n\x1a\n" + b"0" * 128
    files = {"file": ("tiny.png", io.BytesIO(content), "image/png")}

    response = client.post("/v1/upload", files=files, headers=auth_headers)
    assert response.status_code == 202, response.text
    body = response.json()
    assert "job_id" in body
    job_id = body["job_id"]

    # Poll job status until completed
    status = None
    asset_id = None
    deadline = time.time() + 5.0
    while time.time() < deadline:
        job_response = client.get(f"/v1/jobs/{job_id}", headers=auth_headers)
        assert job_response.status_code == 200, job_response.text
        job = job_response.json()
        status = job.get("status")
        if status == "completed":
            asset_id = job.get("asset_id")
            break
        elif status == "failed":
            pytest.fail(f"Job failed unexpectedly: {job}")
        time.sleep(0.05)

    assert status == "completed", f"Job not completed, last status: {status}"
    assert asset_id, "Asset ID not set on completed job"

    # Fetch asset metadata
    asset_response = client.get(f"/v1/assets/{asset_id}", headers=auth_headers)
    assert asset_response.status_code == 200, asset_response.text
    asset = asset_response.json()
    assert asset["asset_id"] == asset_id
    assert asset["content_type"] == "image/png"
    assert asset["size_bytes"] > 0
    assert os.path.exists(asset["processed_path"]) is True


def test_upload_requires_auth(client):
    """Test that upload endpoint requires authentication."""
    content = b"TEST" * 10
    files = {"file": ("tiny.png", io.BytesIO(content), "image/png")}
    response = client.post("/v1/upload", files=files)
    assert response.status_code == 401


def test_job_and_asset_require_auth(client):
    """Test that job and asset endpoints require authentication."""
    job_id = str(uuid.uuid4())
    asset_id = str(uuid.uuid4())
    job_response = client.get(f"/v1/jobs/{job_id}")
    asset_response = client.get(f"/v1/assets/{asset_id}")
    assert job_response.status_code == 401
    assert asset_response.status_code == 401


def test_unsupported_media_type(client, auth_headers):
    """Test upload of unsupported media type returns 415."""
    content = b"hello world"
    files = {"file": ("note.txt", io.BytesIO(content), "text/plain")}
    response = client.post("/v1/upload", files=files, headers=auth_headers)
    assert response.status_code == 415


def test_upload_too_large_with_monkeypatch(client, auth_headers, monkeypatch):
    """Test upload exceeding max size returns 413."""
    import views.ingestion_views as iv
    monkeypatch.setattr(iv, "MAX_UPLOAD_BYTES", 1024)
    big_content = b"A" * 2048
    files = {"file": ("big.png", io.BytesIO(big_content), "image/png")}
    response = client.post("/v1/upload", files=files, headers=auth_headers)
    assert response.status_code == 413


def test_job_and_asset_404(client, auth_headers):
    """Test 404 response for non-existent job and asset IDs."""
    bad_job = str(uuid.uuid4())
    bad_asset = str(uuid.uuid4())
    job_response = client.get(f"/v1/jobs/{bad_job}", headers=auth_headers)
    asset_response = client.get(f"/v1/assets/{bad_asset}", headers=auth_headers)
    assert job_response.status_code == 404
    assert asset_response.status_code == 404


def test_concurrent_uploads_show_parallel_processing(client, auth_headers, monkeypatch):
    """Test that multiple uploads are processed in parallel."""
    import views.ingestion_views as iv

    # Find the actual instance used by the app
    # This assumes the FastAPI app exposes the manager as app.state.ingestion_manager
    ingestion_manager = getattr(getattr(client.app, "state", None), "ingestion_manager", None)
    assert ingestion_manager is not None, "IngestionViewsManager instance not found in app.state.ingestion_manager"

    # Patch the class method so all instances use the instrumented version
    original_process = IVM._process_job
    lock = threading.Lock()
    counters = {"current": 0, "max": 0}

    async def instrumented_process(self, job_id: str):
        with lock:
            counters["current"] += 1
            counters["max"] = max(counters["max"], counters["current"])
        try:
            import asyncio
            await asyncio.sleep(0.3)
            return await original_process(self, job_id)
        finally:
            with lock:
                counters["current"] -= 1

    monkeypatch.setattr(IVM, "_process_job", instrumented_process)

    content = b"\x89PNG\r\n\x1a\n" + b"0" * 1024
    results: List[Tuple[int, dict]] = []
    results_lock = threading.Lock()

    def worker():
        files = {"file": ("tiny.png", io.BytesIO(content), "image/png")}
        response = client.post("/v1/upload", files=files, headers=auth_headers)
        with results_lock:
            status = response.status_code
            body = response.json() if status != 500 else {"error": response.text}
            results.append((status, body))

    threads = [threading.Thread(target=worker) for _ in range(3)]
    start = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.time() - start

    assert len(results) == 3
    assert all(status == 202 for status, _ in results), results
    job_ids = [body.get("job_id") for _, body in results]
    assert all(j is not None for j in job_ids)
    assert len(set(job_ids)) == 3

    for job_id in job_ids:
        job_response = client.get(f"/v1/jobs/{job_id}", headers=auth_headers)
        assert job_response.status_code == 200
        assert job_response.json().get("status") == "completed"

    assert counters["max"] >= 2, f"Observed max concurrency: {counters['max']}"
    assert elapsed < 1.4, f"Took too long, likely serialized: {elapsed:.3f}s"


def test_upload_submits_to_orchestrator(client, auth_headers, orchestrator_env):
    """Test that upload submits job to orchestrator and returns correct status."""
    content = b"\x89PNG\r\n\x1a\n" + b"0" * 128
    files = {"file": ("tiny.png", io.BytesIO(content), "image/png")}
    job_id_holder = {}

    def fake_post(url, json, timeout):
        assert url.endswith("/orchestrator/jobs")
        assert json["file_path"].endswith("tiny.png")
        job_id_holder["job_id"] = json["job_id"]
        class Resp:
            def raise_for_status(self):
                pass
        return Resp()

    with patch("requests.post", side_effect=fake_post):
        response = client.post("/v1/upload", files=files, headers=auth_headers)
        assert response.status_code == 202, response.text
        body = response.json()
        assert body["status"] == "submitted_to_orchestrator"
        assert "job_id" in body
        assert body["job_id"] == job_id_holder["job_id"]


def test_upload_orchestrator_error(client, auth_headers, orchestrator_env):
    """Test upload returns error if orchestrator is unavailable."""
    content = b"\x89PNG\r\n\x1a\n" + b"0" * 128
    files = {"file": ("tiny.png", io.BytesIO(content), "image/png")}

    def fake_post(url, json, timeout):
        raise requests.ConnectionError("orchestrator down")

    with patch("requests.post", side_effect=fake_post):
        response = client.post("/v1/upload", files=files, headers=auth_headers)
        assert response.status_code == 502
        assert "Failed to submit job to orchestrator" in response.text

