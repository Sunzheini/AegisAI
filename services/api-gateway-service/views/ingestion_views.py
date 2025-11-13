"""
Ingestion Views
--------------
Defines the IngestionViewsManager and endpoints for media upload, job status, and asset metadata.
Supports both local and orchestrator modes, and event-driven job submission via Redis.

Environment Variables:
    - USE_ORCHESTRATOR: Enable external workflow orchestrator
    - USE_REDIS_PUBLISH: Enable Redis event-driven job submission
    - STORAGE_ROOT, RAW_DIR, PROCESSED_DIR, TRANSCODED_DIR: Storage paths
    - TEST_REDIS_URL: Redis connection string for tests

Endpoints:
    - POST /v1/upload: Upload media, create job, start processing
    - GET /v1/jobs/{job_id}: Get job status
    - GET /v1/assets/{asset_id}: Get asset metadata
"""
import os
import uuid
import asyncio
import hashlib
import logging
from typing import Dict, Any
from datetime import datetime

import boto3
import requests
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Request
from fastapi import Path as PathParam
from starlette import status as H

load_dotenv()

# Conditional import for shared library usage ----------------------------------------------
USE_SHARED_LIB = os.getenv("USE_SHARED_LIB", False)
if USE_SHARED_LIB:
    from shared_lib.contracts.job_schemas import IngestionJobRequest
    from shared_lib.needs.INeedRedisManager import INeedRedisManagerInterface
    from shared_lib.support.security import auth_required
    from shared_lib.support.constants import ALLOWED_CONTENT_TYPES_SET, MAX_UPLOAD_BYTES_SIZE
    from shared_lib.support.support_functions import sanitize_filename
    from shared_lib.local_storages.local_file_storage import LocalFileStorage
    from shared_lib.local_storages.in_memory_job_and_asset_storage import InMemoryJobAndAssetStorage
else:
    from contracts.job_schemas import IngestionJobRequest
    from needs.INeedRedisManager import INeedRedisManagerInterface
    from support.security import auth_required
    from support.constants import ALLOWED_CONTENT_TYPES_SET, MAX_UPLOAD_BYTES_SIZE
    from support.support_functions import sanitize_filename
    from local_storages.local_file_storage import LocalFileStorage
    from local_storages.in_memory_job_and_asset_storage import InMemoryJobAndAssetStorage
# ------------------------------------------------------------------------------------------

USE_AWS = os.getenv("USE_AWS", "false").lower() == "true"

if not USE_AWS:
    STORAGE_ROOT = os.getenv(
        "STORAGE_ROOT", os.path.abspath(os.path.join(os.getcwd(), "storage"))
    )
    RAW_DIR = os.getenv(
        "RAW_DIR", os.path.join(STORAGE_ROOT, "raw")
    )  # Stores the original uploaded files before any processing
    PROCESSED_DIR = os.getenv(
        "PROCESSED_DIR", os.path.join(STORAGE_ROOT, "processed")
    )  # Stores files after initial processing (e.g., validation, copying, basic transformation)
    TRANSCODED_DIR = os.getenv(
        "TRANSCODED_DIR", os.path.join(STORAGE_ROOT, "transcoded")
    )  # Stores files after advanced processing, such as format conversion or transcoding
else:
    RAW_DIR = os.getenv("RAW_DIR_AWS", "aegisai-raw-danielzorov")
    PROCESSED_DIR = os.getenv("PROCESSED_DIR_AWS", "aegisai-processed-danielzorov")
    TRANSCODED_DIR = os.getenv("TRANSCODED_DIR_AWS", "aegisai-transcoded-danielzorov")

ALLOWED_CONTENT_TYPES = ALLOWED_CONTENT_TYPES_SET
MAX_UPLOAD_BYTES = MAX_UPLOAD_BYTES_SIZE  # 50 MB
USE_REDIS_PUBLISH = os.getenv("USE_REDIS_PUBLISH", "false").lower() == "true"

# ToDo: Instantiate abstractions for local usage, change to AWS later
# file_storage = LocalFileStorage(RAW_DIR)
file_storage = boto3.client('s3')
job_asset_store = InMemoryJobAndAssetStorage()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ingestion")


class IngestionViewsManager(INeedRedisManagerInterface):
    """
    Registers versioned ingestion endpoints under /v1 on the provided router.

    Modes:
        - Local: Jobs processed by API Gateway
        - Orchestrator: Jobs submitted to external workflow orchestrator
        - Redis: Jobs published to Redis for event-driven orchestration

    Endpoints:
        - POST /v1/upload: Upload media, create job, start processing
        - GET  /v1/jobs/{job_id}: Get job status
        - GET  /v1/assets/{asset_id}: Get asset metadata
    """

    # In-memory stores (class-level so they persist for the app lifetime)
    """
    jobs_store and assets_store are used for local metadata storage in the API Gateway & 
    Ingestion Service. They track uploaded jobs and assets, and are needed for endpoints 
    like /v1/jobs/{job_id} and /v1/assets/{asset_id}. The orchestrator only needs the 
    job metadata sent via the event (Redis), not the full local store.
    """
    # ToDo: If I later migrate to a cloud database or shared storage, refactor these to
    #  use a persistent backend (e.g., PostgreSQL, DynamoDB).
    jobs_store: Dict[str, Dict[str, Any]] = (
        {}
    )  # job_id -> job_record, stores the ingestion jobs
    assets_store: Dict[str, Dict[str, Any]] = (
        {}
    )  # asset_id -> asset_record, stores the processed assets

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
    def _copy_file_sync(
        src_path: str, dst_path: str, chunk_size: int = 1024 * 1024
    ) -> None:
        """Copy a file using blocking I/O; intended for threadpool use."""
        with open(src_path, "rb") as rf, open(dst_path, "wb") as wf:
            while True:
                chunk = rf.read(chunk_size)
                if not chunk:
                    break
                wf.write(chunk)

    async def _process_job(self, job_id: str) -> None:
        logger.info("Processing job: %s", job_id)
        """
        Takes a pending job, copies the uploaded file to the processed directory, creates 
        asset metadata, and updates the job status accordingly. It handles errors gracefully 
        and ensures all operations are tracked in memory.

        1. Fetches the Job: It retrieves the job record from the in-memory jobs_store using 
        the provided job_id.
        2. Updates Job Status:  Sets the job status to "in_progress" and updates the timestamp.
        3. Simulates Processing Delay: Waits for 0.2 seconds to simulate a processing delay 
        (useful for testing concurrency and async behavior).
        4. Validates File Existence: Checks if the file path exists. If not, marks the job 
        as "failed" and records the error.
        5. Prepares Asset Metadata: Generates a new asset_id and builds the destination filename 
        and path for the processed file.
        6. Copies the File: Uses asyncio.to_thread to call the blocking _copy_file_sync method, 
        which copies the file from the raw directory to the processed directory. This is done 
        in a background thread to avoid blocking the event loop.
        7. Handles Copy Errors: If an error occurs during copying, marks the job as "failed" 
        and records the error.
        8. Creates Asset Record: If successful, creates an asset record with metadata (asset_id, 
        job_id, filename, content type, processed path, size, creation time) and stores it in 
        assets_store.
        9. Updates Job Status to Completed: Marks the job as "completed", links the asset_id, 
        and updates the timestamp.

        :param job_id: The ID of the job to process
        :return: None
        """

        job = self.job_asset_store.get_job(job_id)
        if not job:
            return
        self.job_asset_store.update_job(
            job_id,
            {"status": "in_progress", "updated_at": datetime.utcnow().isoformat()},
        )

        # Simulate processing delay
        await asyncio.sleep(0.2)

        src_path = job.get("file_path")
        logger.info("Processing file from: %s", src_path)
        if not src_path or not os.path.exists(src_path):
            self.job_asset_store.update_job(
                job_id,
                {
                    "status": "failed",
                    "error": "File not found",
                    "updated_at": datetime.utcnow().isoformat(),
                },
            )
            return

        asset_id = str(uuid.uuid4())
        dst_filename = f"{asset_id}_{os.path.basename(src_path)}"
        dst_path = os.path.join(PROCESSED_DIR, dst_filename)
        logger.info("Copying file to processed: %s", dst_path)

        # Ensure processed directory exists before copying
        os.makedirs(PROCESSED_DIR, exist_ok=True)
        try:
            await asyncio.to_thread(self.file_storage.copy_file, src_path, dst_path)
        except (OSError, FileNotFoundError) as e:
            self.job_asset_store.update_job(
                job_id,
                {
                    "status": "failed",
                    "error": str(e),
                    "updated_at": datetime.utcnow().isoformat(),
                },
            )
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
        self.job_asset_store.update_job(
            job_id,
            {
                "status": "completed",
                "asset_id": asset_id,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )
        logger.info("Job %s completed, asset at: %s", job_id, dst_path)

    async def _stream_file_to_disk(self, file, destination_path):
        logger.info("Streaming upload to: %s", destination_path)

        total_size_in_bytes = 0
        hasher = hashlib.sha256()

        # --------------------------------------------------------------------------------------
        if not USE_AWS:
            with open(destination_path, "wb") as out:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    total_size_in_bytes += len(chunk)
                    if total_size_in_bytes > MAX_UPLOAD_BYTES:
                        logger.error("File too large: %d bytes", total_size_in_bytes)
                        raise HTTPException(
                            status_code=413,
                            detail="Uploaded file is larger than the maximum allowed size",
                        )
                    hasher.update(chunk)
                    await asyncio.to_thread(out.write, chunk)

            await file.close()
            logger.info(
                "Finished streaming upload to: %s, size: %d",
                destination_path,
                total_size_in_bytes,
            )
            return total_size_in_bytes, hasher

        # --------------------------------------------------------------------------------------
        else:
            s3_key = f"uploads/{file.filename}"

            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total_size_in_bytes += len(chunk)
                if total_size_in_bytes > MAX_UPLOAD_BYTES:
                    logger.error("File too large: %d bytes", total_size_in_bytes)
                    raise HTTPException(
                        status_code=413,
                        detail="Uploaded file is larger than the maximum allowed size",
                    )
                hasher.update(chunk)

            # Reset file pointer and upload to S3
            await file.seek(0)
            self.file_storage.upload_fileobj(file.file, destination_path, s3_key)

            await file.close()
            logger.info("Uploaded to S3: %s, size: %d", s3_key, total_size_in_bytes)
            return s3_key, total_size_in_bytes, hasher

        # --------------------------------------------------------------------------------------

    def register_views(self) -> None:
        """
        Register ingestion endpoints on the router.
        Endpoints:
            - POST /v1/upload: Upload media and create job
            - GET /v1/jobs/{job_id}: Get job status
            - GET /v1/assets/{asset_id}: Get asset metadata
        """
        logger.info("STORAGE_ROOT: %s", STORAGE_ROOT)
        logger.info("RAW_DIR: %s", RAW_DIR)
        logger.info("PROCESSED_DIR: %s", PROCESSED_DIR)
        logger.info("TRANSCODED_DIR: %s", TRANSCODED_DIR)

        # POST @ http://127.0.0.1:8000/v1/upload
        @self.router.post(
            "/upload", status_code=H.HTTP_202_ACCEPTED, summary="Upload media (v1)"
        )
        @auth_required
        async def upload_media(
            request: Request,
            file: UploadFile = File(...),
            current_user=Depends(self.get_current_user),
        ) -> Dict[str, Any]:
            """
            Uploads a file and creates an ingestion job.

            Modes:
                - Local: Process job in API Gateway
                - Orchestrator: Submit job to external orchestrator
                - Redis: Publish job to Redis for event-driven orchestration

            Args:
                request (Request): FastAPI request object
                file (UploadFile): Uploaded file
                current_user: Authenticated user
            Returns:
                dict: Job ID and status
            Raises:
                HTTPException: On validation or processing errors
            """
            import os  # Ensure we get the latest env vars

            USE_ORCHESTRATOR = os.getenv("USE_ORCHESTRATOR", "false").lower() == "true"
            ORCHESTRATOR_URL = os.getenv(
                "ORCHESTRATOR_URL", "http://localhost:9000/jobs"
            )

            print(20 * "-")
            print(f"file content_type: {file.content_type}")
            print(f"file filename: {file.filename}")
            print(20 * "-")

            if file.content_type not in ALLOWED_CONTENT_TYPES:
                raise HTTPException(
                    status_code=415,
                    detail="Supported content types: "
                    + ", ".join(ALLOWED_CONTENT_TYPES),
                )

            job_id = str(uuid.uuid4())
            safe_name = sanitize_filename(file.filename or "upload.bin")
            raw_filename = f"{job_id}_{safe_name}"

            if not USE_AWS:
                destination_path = os.path.join(RAW_DIR, raw_filename)
                total_size_in_bytes, hasher = await self._stream_file_to_disk(
                    file, destination_path
                )
            else:
                destination_path = RAW_DIR  # S3 bucket name
                s3_key, total_size_in_bytes, hasher = await self._stream_file_to_disk(
                    file, destination_path
                )
                destination_path = f"s3://{destination_path}/{s3_key}"

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

            # -----------------------------------------------------------------------------------
            # Mode 1: Event-driven architecture with Redis Pub/Sub
            # -----------------------------------------------------------------------------------
            if USE_REDIS_PUBLISH:
                return await self.redis_manager.publish_message_to_redis(
                    job_id, job_record, file, current_user
                )

            # -----------------------------------------------------------------------------------
            # Mode 2: Direct submission to orchestrator or local processing
            # -----------------------------------------------------------------------------------
            else:
                print(f"[upload_media] Submitting job directly for job_id: {job_id}")

                # Mode 2 Option 1: Send job to orchestrator if configured
                if USE_ORCHESTRATOR:
                    try:
                        job_payload = IngestionJobRequest(
                            job_id=job_id,
                            file_path=destination_path,
                            content_type=file.content_type,
                            checksum_sha256=hasher.hexdigest(),
                            submitted_by=getattr(current_user, "name", None),
                        ).model_dump()
                        resp = requests.post(
                            ORCHESTRATOR_URL, json=job_payload, timeout=5
                        )

                        resp.raise_for_status()
                    except Exception as e:
                        self.job_asset_store.update_job(
                            job_id,
                            {
                                "status": "failed",
                                "error": str(e),
                                "updated_at": datetime.utcnow().isoformat(),
                            },
                        )
                        raise HTTPException(
                            status_code=502,
                            detail=f"Failed to submit job to orchestrator: {e}",
                        ) from e

                    return {"job_id": job_id, "status": "submitted_to_orchestrator"}

                # Mode 2 Option 2: Local processing: await in tests, concurrent otherwise
                else:
                    if getattr(getattr(request.app, "state", None), "testing", False):
                        await self._process_job(job_id)
                    else:
                        asyncio.create_task(self._process_job(job_id))
                    return {"job_id": job_id, "status": "accepted"}

        # GET @ http://127.0.0.1:8000/v1/jobs/{job_id}
        @self.router.get(
            "/jobs/{job_id}", status_code=H.HTTP_200_OK, summary="Get job status (v1)"
        )
        @auth_required
        async def get_job_status(
            job_id: str = PathParam(..., min_length=1),
            current_user=Depends(self.get_current_user),
        ) -> Dict[str, Any]:
            """
            Returns job status for the given job_id.
            Args:
                job_id (str): Job identifier
                current_user: Authenticated user
            Returns:
                dict: Job metadata
            Raises:
                HTTPException: If job not found
            """
            job = self.job_asset_store.get_job(job_id)
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
            return job

        # GET @ http://127.0.0.1:8000/v1/assets/{asset_id}
        @self.router.get(
            "/assets/{asset_id}",
            status_code=H.HTTP_200_OK,
            summary="Get asset metadata (v1)",
        )
        @auth_required
        async def get_asset(
            asset_id: str = PathParam(..., min_length=1),
            current_user=Depends(self.get_current_user),
        ) -> Dict[str, Any]:
            """
            Returns asset metadata for the given asset_id.
            Args:
                asset_id (str): Asset identifier
                current_user: Authenticated user
            Returns:
                dict: Asset metadata
            Raises:
                HTTPException: If asset not found
            """
            asset = self.job_asset_store.get_asset(asset_id)
            if not asset:
                raise HTTPException(status_code=404, detail="Asset not found")
            return asset
