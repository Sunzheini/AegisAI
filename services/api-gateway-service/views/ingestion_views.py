from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Path
from starlette import status as H
from typing import Dict, Any
import uuid
import os
import asyncio
import hashlib
from datetime import datetime

from routers.security import auth_required


STORAGE_ROOT = os.path.abspath(os.path.join(os.getcwd(), "storage"))
RAW_DIR = os.path.join(STORAGE_ROOT, "raw")
PROCESSED_DIR = os.path.join(STORAGE_ROOT, "processed")
TRANSCODED_DIR = os.path.join(STORAGE_ROOT, "transcoded")

ALLOWED_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "video/mp4",
    "application/pdf",
}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


def _ensure_dirs():
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(TRANSCODED_DIR, exist_ok=True)


def _sanitize_filename(name: str) -> str:
    keep = [c if c.isalnum() or c in (".", "-", "_") else "_" for c in name]
    return "".join(keep) or "file"


async def _process_job(job_id: str):
    # Simulate validation and processing, then create an asset entry
    job = IngestionViewsManager.jobs_store.get(job_id)
    if not job:
        return
    job["status"] = "in_progress"
    job["updated_at"] = datetime.utcnow().isoformat()

    # Simulate some processing delay
    await asyncio.sleep(0.2)

    src_path = job.get("file_path")
    if not src_path or not os.path.exists(src_path):
        job["status"] = "failed"
        job["error"] = "File not found"
        job["updated_at"] = datetime.utcnow().isoformat()
        return

    # For local processing, just "promote" the file to processed
    asset_id = str(uuid.uuid4())
    dst_filename = f"{asset_id}_{os.path.basename(src_path)}"
    dst_path = os.path.join(PROCESSED_DIR, dst_filename)

    try:
        # Copy file in chunks to avoid large memory
        with open(src_path, "rb") as rf, open(dst_path, "wb") as wf:
            while True:
                chunk = rf.read(1024 * 1024)
                if not chunk:
                    break
                wf.write(chunk)
    except Exception as e:
        job["status"] = "failed"
        job["error"] = str(e)
        job["updated_at"] = datetime.utcnow().isoformat()
        return

    # Create asset metadata
    asset = {
        "asset_id": asset_id,
        "source_job_id": job_id,
        "filename": os.path.basename(dst_path),
        "content_type": job.get("content_type"),
        "processed_path": dst_path,
        "size_bytes": os.path.getsize(dst_path),
        "created_at": datetime.utcnow().isoformat(),
    }
    IngestionViewsManager.assets_store[asset_id] = asset

    # Update job status
    job["status"] = "completed"
    job["asset_id"] = asset_id
    job["updated_at"] = datetime.utcnow().isoformat()


class IngestionViewsManager:
    """
    Registers versioned ingestion endpoints under /v1 on the provided router.

    Endpoints (local implementation):
      - POST /v1/upload -> streams to local storage, creates job, returns 202 {job_id}
      - GET  /v1/jobs/{job_id} -> 200 with job status or 404
      - GET  /v1/assets/{asset_id} -> 200 with asset metadata or 404
    """

    # In-memory stores (class-level so they persist for the app lifetime)
    jobs_store: Dict[str, Dict[str, Any]] = {}
    assets_store: Dict[str, Dict[str, Any]] = {}

    def __init__(self, router: APIRouter, get_current_user):
        self.router = router
        self.get_current_user = get_current_user

        _ensure_dirs()
        self.register_views()

    def register_views(self):
        # POST @ http://127.0.0.1:8000/v1/upload
        @self.router.post("/upload", status_code=H.HTTP_202_ACCEPTED, summary="Upload media (v1)")
        @auth_required
        async def upload_media(file: UploadFile = File(...), current_user=Depends(self.get_current_user)) -> Dict[str, Any]:
            """
            Accept a file upload, stream to local storage, and create a job. Returns 202 with a job_id.
            """
            if file.content_type not in ALLOWED_CONTENT_TYPES:
                raise HTTPException(status_code=415, detail="Unsupported media type for local ingestion")

            # Create a new job id
            job_id = str(uuid.uuid4())

            # Build destination path
            safe_name = _sanitize_filename(file.filename or "upload.bin")
            raw_filename = f"{job_id}_{safe_name}"
            dst_path = os.path.join(RAW_DIR, raw_filename)

            # Stream upload to disk and compute checksum with a size cap
            hasher = hashlib.sha256()
            total = 0
            try:
                with open(dst_path, "wb") as out:
                    while True:
                        chunk = await file.read(1024 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > MAX_UPLOAD_BYTES:
                            raise HTTPException(status_code=413, detail="Uploaded file too large for local limit")
                        hasher.update(chunk)
                        out.write(chunk)
            finally:
                await file.close()

            # Record job
            job_record = {
                "job_id": job_id,
                "filename": file.filename,
                "stored_filename": raw_filename,
                "file_path": dst_path,
                "content_type": file.content_type,
                "size_bytes": total,
                "checksum_sha256": hasher.hexdigest(),
                "status": "pending",
                "submitted_by": getattr(current_user, "name", None),
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
            IngestionViewsManager.jobs_store[job_id] = job_record

            # For local tests, process immediately to ensure determinism
            await _process_job(job_id)

            return {"job_id": job_id, "status": "accepted"}

        # GET @ http://127.0.0.1:8000/v1/jobs/{job_id}
        @self.router.get("/jobs/{job_id}", status_code=H.HTTP_200_OK, summary="Get job status (v1)")
        @auth_required
        async def get_job_status(job_id: str = Path(..., min_length=1), current_user=Depends(self.get_current_user)) -> Dict[str, Any]:
            job = IngestionViewsManager.jobs_store.get(job_id)
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
            return job

        # GET @ http://127.0.0.1:8000/v1/assets/{asset_id}
        @self.router.get("/assets/{asset_id}", status_code=H.HTTP_200_OK, summary="Get asset metadata (v1)")
        @auth_required
        async def get_asset(asset_id: str = Path(..., min_length=1), current_user=Depends(self.get_current_user)) -> Dict[str, Any]:
            asset = IngestionViewsManager.assets_store.get(asset_id)
            if not asset:
                raise HTTPException(status_code=404, detail="Asset not found")
            return asset
