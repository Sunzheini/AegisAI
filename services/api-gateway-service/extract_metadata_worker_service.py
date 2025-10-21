"""
Extract Metadata Service
------------------
Standalone service that executes extract metadata tasks.
Uses RedisManager for consistent connection management.
"""
import os
import json
import asyncio
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from contracts.job_schemas import WorkflowGraphState
from custom_middleware.error_middleware import ErrorMiddleware
from needs.INeedRedisManager import INeedRedisManagerInterface
from needs.ResolveNeedsManager import ResolveNeedsManager
from redis_management.redis_manager import RedisManager
from logging_management import LoggingManager
from custom_middleware.logging_middleware import EnhancedLoggingMiddleware


# Configuration
EXTRACT_METADATA_QUEUE = os.getenv("EXTRACT_METADATA_QUEUE", "extract_metadata_queue")
EXTRACT_METADATA_CALLBACK_QUEUE = os.getenv("EXTRACT_METADATA_CALLBACK_QUEUE", "extract_metadata_callback_queue")


# Extract metadata constraints


logger = LoggingManager.setup_logging(
    service_name="extract-metadata-service",
    log_file_path="logs/extract_metadata_service.log",
    log_level=logging.INFO
)


@asynccontextmanager
async def lifespan(app):
    """Lifespan context manager to start/stop Redis listener."""
    logger.info("Starting Extract Metadata Service...")

    # Create RedisManager
    redis_manager = RedisManager()

    # Create extract metadata service and inject RedisManager
    extract_metadata_service = ExtractMetadataService()
    ResolveNeedsManager.resolve_needs(extract_metadata_service)

    # Store in app.state
    app.state.extract_metadata_service = extract_metadata_service
    app.state.redis_manager = redis_manager

    print("[ExtractMetadataService] Starting Redis listener...")
    logger.info("Starting Redis listener...")
    task = asyncio.create_task(redis_listener(extract_metadata_service))
    yield
    print("[ExtractMetadataService] Shutting down Redis listener.")
    logger.info("Shutting down Redis listener.")
    task.cancel()
    await app.state.redis_manager.close()


app = FastAPI(title="Extract Metadata Service", lifespan=lifespan)
app.add_middleware(ErrorMiddleware)
app.add_middleware(EnhancedLoggingMiddleware, service_name="extract-metadata-service")


class ExtractMetadataService(INeedRedisManagerInterface):
    """Handles file metadata extraction tasks using shared RedisManager."""

    def __init__(self):
        self.logger = logging.getLogger("extract-metadata-service")

        # Instance-level configuration


    async def process_extract_metadata_task(self, task_data: dict) -> dict:
        """Process extract metadata task using shared Redis connection."""
        try:
            state = WorkflowGraphState(**task_data)
            result_state = await self._process_extract_metadata_worker(state)
            return dict(result_state)
        except Exception as e:
            self.logger.error(f"Extract metadata failed: {e}")
            return {
                "job_id": task_data.get("job_id"),
                "status": "failed",
                "step": "extract_metadata_from_file_failed",
                "metadata": {"errors": [str(e)]},
                "updated_at": self._current_timestamp()
            }

    # region Media Processing Methods

    # endregion

    async def _process_extract_metadata_worker(self, state: WorkflowGraphState) -> WorkflowGraphState:
        """
        Extracting metadata from file.
        Updates the job state with the results of the extracting metadata.
        Args:
            state (WorkflowGraphState): The job state dictionary containing file metadata and path.
        Returns:
            WorkflowGraphState: Updated job state after extracting metadata.
        """
        print(f"[Worker:extract_metadata_from_file] Job {state['job_id']} extracting metadata...")
        await asyncio.sleep(0.5)
        errors = []

        # -------------------------------------------------------------------------------
        # The real metadata extraction!
        # -------------------------------------------------------------------------------

        # -------------------------------------------------------------------------------
        if errors:
            state["status"] = "failed"
            state["step"] = "extract_metadata_from_file_failed"
            state["metadata"] = {"errors": errors}

        else:
            state["status"] = "success"
            state["step"] = "extract_metadata_from_file_done"
            state["metadata"] = {"extracting_metadata": "passed"}

        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        print(f"[Worker:extract_metadata_from_file] Job {state['job_id']} extracting metadata done. State: {state}")
        return state

    @staticmethod
    def _current_timestamp():
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "extracting_metadata"}


# ----------------------------------------------------------------------------------------------
# Redis listener to subscribe to validation tasks
# ----------------------------------------------------------------------------------------------
async def redis_listener(extract_metadata_service: ExtractMetadataService):
    """Redis listener using shared RedisManager."""
    redis_client = await extract_metadata_service.redis_manager.get_redis_client()
    pubsub = redis_client.pubsub()

    try:
        await pubsub.subscribe(EXTRACT_METADATA_QUEUE)
        print(f"[ExtractMetadataService] Listening on '{EXTRACT_METADATA_QUEUE}'...")

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    task = json.loads(message["data"])
                    job_id = task.get("job_id", "unknown")
                    print(f"[ExtractMetadataService] Processing job: {job_id}")

                    result = await extract_metadata_service.process_extract_metadata_task(task)

                    # Use shared Redis connection to publish result
                    await redis_client.publish(
                        EXTRACT_METADATA_CALLBACK_QUEUE,
                        json.dumps({"job_id": job_id, "result": result})
                    )
                    print(f"[ExtractMetadataService] Published result for: {job_id}")

                except Exception as e:
                    print(f"[ExtractMetadataService] Error: {e}")

    except asyncio.CancelledError:
        print("[ExtractMetadataService] Listener cancelled")
    finally:
        await pubsub.unsubscribe(EXTRACT_METADATA_QUEUE)
        await pubsub.close()
