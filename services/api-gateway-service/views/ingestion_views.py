import os
import uuid
import asyncio
import hashlib
from typing import Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Path, Request
from starlette import status as H

from routers.security import auth_required
from support.constants import ALLOWED_CONTENT_TYPES_SET, MAX_UPLOAD_BYTES_SIZE
from support.support_functions import sanitize_filename
from support.storage_abstraction import LocalFileStorage, InMemoryJobAssetStore


STORAGE_ROOT = os.getenv("STORAGE_ROOT", os.path.abspath(os.path.join(os.getcwd(), "storage")))
RAW_DIR = os.getenv("RAW_DIR", os.path.join(STORAGE_ROOT, "raw"))
PROCESSED_DIR = os.getenv("PROCESSED_DIR", os.path.join(STORAGE_ROOT, "processed"))
TRANSCODED_DIR = os.getenv("TRANSCODED_DIR", os.path.join(STORAGE_ROOT, "transcoded"))

ALLOWED_CONTENT_TYPES = ALLOWED_CONTENT_TYPES_SET
MAX_UPLOAD_BYTES = MAX_UPLOAD_BYTES_SIZE  # 50 MB


# ToDo: Instantiate abstractions for local usage, change to AWS later
file_storage = LocalFileStorage(RAW_DIR)
job_asset_store = InMemoryJobAssetStore()


class IngestionViewsManager:
    """
    Registers versioned ingestion endpoints under /v1 on the provided router.

    Endpoints:
      - POST /v1/upload: Upload media, create job, start processing
      - GET  /v1/jobs/{job_id}: Get job status
      - GET  /v1/assets/{asset_id}: Get asset metadata
    """
    # ToDo: move to persistent storage (database, cloud storage) in production
    # In-memory stores (class-level so they persist for the app lifetime)
    jobs_store: Dict[str, Dict[str, Any]] = {}      # job_id -> job_record, stores the ingestion jobs
    assets_store: Dict[str, Dict[str, Any]] = {}    # asset_id -> asset_record, stores the processed assets

    def __init__(self, router: APIRouter, get_current_user):
        self.router = router
        self.get_current_user = get_current_user
        self.file_storage = file_storage
        self.job_asset_store = job_asset_store

        self._ensure_dirs()
        self.register_views()

    @staticmethod
    def _ensure_dirs() -> None:
        """Create storage directories if they do not exist."""
        os.makedirs(RAW_DIR, exist_ok=True)
        os.makedirs(PROCESSED_DIR, exist_ok=True)
        os.makedirs(TRANSCODED_DIR, exist_ok=True)

    @staticmethod
    def _copy_file_sync(src_path: str, dst_path: str, chunk_size: int = 1024 * 1024) -> None:
        """Copy a file using blocking I/O; intended for threadpool use."""
        with open(src_path, "rb") as rf, open(dst_path, "wb") as wf:
            while True:
                chunk = rf.read(chunk_size)
                if not chunk:
                    break
                wf.write(chunk)

    async def _process_job(self, job_id: str) -> None:
        """
        Takes a pending job, copies the uploaded file to the processed directory, creates asset
        metadata, and updates the job status accordingly. It handles errors gracefully and ensures all operations
        are tracked in memory.

        1. Fetches the Job: It retrieves the job record from the in-memory jobs_store using the provided job_id.
        2. Updates Job Status:  Sets the job status to "in_progress" and updates the timestamp.
        3. Simulates Processing Delay: Waits for 0.2 seconds to simulate a processing delay (useful for testing concurrency and async behavior).
        4. Validates File Existence: Checks if the file path exists. If not, marks the job as "failed" and records the error.
        5. Prepares Asset Metadata: Generates a new asset_id and builds the destination filename and path for the processed file.
        6. Copies the File: Uses asyncio.to_thread to call the blocking _copy_file_sync method, which copies the file from the raw directory to the processed directory. This is done in a background thread to avoid blocking the event loop.
        7. Handles Copy Errors: If an error occurs during copying, marks the job as "failed" and records the error.
        8. Creates Asset Record: If successful, creates an asset record with metadata (asset_id, job_id, filename, content type, processed path, size, creation time) and stores it in assets_store.
        9. Updates Job Status to Completed: Marks the job as "completed", links the asset_id, and updates the timestamp.

        :param job_id: The ID of the job to process
        :return: None
        """
        job = self.job_asset_store.get_job(job_id)
        if not job:
            return
        self.job_asset_store.update_job(job_id, {"status": "in_progress", "updated_at": datetime.utcnow().isoformat()})

        # Simulate processing delay
        await asyncio.sleep(0.2)

        src_path = job.get("file_path")
        if not src_path or not os.path.exists(src_path):
            self.job_asset_store.update_job(job_id, {"status": "failed", "error": "File not found", "updated_at": datetime.utcnow().isoformat()})
            return

        asset_id = str(uuid.uuid4())
        dst_filename = f"{asset_id}_{os.path.basename(src_path)}"
        dst_path = os.path.join(PROCESSED_DIR, dst_filename)

        # Ensure processed directory exists before copying
        os.makedirs(PROCESSED_DIR, exist_ok=True)
        try:
            await asyncio.to_thread(self.file_storage.copy_file, src_path, dst_path)
        except Exception as e:
            self.job_asset_store.update_job(job_id, {"status": "failed", "error": str(e), "updated_at": datetime.utcnow().isoformat()})
            return
        asset = {
            "asset_id": asset_id,
            "source_job_id": job_id,
            "filename": os.path.basename(dst_path),
            "content_type": job.get("content_type"),
            "processed_path": dst_path,
            "size_bytes": os.path.getsize(dst_path),
            "created_at": datetime.utcnow().isoformat(),
        }
        self.job_asset_store.create_asset(asset)
        self.job_asset_store.update_job(job_id, {"status": "completed", "asset_id": asset_id, "updated_at": datetime.utcnow().isoformat()})

    @staticmethod
    async def _stream_file_to_disk(file, destination_path):
        # Use abstraction for saving file
        total_size_in_bytes = 0
        hasher = hashlib.sha256()
        with open(destination_path, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total_size_in_bytes += len(chunk)
                if total_size_in_bytes > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="Uploaded file is larger than the maximum allowed size"
                    )
                hasher.update(chunk)
                await asyncio.to_thread(out.write, chunk)
        await file.close()
        return total_size_in_bytes, hasher

    def register_views(self) -> None:
        # POST @ http://127.0.0.1:8000/v1/upload
        @self.router.post("/upload", status_code=H.HTTP_202_ACCEPTED, summary="Upload media (v1)")
        @auth_required
        async def upload_media(request: Request, file: UploadFile = File(...), current_user=Depends(self.get_current_user)) -> Dict[str, Any]:
            """
            1. Accept a file upload, 2. stream to local storage, 3. and create a job. 4. Returns 202 with a job_id.
            """
            if file.content_type not in ALLOWED_CONTENT_TYPES:
                raise HTTPException(
                    status_code=415,
                    detail="Supported content types: " + ", ".join(ALLOWED_CONTENT_TYPES)
                )

            # Create a new job id
            job_id = str(uuid.uuid4())

            # Build destination path
            safe_name = sanitize_filename(file.filename or "upload.bin")
            raw_filename = f"{job_id}_{safe_name}"
            destination_path = os.path.join(RAW_DIR, raw_filename)

            # Stream file to disk and compute checksum
            total_size_in_bytes, hasher = await self._stream_file_to_disk(file, destination_path)

            # Record job
            job_record = {
                "job_id": job_id,
                "filename": file.filename,
                "stored_filename": raw_filename,
                "file_path": destination_path,
                "content_type": file.content_type,
                "size_bytes": total_size_in_bytes,
                "checksum_sha256": hasher.hexdigest(),
                "status": "pending",
                "submitted_by": getattr(current_user, "name", None),
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
            self.job_asset_store.create_job(job_record)

            # Run processing: await in tests, background otherwise
            if getattr(getattr(request.app, "state", None), "testing", False):
                await self._process_job(job_id)
            else:
                asyncio.create_task(self._process_job(job_id))   # You cannot call asyncio.run inside an already running event loop

            return {"job_id": job_id, "status": "accepted"}

        # GET @ http://127.0.0.1:8000/v1/jobs/{job_id}
        @self.router.get("/jobs/{job_id}", status_code=H.HTTP_200_OK, summary="Get job status (v1)")
        @auth_required
        async def get_job_status(job_id: str = Path(..., min_length=1), current_user=Depends(self.get_current_user)) -> Dict[str, Any]:
            """Return job status or 404 if not found."""
            job = self.job_asset_store.get_job(job_id)
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
            return job

        # GET @ http://127.0.0.1:8000/v1/assets/{asset_id}
        @self.router.get("/assets/{asset_id}", status_code=H.HTTP_200_OK, summary="Get asset metadata (v1)")
        @auth_required
        async def get_asset(
            asset_id: str = Path(..., min_length=1), current_user=Depends(self.get_current_user)) -> Dict[str, Any]:
            """Return asset metadata or 404 if not found."""
            asset = self.job_asset_store.get_asset(asset_id)
            if not asset:
                raise HTTPException(status_code=404, detail="Asset not found")
            return asset
