I have a monorepo with several microservices in separate folders. This is the structure:

AegisAI/
├── docker-compose.yml
├── shared-storage/  
├── services/ 
│   ├── api-gateway-service/
│   ├── workflow-orchestrator-service/
│	│	└── worker_clients/
│	├── validation-service/
│	├── extract-metadata-service/
│	├── extract-content-service/
│	└── ai-service/
└── shared-lib/
    └── ...


Each microservice (e.g api-gateway-service) has its own .env, pyproject.toml, .venv, etc. I will give example with the first service in the chain: this is its main.py: `"""
API Gateway Microservice
-----------------------
Entry point for the API Gateway & Ingestion Service. Sets up FastAPI app, routers, and middleware.

Routers:
    - auth: Authentication endpoints
    - users: User management endpoints
    - v1: Versioned API endpoints (including ingestion)
    - redis_router: Redis health and pub/sub endpoints

Middleware:
    - InMemoryRateLimiter: Local rate limiting (bypassed during tests)

App State:
    - ingestion_manager: Instance of IngestionViewsManager for job and asset management

Health Endpoint:
    - GET /health: Returns service status
"""
import os
import logging

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

# Conditional import for shared library usage ----------------------------------------------
USE_SHARED_LIB = os.getenv("USE_SHARED_LIB", False)

if USE_SHARED_LIB:
    from shared_lib.support.constants import LOG_FILE_PATH, APP_NAME
    from shared_lib.custom_middleware.rate_limiting_middleware import InMemoryRateLimiter
    from shared_lib.custom_middleware.error_middleware import ErrorMiddleware
    from shared_lib.custom_middleware.logging_middleware import EnhancedLoggingMiddleware
    from shared_lib.logging_management.logging_manager import LoggingManager
else:
    from support.constants import LOG_FILE_PATH, APP_NAME
    from custom_middleware.rate_limiting_middleware import InMemoryRateLimiter
    from custom_middleware.error_middleware import ErrorMiddleware
    from custom_middleware.logging_middleware import EnhancedLoggingMiddleware
    from logging_management.logging_manager import LoggingManager
# ------------------------------------------------------------------------------------------

from views.ingestion_views import IngestionViewsManager
from routers import auth_router, users_router, v1_router, redis_router
from routers.users_router import get_current_user


logger = LoggingManager.setup_logging(
    service_name=APP_NAME, log_file_path=LOG_FILE_PATH, log_level=logging.DEBUG
)


# FastAPI app setup
app = FastAPI(title="api-gateway-microservice", version="1.0.0")


# Middleware
app.add_middleware(
    InMemoryRateLimiter, requests_per_minute=60
)  # Local-only rate limiting middleware (fixed window). Bypassed during tests.
app.add_middleware(ErrorMiddleware)
app.add_middleware(EnhancedLoggingMiddleware, service_name=APP_NAME)


# Include routers
app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(v1_router.router)
app.include_router(redis_router.router)


"""
Register ingestion manager and expose for tests! app.state is a dynamic attribute 
(using Starlette’s State object)!
"""
app.state.ingestion_manager = IngestionViewsManager(v1_router.router, get_current_user)


# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Health check endpoint for API Gateway service.

    Returns:
        dict: Service status
    """
    return {"status": "ok"}


@app.get("/raise-error")
async def raise_error():
    """Endpoint to intentionally raise an error for testing error middleware (needed in tests)."""
    raise RuntimeError("Intentional error for testing error middleware")
`, the ingestion_views.py: `"""
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
    from shared_lib.support.storage_abstraction import LocalFileStorage, InMemoryJobAssetStore
else:
    from contracts.job_schemas import IngestionJobRequest
    from needs.INeedRedisManager import INeedRedisManagerInterface
    from support.security import auth_required
    from support.constants import ALLOWED_CONTENT_TYPES_SET, MAX_UPLOAD_BYTES_SIZE
    from support.support_functions import sanitize_filename
    from support.storage_abstraction import LocalFileStorage, InMemoryJobAssetStore
# ------------------------------------------------------------------------------------------

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

ALLOWED_CONTENT_TYPES = ALLOWED_CONTENT_TYPES_SET
MAX_UPLOAD_BYTES = MAX_UPLOAD_BYTES_SIZE  # 50 MB
USE_REDIS_PUBLISH = os.getenv("USE_REDIS_PUBLISH", "false").lower() == "true"

# ToDo: Instantiate abstractions for local usage, change to AWS later
file_storage = LocalFileStorage(RAW_DIR)
job_asset_store = InMemoryJobAssetStore()

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

    @staticmethod
    async def _stream_file_to_disk(file, destination_path):
        logger.info("Streaming upload to: %s", destination_path)
        total_size_in_bytes = 0
        hasher = hashlib.sha256()
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
            destination_path = os.path.join(RAW_DIR, raw_filename)

            total_size_in_bytes, hasher = await self._stream_file_to_disk(
                file, destination_path
            )

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
            asset = self.job_asset_store.get_asset(asset_id)
            if not asset:
                raise HTTPException(status_code=404, detail="Asset not found")
            return asset
`, the .env `DEBUG=True
SECRET_KEY=mysecretkey
AUTH_ENVIRONMENT=local
STORAGE_ROOT=D:/Study/Projects/Github/AegisAI/shared-storage
RAW_DIR=D:/Study/Projects/Github/AegisAI/shared-storage/raw
PROCESSED_DIR=D:/Study/Projects/Github/AegisAI/shared-storage/processed
TRANSCODED_DIR=D:/Study/Projects/Github/AegisAI/shared-storage/transcoded
USE_ORCHESTRATOR=True
ORCHESTRATOR_URL=http://localhost:9000/jobs
TEST_REDIS_URL=redis://localhost:6379/2
USE_REDIS_PUBLISH=True
DB_NAME=fastapi_db
DB_USER=postgres_user
DB_PASSWORD=password
DB_HOST=localhost
DB_PORT=5432
USE_SHARED_LIB=True` and the toml `[project]
name = "api-gateway-service"
version = "0.1.0"
description = ""
authors = [
    {name = "Sunzheini",email = "daniel_zorov@abv.bg"}
]
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "fastapi[standard] (>=0.117.1,<0.118.0)",
    "uvicorn[standard] (>=0.37.0,<0.38.0)",
    "python-jose (>=3.5.0,<4.0.0)",
    "python-dotenv (>=1.1.1,<2.0.0)",
    "pytest (>=8.4.2,<9.0.0)",
    "passlib[bcrypt] (>=1.7.4,<2.0.0)",
    "requests (>=2.32.5,<3.0.0)",
    "redis (>=6.4.0,<7.0.0)",
    "pytest-asyncio (>=1.2.0,<2.0.0)",
    "langgraph (>=0.6.8,<0.7.0)",
    "langgraph-sdk (>=0.2.9,<0.3.0)",
    "langgraph-checkpoint (>=2.1.2,<3.0.0)",
    "langgraph-prebuilt (>=0.6.4,<0.7.0)",
    "pylint (>=4.0.0,<5.0.0)",
    "black (>=25.9.0,<26.0.0)",
    "logging (>=0.4.9.6,<0.5.0.0)",
    "sqlalchemy (>=2.0.44,<3.0.0)",
    "psycopg2 (>=2.9.11,<3.0.0)",
    "user-agents (>=2.2.0,<3.0.0)",
    "pdfplumber (>=0.11.7,<0.12.0)",
    "shared-lib @ file:///D:/Study/Projects/Github/AegisAI/shared-lib"
]


[build-system]
requires = ["poetry-core>=2.0.0,<3.0.0"]
build-backend = "poetry.core.masonry.api"
`. The second service main.py: `"""
Workflow Orchestrator Service
----------------------------
Orchestrates ingestion jobs using a workflow graph (LangGraph).
Supports both direct HTTP job submission and event-driven orchestration via Redis.

Features:
    - Modular design for migration to AWS or other cloud platforms
    - All workflow logic encapsulated in WorkflowOrchestrator class
    - Endpoints: POST /jobs (submit job), GET /jobs/{job_id} (poll status)
    - Redis listener for JOB_CREATED events from API Gateway

Environment Variables:
    - USE_REDIS_LISTENER: Enable Redis event-driven orchestration
    - TEST_REDIS_URL: Redis connection string for tests

To run:
    uvicorn workflow_orchestrator_example:app --reload --port 9000

Migration Notes:
    - Move shared contracts (e.g., contracts/job_schemas.py) to new project
    - Update import paths as needed
    - Ensure both services use the same Redis instance and job schema
    - Replace in-memory stores with S3/DynamoDB for production
    - Replace simulated workers with Lambda/Step Functions for cloud
"""
import os
import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import asyncio
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from fastapi import FastAPI, HTTPException, status, Request

load_dotenv()

from shared_lib.contracts.job_schemas import (
    IngestionJobRequest,
    IngestionJobStatusResponse,
    WorkflowGraphState,
)
from shared_lib.needs.INeedRedisManager import INeedRedisManagerInterface
from shared_lib.needs.ResolveNeedsManager import ResolveNeedsManager
from shared_lib.support.support_functions import resolve_file_path
from shared_lib.logging_management.logging_manager import LoggingManager
from shared_lib.custom_middleware.logging_middleware import EnhancedLoggingMiddleware
from shared_lib.custom_middleware.error_middleware import ErrorMiddleware

from media_processing_worker_example import (
    generate_thumbnails_worker,
    extract_audio_worker,
    transcribe_audio_worker,
    generate_video_summary_worker,
)
from ai_worker_example import (
    analyze_image_with_ai_worker,
)

# Worker clients using Redis
from worker_clients.validation_worker_client import validate_file_worker_redis
from worker_clients.extract_metadata_worker_client import (
    extract_metadata_from_file_worker_redis,
)
from worker_clients.extract_text_worker_client import (
    extract_text_from_file_worker_redis,
)
from worker_clients.ai_worker_client import process_file_by_ai_worker_redis


USE_REDIS_LISTENER = os.getenv("USE_REDIS_LISTENER", "true").lower() == "true"


logger = LoggingManager.setup_logging(
    service_name="workflow-orchestrator",
    log_file_path="logs/workflow_orchestrator.log",
    log_level=logging.INFO,
)


@asynccontextmanager
async def lifespan(app):
    """Lifespan context manager to start/stop Redis listener if enabled."""
    logger.info("Starting Workflow Orchestrator service...")

    # Create orchestrator and inject RedisManager
    orchestrator = WorkflowOrchestrator()
    ResolveNeedsManager.resolve_needs(orchestrator)

    # Resolve ValidationWorkerClient dependency
    from worker_clients.validation_worker_client import validation_worker_client
    from worker_clients.extract_metadata_worker_client import (
        extract_metadata_worker_client,
    )
    from worker_clients.extract_text_worker_client import extract_text_worker_client
    from worker_clients.ai_worker_client import ai_worker_client

    ResolveNeedsManager.resolve_needs(validation_worker_client)
    ResolveNeedsManager.resolve_needs(extract_metadata_worker_client)
    ResolveNeedsManager.resolve_needs(extract_text_worker_client)
    ResolveNeedsManager.resolve_needs(ai_worker_client)

    # Store orchestrator in app.state so routes can access it
    app.state.orchestrator = orchestrator
    app.state.redis_manager = orchestrator.redis_manager
    app.state.validation_worker_client = validation_worker_client
    app.state.extract_metadata_worker_client = extract_metadata_worker_client
    app.state.extract_text_worker_client = extract_text_worker_client
    app.state.ai_worker_client = ai_worker_client

    if USE_REDIS_LISTENER:
        print("[Orchestrator] Redis listener mode enabled. Starting Redis listener...")
        logger.info("Redis listener mode enabled. Starting Redis listener...")
        # Pass orchestrator to redis_listener
        task = asyncio.create_task(redis_listener(orchestrator))
        yield
        print("[Orchestrator] Shutting down Redis listener.")
        logger.info("Shutting down Redis listener.")
        task.cancel()

        # Close RedisManager connection - NOW IT EXISTS!
        await app.state.redis_manager.close()
    else:
        print(
            "[Orchestrator] Redis listener mode disabled. "
            "Only direct HTTP submission will be processed."
        )
        logger.info(
            "Redis listener mode disabled. Only direct HTTP submission will be processed."
        )
        yield


app = FastAPI(title="Workflow Orchestrator Example", lifespan=lifespan)
app.add_middleware(ErrorMiddleware)
app.add_middleware(EnhancedLoggingMiddleware, service_name="workflow-orchestrator")


class WorkflowOrchestrator(INeedRedisManagerInterface):
    """
    Orchestrates ingestion jobs using a workflow graph.
    Each step is a simulated async worker.
    Replace with real workers/cloud services for production.
    """

    def __init__(self):
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger("workflow-orchestrator")
        # Define workflow graph structure
        self.graph = self._build_graph()

    def _build_graph(self):
        print("[Orchestrator] Building workflow graph...")
        # Use LangGraph StateGraph if available, else use dict
        if StateGraph:
            print(
                "[Orchestrator] Using LangGraph StateGraph with state_schema=MyState."
            )
            graph = StateGraph(state_schema=WorkflowGraphState)

            # Nodes
            graph.add_node("validate_file", validate_file_worker_redis)
            graph.add_node("extract_metadata", extract_metadata_from_file_worker_redis)
            graph.add_node("route_workflow", self._worker_route_workflow)

            # Image branch
            graph.add_node(
                "generate_thumbnails", generate_thumbnails_worker
            )  # placeholder
            graph.add_node(
                "analyze_image_with_ai", analyze_image_with_ai_worker
            )  # placeholder

            # Video branch
            graph.add_node("extract_audio", extract_audio_worker)  # placeholder
            graph.add_node("transcribe_audio", transcribe_audio_worker)  # placeholder
            graph.add_node(
                "generate_video_summary", generate_video_summary_worker
            )  # placeholder

            # PDF branch
            graph.add_node("extract_text", extract_text_from_file_worker_redis)
            graph.add_node("summarize_document", process_file_by_ai_worker_redis)
            print("[Orchestrator] Added all nodes to graph.")

            # Conditional edge after validation: if failed, go to END
            def after_validation(state: WorkflowGraphState):
                if state.get("status") == "failed":
                    return "END"
                return "extract_metadata"

            graph.add_conditional_edges(
                "validate_file",
                after_validation,
                {"END": END, "extract_metadata": "extract_metadata"},
            )

            graph.add_edge("extract_metadata", "route_workflow")
            print("[Orchestrator] Added main edges.")

            # Conditional routing based on content type
            def route_workflow(state: WorkflowGraphState):
                return state["branch"]

            graph.add_conditional_edges(
                "route_workflow",
                route_workflow,
                {
                    "image_branch": "generate_thumbnails",
                    "video_branch": "extract_audio",
                    "pdf_branch": "extract_text",
                },
            )

            # Define branch flows
            graph.add_edge("generate_thumbnails", "analyze_image_with_ai")
            graph.add_edge("analyze_image_with_ai", END)

            graph.add_edge("extract_audio", "transcribe_audio")
            graph.add_edge("transcribe_audio", "generate_video_summary")
            graph.add_edge("generate_video_summary", END)

            graph.add_edge("extract_text", "summarize_document")
            graph.add_edge("summarize_document", END)

            graph.set_entry_point("validate_file")
            compiled_graph = graph.compile()

            # Add visualization to see graph
            try:
                compiled_graph.get_graph().draw_mermaid_png(
                    output_file_path="workflow_graph.png"
                )
                print(
                    "[Orchestrator] Workflow graph visualization saved to workflow_graph.png"
                )
            # The visualization code could fail for various reasons (e.g., file I/O errors,
            # missing dependencies, graph rendering issues)
            except Exception as e:
                print(f"[Orchestrator] Could not generate graph visualization: {e}")

            return compiled_graph

        else:
            print(
                "[Orchestrator] LangGraph not available, using fallback graph structure."
            )
            return {
                "nodes": ["validate_file", "extract_metadata", "route_workflow"],
                "branches": {
                    "image": ["generate_thumbnails", "analyze_image_with_ai"],
                    "video": [
                        "extract_audio",
                        "transcribe_audio",
                        "generate_video_summary",
                    ],
                    "pdf": ["extract_text", "summarize_document"],
                },
            }

    async def submit_job(self, job: IngestionJobRequest):
        """
        Submit a new job to the orchestrator.
        Args:
            job (IngestionJobRequest): Job request from API Gateway.
        Raises:
            ValueError: If job_id already exists.
        """
        print(f"[Orchestrator] Received job submission: {job.job_id}")
        # Check Redis for existing job
        existing_state = await self.redis_manager.load_job_state_from_redis(job.job_id)
        if existing_state:
            print(f"[Orchestrator] Job {job.job_id} already exists!")
            raise ValueError("Job already exists")

        # Resolve file path once in orchestrator
        resolved_path = await resolve_file_path(job.file_path, job.job_id)

        state = WorkflowGraphState(
            job_id=job.job_id,
            # file_path=job.file_path,
            file_path=resolved_path,
            content_type=job.content_type,
            checksum_sha256=job.checksum_sha256,
            submitted_by=job.submitted_by,
            status="queued",
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            step="queued",
            branch="",  # will be set by route_workflow
            metadata=None,
        )

        self.jobs[job.job_id] = state
        await self.redis_manager.save_job_state_to_redis(job.job_id, state)
        print(f"[Orchestrator] Job {job.job_id} queued. Initial state: {state}")
        print(f"Jon content type: {job.content_type}")

        # Start workflow in background
        asyncio.create_task(self._run_workflow(job.job_id))

    async def _run_workflow(self, job_id: str) -> None:
        """
        Runs the workflow for a given job_id.
        Updates job state in self.jobs and Redis.
        Args:
            job_id (str): The job identifier.
        ️ Note: This runs in the background as a separate task.
        """
        try:
            state = self.jobs[job_id]
            print(f"[DEBUG] Before graph.ainvoke: {state}")
            final_state = await self.graph.ainvoke(state)  # Call the graph
            self.jobs[job_id] = final_state
            await self.redis_manager.save_job_state_to_redis(job_id, final_state)

        # Can raise various exceptions, including those from async workers, graph logic, or deps
        except Exception as e:
            # Get the current state and update it
            state = self.jobs[job_id]
            state["status"] = "failed"
            current_step = state.get("step", "unknown")
            state["step"] = f"failed_at_{current_step}"
            state["updated_at"] = datetime.now(timezone.utc).isoformat()
            self.jobs[job_id] = state
            await self.redis_manager.save_job_state_to_redis(job_id, state)
            self.logger.error("Workflow failed for job %s: %s", job_id, e)

    async def get_job(self, job_id: str) -> Optional[WorkflowGraphState]:
        """Get job state from Redis as MyState."""
        return await self.redis_manager.load_job_state_from_redis(job_id)

    @staticmethod
    async def _worker_route_workflow(state: WorkflowGraphState) -> WorkflowGraphState:
        """
        Simulated routing worker.
        Uses content_type from IngestionJobRequest to decide the workflow branch
        (image, video, pdf).
        In production, replace with a real routing service or logic.
        Args:
            job_id (str): The job identifier.
        Returns:
            str: The selected branch (image, video, pdf).
        """
        print(f"[Worker:route_workflow] Job {state['job_id']} routing workflow...")
        await asyncio.sleep(0.2)

        # Simulate branch selection based on content_type
        content_type = state["content_type"]
        if "image" in content_type:
            state["branch"] = "image_branch"
        elif "video" in content_type:
            state["branch"] = "video_branch"
        elif "pdf" in content_type:
            state["branch"] = "pdf_branch"
        else:
            state["branch"] = "image_branch"

        state["status"] = f"routed_to_{state['branch']}"
        state["step"] = "route_workflow"
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        print(
            f"[Worker:route_workflow] Job {state['job_id']} routed to {state['branch']} "
            f"branch. State: {state}"
        )
        return state


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
    orchestrator = request.app.state.orchestrator  # Get from app.state
    print(f"[Orchestrator] Received direct job submission for job_id: {job.job_id}")
    try:
        await orchestrator.submit_job(job)
    except ValueError as e:
        print(
            f"[Orchestrator] Duplicate job_id {job.job_id} received via HTTP. Skipping."
        )
        raise HTTPException(status_code=409, detail=str(e)) from e
    return {"job_id": job.job_id, "status": "queued"}


@app.get(
    "/jobs/{job_id}",
    status_code=status.HTTP_200_OK,
    response_model=IngestionJobStatusResponse,
)
async def get_job_status(job_id: str, request: Request):
    """
    The frontend polls this endpoint to get job status updates.
    Returns the current status and metadata for a job.
    Args:
        job_id (str): The job identifier.
        request (Request): FastAPI request object.
    Returns:
        IngestionJobStatusResponse: Job metadata if found.
    Raises:
        HTTPException: If job not found.
    """
    orchestrator = request.app.state.orchestrator  # Get from app.state
    job = await orchestrator.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return IngestionJobStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        step=job["step"],
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        file_path=job["file_path"],
        content_type=job["content_type"],
        checksum_sha256=job["checksum_sha256"],
        submitted_by=job.get("submitted_by"),
        metadata=job.get("metadata"),
    )


# ----------------------------------------------------------------------------------------------
# Redis listener to subscribe to command_queue and process JOB_CREATED events
# ----------------------------------------------------------------------------------------------
async def redis_listener(orchestrator_instance):
    """
    Redis listener for JOB_CREATED events.
    Subscribes to the 'command_queue' channel and processes new jobs.
    Reconstructs jobs using IngestionJobRequest and submits them to the workflow orchestrator.
    Skips duplicate jobs.
    """
    pubsub = await orchestrator_instance.redis_manager.get_pubsub()
    try:
        await pubsub.subscribe("command_queue")
        print("[Orchestrator] Listening for JOB_CREATED events on Redis...")
        async for message in pubsub.listen():
            if message["type"] == "message":
                event = json.loads(message["data"])
                if event.get("event") == "JOB_CREATED":
                    print(
                        f"[Orchestrator] Received JOB_CREATED event for job_id: {event['job_id']}"
                    )

                    # Use IngestionJobRequest to reconstruct job from event
                    job = IngestionJobRequest(
                        **{k: v for k, v in event.items() if k != "event"}
                    )
                    try:
                        await orchestrator_instance.submit_job(job)
                    except ValueError:
                        print(
                            f"[Orchestrator] Duplicate job_id {event['job_id']} received from "
                            f"Redis. Skipping."
                        )
    except asyncio.CancelledError:
        await pubsub.unsubscribe("command_queue")
`, the .env `DEBUG=True
STORAGE_ROOT=D:/Study/Projects/Github/AegisAI/shared-storage
RAW_DIR=D:/Study/Projects/Github/AegisAI/shared-storage/raw
PROCESSED_DIR=D:/Study/Projects/Github/AegisAI/shared-storage/processed
TRANSCODED_DIR=D:/Study/Projects/Github/AegisAI/shared-storage/transcoded
TEST_REDIS_URL=redis://localhost:6379/2` and toml `[project]
name = "workflow-orchestrator-service"
version = "0.1.0"
description = ""
authors = [
    {name = "Sunzheini",email = "daniel_zorov@abv.bg"}
]
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "requests (>=2.32.5,<3.0.0)",
    "fastapi[standard] (>=0.119.1,<0.120.0)",
    "redis (>=6.4.0,<7.0.0)",
    "uvicorn[standard] (>=0.38.0,<0.39.0)",
    "pytest (>=8.4.2,<9.0.0)",
    "pytest-asyncio (>=1.2.0,<2.0.0)",
    "langgraph (>=0.6.8,<0.7.0)",
    "pylint (>=4.0.0,<5.0.0)",
    "black (>=25.9.0,<26.0.0)",
    "python-dotenv (>=1.1.1,<2.0.0)",
    "shared-lib @ file:///D:/Study/Projects/Github/AegisAI/shared-lib",
    "user-agents (>=2.2.0,<3.0.0)"
]


[build-system]
requires = ["poetry-core>=2.0.0,<3.0.0"]
build-backend = "poetry.core.masonry.api"
`. As you can see the second service uses worker_clients, e.g. `"""
Validation Worker Client for Orchestrator
----------------------------------
Lightweight client that publishes validation tasks to Redis and waits for results.
Used by the workflow orchestrator.
"""
import os

from dotenv import load_dotenv

from shared_lib.contracts.job_schemas import WorkflowGraphState
from shared_lib.worker_clients.base_worker_client import BaseWorkerClient


load_dotenv()


# Specific Configuration
VALIDATION_WORKER_NAME = os.getenv("VALIDATION_WORKER_NAME", "ValidationWorker")
VALIDATION_TASK_NAME = os.getenv("VALIDATION_TASK_NAME", "validation")
VALIDATION_QUEUE = os.getenv("VALIDATION_QUEUE", "validation_queue")
VALIDATION_CALLBACK_QUEUE = os.getenv(
    "VALIDATION_CALLBACK_QUEUE", "validation_callback_queue"
)


class ValidationWorkerClient(BaseWorkerClient):
    """Client for interacting with the validation service."""

    def __init__(self):
        self.worker_name = VALIDATION_WORKER_NAME
        self.task_name = VALIDATION_TASK_NAME
        self.worker_queue = VALIDATION_QUEUE
        self.worker_callback_queue = VALIDATION_CALLBACK_QUEUE


validation_worker_client = ValidationWorkerClient()


# Backward compatibility - function used by orchestrator graph
async def validate_file_worker_redis(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Function called by orchestrator workflow graph.
    Delegates to the validation service via Redis.
    """
    return await validation_worker_client.process_file_by_the_worker(state)
` to connect to the next services. 

I also use Redis and PostgreSQL in docker, so have that in mind. But also I use them in other projects, and I will give you an example how: `# Docker Compose file is used to define and run multi-container Docker applications.
version: '3.8'

services:
  web:
    build:
      context: .
      dockerfile: Dockerfile
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - .:/app
      - media_volume:/app/media_files  # Persistent media storage
    ports:
      - "8000:8000"
    environment:
      - DOCKER=True
      - DATABASE_URL=postgresql://postgres_user:password@db/ohmi_audit_db
      - DEBUG=True
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/"]
      interval: 30s
      timeout: 10s
      retries: 3

  db:
    image: postgres:13
    environment:
      - POSTGRES_DB=ohmi_audit_db
      - POSTGRES_USER=postgres_user
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data/
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres_user -d ohmi_audit_db"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:  # Add this if using Redis
    image: redis:6
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
        test: ["CMD", "redis-cli", "ping"]
        interval: 30s
        timeout: 10s
        retries: 3

  celery:
    build: .
    command: celery -A ohmi_audit worker --loglevel=info
    volumes:
      - .:/app
    environment:
      - DOCKER=True
      - USE_CELERY=True
      - DATABASE_URL=postgresql://postgres_user:password@db/ohmi_audit_db
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    healthcheck:
      test: ["CMD-SHELL", "celery -A ohmi_audit status 2>&1 | grep -q '1 node'"]
      interval: 30s
      timeout: 20s
      start_period: 15s  # Since your worker starts in 5s
      retries: 2

volumes:
  media_volume:
  postgres_data:
  redis_data:`, so please dont make conflicts between the projects.

Help me containerize all applications and dependencies, so I can later deploy on a cloud.