import io
import os
import time
import uuid
import pytest

from views.ingestion_views import IngestionViewsManager as IVM


# --------------------------------------------------------------------------------------
# Module-scoped/auto-used fixtures specific to ingestion tests
# --------------------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def clean_ingestion_state(tmp_path):
    # Clear in-memory stores between tests to avoid cross-test interference
    IVM.jobs_store.clear()
    IVM.assets_store.clear()

    # Clean up any files created in storage directories if they exist
    storage_root = os.path.abspath(os.path.join(os.getcwd(), "storage"))
    for sub in ("raw", "processed", "transcoded"):
        d = os.path.join(storage_root, sub)
        if os.path.isdir(d):
            for name in os.listdir(d):
                try:
                    os.remove(os.path.join(d, name))
                except OSError:
                    # best-effort cleanup only
                    pass
    yield
    # Post-test cleanup (same best-effort)
    for sub in ("raw", "processed", "transcoded"):
        d = os.path.join(storage_root, sub)
        if os.path.isdir(d):
            for name in os.listdir(d):
                try:
                    os.remove(os.path.join(d, name))
                except OSError:
                    pass


# --------------------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------------------
def test_upload_and_processing_success(client, auth_headers):
    # Prepare a tiny PNG-like payload (content type is what matters for validation here)
    content = b"\x89PNG\r\n\x1a\n" + b"0" * 128
    files = {"file": ("tiny.png", io.BytesIO(content), "image/png")}

    # Upload
    r = client.post("/v1/upload", files=files, headers=auth_headers)
    assert r.status_code == 202, r.text
    body = r.json()
    assert "job_id" in body
    job_id = body["job_id"]

    # Poll job status until completed (background processing simulates ~0.2s)
    status = None
    asset_id = None
    deadline = time.time() + 5.0  # up to 5 seconds
    while time.time() < deadline:
        jr = client.get(f"/v1/jobs/{job_id}", headers=auth_headers)
        assert jr.status_code == 200, jr.text
        j = jr.json()
        status = j.get("status")
        if status == "completed":
            asset_id = j.get("asset_id")
            break
        elif status == "failed":
            pytest.fail(f"Job failed unexpectedly: {j}")
        time.sleep(0.05)

    assert status == "completed", f"Job not completed, last status: {status}"
    assert asset_id, "Asset ID not set on completed job"

    # Fetch asset metadata
    ar = client.get(f"/v1/assets/{asset_id}", headers=auth_headers)
    assert ar.status_code == 200, ar.text
    asset = ar.json()
    assert asset["asset_id"] == asset_id
    assert asset["content_type"] == "image/png"
    assert asset["size_bytes"] > 0
    # Check that processed file path exists
    assert os.path.exists(asset["processed_path"]) is True


def test_upload_requires_auth(client):
    content = b"TEST" * 10
    files = {"file": ("tiny.png", io.BytesIO(content), "image/png")}
    r = client.post("/v1/upload", files=files)
    assert r.status_code == 401


def test_job_and_asset_require_auth(client):
    # random ids without auth
    r1 = client.get(f"/v1/jobs/{uuid.uuid4()}")
    r2 = client.get(f"/v1/assets/{uuid.uuid4()}")
    assert r1.status_code == 401
    assert r2.status_code == 401


def test_unsupported_media_type(client, auth_headers):
    content = b"hello world"
    files = {"file": ("note.txt", io.BytesIO(content), "text/plain")}
    r = client.post("/v1/upload", files=files, headers=auth_headers)
    assert r.status_code == 415


def test_upload_too_large_with_monkeypatch(client, auth_headers, monkeypatch):
    # Reduce the local max upload size to keep the test fast, then go over that limit
    import views.ingestion_views as iv
    monkeypatch.setattr(iv, "MAX_UPLOAD_BYTES", 1024)

    big_content = b"A" * 2048
    files = {"file": ("big.png", io.BytesIO(big_content), "image/png")}

    r = client.post("/v1/upload", files=files, headers=auth_headers)
    assert r.status_code == 413


def test_job_and_asset_404(client, auth_headers):
    bad_job = str(uuid.uuid4())
    bad_asset = str(uuid.uuid4())

    rj = client.get(f"/v1/jobs/{bad_job}", headers=auth_headers)
    ra = client.get(f"/v1/assets/{bad_asset}", headers=auth_headers)
    assert rj.status_code == 404
    assert ra.status_code == 404
