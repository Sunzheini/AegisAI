"""
Extract Text Service
------------------
Standalone service that executes extract text (from a pdf) tasks.
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
from logging_management.logging_manager import LoggingManager
from custom_middleware.logging_middleware import EnhancedLoggingMiddleware


# Configuration
EXTRACT_TEXT_QUEUE = os.getenv("EXTRACT_TEXT_QUEUE", "extract_text_queue")
EXTRACT_TEXT_CALLBACK_QUEUE = os.getenv("EXTRACT_TEXT_CALLBACK_QUEUE", "extract_text_callback_queue")

# Upload/raw storage location constant (configurable)
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "storage/processed")).resolve()

# Extract text constraints


logger = LoggingManager.setup_logging(
    service_name="extract-text-service",
    log_file_path="logs/extract_text_service.log",
    log_level=logging.INFO
)


@asynccontextmanager
async def lifespan(app):
    """Lifespan context manager to start/stop Redis listener."""
    logger.info("Starting Extract Text Service...")

    # Create RedisManager
    redis_manager = RedisManager()

    # Create extract text service and inject RedisManager
    extract_text_service = ExtractTextService()
    ResolveNeedsManager.resolve_needs(extract_text_service)

    # Store in app.state
    app.state.extract_text_service = extract_text_service
    app.state.redis_manager = redis_manager

    print("[ExtractTextService] Starting Redis listener...")
    logger.info("Starting Redis listener...")
    task = asyncio.create_task(redis_listener(extract_text_service))
    yield
    print("[ExtractTextService] Shutting down Redis listener.")
    logger.info("Shutting down Redis listener.")
    task.cancel()
    await app.state.redis_manager.close()


app = FastAPI(title="Extract Text Service", lifespan=lifespan)
app.add_middleware(ErrorMiddleware)
app.add_middleware(EnhancedLoggingMiddleware, service_name="extract-text-service")


class ExtractTextService(INeedRedisManagerInterface):
    """Handles file text extraction tasks using shared RedisManager."""

    def __init__(self):
        self.logger = logging.getLogger("extract-text-service")

        # Instance-level configuration

    async def process_extract_text_task(self, task_data: dict) -> dict:
        """Process extract text task using shared Redis connection."""
        try:
            state = WorkflowGraphState(**task_data)
            result_state = await self._process_extract_text_worker(state)
            return dict(result_state)
        except Exception as e:
            self.logger.error(f"Extract text failed: {e}")
            return {
                "job_id": task_data.get("job_id"),
                "status": "failed",
                "step": "extract_text_from_file_failed",
                "metadata": {"errors": [str(e)]},
                "updated_at": self._current_timestamp()
            }

    # region Extract Text Methods

    # endregion

    async def _process_extract_text_worker(self, state: WorkflowGraphState) -> WorkflowGraphState:
        """
        Extracting text from file.
        Updates the job state with the results of the extracting text.
        Args:
            state (WorkflowGraphState): The job state dictionary containing file metadata and path.
        Returns:
            WorkflowGraphState: Updated job state after extracting text.
        """
        print(f"[Worker:extract_text_from_file] Job {state['job_id']} extracting text...")
        await asyncio.sleep(0.5)
        errors = []

        # -------------------------------------------------------------------------------
        # The real text extraction!
        # -------------------------------------------------------------------------------

        # -------------------------------------------------------------------------------
        if errors:
            state["status"] = "failed"
            state["step"] = "extract_text_failed"
            state["metadata"] = {"errors": errors}

        else:
            state["status"] = "success"
            state["step"] = "extract_text_done"
            state["metadata"] = {"extract_text": "passed"}

        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        print(f"[Worker:extract_text] Job {state['job_id']} extracting text done. State: {state}")
        return state

    @staticmethod
    def _current_timestamp():
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "extracting_text"}


# ----------------------------------------------------------------------------------------------
# Redis listener to subscribe to validation tasks
# ----------------------------------------------------------------------------------------------
async def redis_listener(extract_text_service: ExtractTextService):
    """Redis listener using shared RedisManager."""
    redis_client = await extract_text_service.redis_manager.get_redis_client()
    pubsub = redis_client.pubsub()

    try:
        await pubsub.subscribe(EXTRACT_TEXT_QUEUE)
        print(f"[ExtractTextService] Listening on '{EXTRACT_TEXT_QUEUE}'...")

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    task = json.loads(message["data"])
                    job_id = task.get("job_id", "unknown")
                    print(f"[ExtractTextService] Processing job: {job_id}")

                    result = await extract_text_service.process_extract_text_task(task)

                    # Use shared Redis connection to publish result
                    await redis_client.publish(
                        EXTRACT_TEXT_CALLBACK_QUEUE,
                        json.dumps({"job_id": job_id, "result": result})
                    )
                    print(f"[ExtractTextService] Published result for: {job_id}")

                except Exception as e:
                    print(f"[ExtractTextService] Error: {e}")

    except asyncio.CancelledError:
        print("[ExtractTextService] Listener cancelled")
    finally:
        await pubsub.unsubscribe(EXTRACT_TEXT_QUEUE)
        await pubsub.close()
