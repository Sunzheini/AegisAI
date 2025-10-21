"""
Media Processing Service
------------------
Standalone service that executes media processing tasks.
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
MEDIA_PROCESSING_QUEUE = os.getenv("MEDIA_PROCESSING_QUEUE", "media_processing_queue")
MEDIA_PROCESSING_CALLBACK_QUEUE = os.getenv("MEDIA_PROCESSING_CALLBACK_QUEUE", "media_processing_callback_queue")


# Media processing constraints


logger = LoggingManager.setup_logging(
    service_name="media-processing-service",
    log_file_path="logs/media_processing_service.log",
    log_level=logging.INFO
)


@asynccontextmanager
async def lifespan(app):
    """Lifespan context manager to start/stop Redis listener."""
    logger.info("Starting Media Processing Service...")

    # Create RedisManager
    redis_manager = RedisManager()

    # Create media processing service and inject RedisManager
    media_processing_service = MediaProcessingService()
    ResolveNeedsManager.resolve_needs(media_processing_service)

    # Store in app.state
    app.state.media_processing_service = media_processing_service
    app.state.redis_manager = redis_manager

    print("[MediaProcessingService] Starting Redis listener...")
    logger.info("Starting Redis listener...")
    task = asyncio.create_task(redis_listener(media_processing_service))
    yield
    print("[MediaProcessingService] Shutting down Redis listener.")
    logger.info("Shutting down Redis listener.")
    task.cancel()
    await app.state.redis_manager.close()


app = FastAPI(title="Media Processing Service", lifespan=lifespan)
app.add_middleware(ErrorMiddleware)
app.add_middleware(EnhancedLoggingMiddleware, service_name="media-processing-service")


class MediaProcessingService(INeedRedisManagerInterface):
    """Handles file media processing tasks using shared RedisManager."""

    def __init__(self):
        self.logger = logging.getLogger("media-processing-service")

        # Instance-level configuration


    async def process_media_processing_task(self, task_data: dict) -> dict:
        """Process media processing task using shared Redis connection."""
        try:
            state = WorkflowGraphState(**task_data)
            result_state = await self._process_media_file_worker(state)
            return dict(result_state)
        except Exception as e:
            self.logger.error(f"Media processing failed: {e}")
            return {
                "job_id": task_data.get("job_id"),
                "status": "failed",
                "step": "media_process_file_failed",
                "metadata": {"errors": [str(e)]},
                "updated_at": self._current_timestamp()
            }

    # region Media Processing Methods

    # endregion

    async def _process_media_file_worker(self, state: WorkflowGraphState) -> WorkflowGraphState:
        """
        Media processes the file...
        Updates the job state with the results of the media processing.
        Args:
            state (WorkflowGraphState): The job state dictionary containing file metadata and path.
        Returns:
            WorkflowGraphState: Updated job state after media processing.
        """
        print(f"[Worker:media_process_file] Job {state['job_id']} media processing...")
        await asyncio.sleep(0.5)
        errors = []

        # -------------------------------------------------------------------------------
        # The real media processing!
        # -------------------------------------------------------------------------------

        # -------------------------------------------------------------------------------
        if errors:
            state["status"] = "failed"
            state["step"] = "media_process_file_failed"
            state["metadata"] = {"errors": errors}

        else:
            state["status"] = "success"
            state["step"] = "media_process_file_done"
            state["metadata"] = {"media_processing": "passed"}

        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        print(f"[Worker:media_process_file] Job {state['job_id']} media processing done. State: {state}")
        return state

    @staticmethod
    def _current_timestamp():
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "media_processing"}


# ----------------------------------------------------------------------------------------------
# Redis listener to subscribe to validation tasks
# ----------------------------------------------------------------------------------------------
async def redis_listener(media_processing_service: MediaProcessingService):
    """Redis listener using shared RedisManager."""
    redis_client = await media_processing_service.redis_manager.get_redis_client()
    pubsub = redis_client.pubsub()

    try:
        await pubsub.subscribe(MEDIA_PROCESSING_QUEUE)
        print(f"[MediaProcessingService] Listening on '{MEDIA_PROCESSING_QUEUE}'...")

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    task = json.loads(message["data"])
                    job_id = task.get("job_id", "unknown")
                    print(f"[MediaProcessingService] Processing job: {job_id}")

                    result = await media_processing_service.process_media_processing_task(task)

                    # Use shared Redis connection to publish result
                    await redis_client.publish(
                        MEDIA_PROCESSING_CALLBACK_QUEUE,
                        json.dumps({"job_id": job_id, "result": result})
                    )
                    print(f"[MediaProcessingService] Published result for: {job_id}")

                except Exception as e:
                    print(f"[MediaProcessingService] Error: {e}")

    except asyncio.CancelledError:
        print("[MediaProcessingService] Listener cancelled")
    finally:
        await pubsub.unsubscribe(MEDIA_PROCESSING_QUEUE)
        await pubsub.close()
