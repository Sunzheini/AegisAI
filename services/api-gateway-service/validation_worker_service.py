"""
Validation Service
------------------
Standalone service that processes validation tasks.
Uses RedisManager for consistent connection management.
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI
from contracts.job_schemas import WorkflowGraphState
from custom_middleware.error_middleware import ErrorMiddleware
from needs.INeedRedisManager import INeedRedisManagerInterface
from needs.ResolveNeedsManager import ResolveNeedsManager
from redis_management.redis_manager import RedisManager


# Configuration
VALIDATION_QUEUE = os.getenv("VALIDATION_QUEUE", "validation_queue")
VALIDATION_CALLBACK_QUEUE = os.getenv("VALIDATION_CALLBACK_QUEUE", "validation_callback_queue")




from logging_management import LoggingManager
from custom_middleware.logging_middleware import EnhancedLoggingMiddleware

logger = LoggingManager.setup_logging(
    service_name="validation-service",
    log_file_path="logs/validation_service.log",
    log_level=logging.INFO
)





@asynccontextmanager
async def lifespan(app):
    """Lifespan context manager to start/stop Redis listener."""
    logger.info("Starting Validation Service...")

    # Create RedisManager
    redis_manager = RedisManager()

    # Create validation service and inject RedisManager
    validation_service = ValidationService()
    ResolveNeedsManager.resolve_needs(validation_service)

    # Store in app.state
    app.state.validation_service = validation_service
    app.state.redis_manager = redis_manager

    print("[ValidationService] Starting Redis listener...")
    logger.info("Starting Redis listener...")
    task = asyncio.create_task(redis_listener(validation_service))
    yield
    print("[ValidationService] Shutting down Redis listener.")
    logger.info("Shutting down Redis listener.")
    task.cancel()
    await app.state.redis_manager.close()


app = FastAPI(title="Validation Service", lifespan=lifespan)
app.add_middleware(ErrorMiddleware)






app.add_middleware(EnhancedLoggingMiddleware, service_name="validation-service")








class ValidationService(INeedRedisManagerInterface):
    """Handles file validation tasks using shared RedisManager."""

    def __init__(self):
        self.logger = logging.getLogger("validation-service")

    async def process_validation_task(self, task_data: dict) -> dict:
        """Process validation task using shared Redis connection."""
        try:
            state = WorkflowGraphState(**task_data)
            result_state = await self._validate_file_worker(state)
            return dict(result_state)
        except Exception as e:
            self.logger.error(f"Validation failed: {e}")
            return {
                "job_id": task_data.get("job_id"),
                "status": "failed",
                "step": "validate_file_failed",
                "metadata": {"errors": [str(e)]},
                "updated_at": self._current_timestamp()
            }

    @staticmethod
    async def _validate_file_worker(state: WorkflowGraphState) -> WorkflowGraphState:
        """
        Validates the file type, size, and integrity for an ingestion job.
        Updates the job state with validation results.
        Args:
            state (WorkflowGraphState): The job state dictionary containing file metadata and path.
        Returns:
            WorkflowGraphState: Updated job state after validation.
        """
        print(f"[Worker:validate_file] Job {state['job_id']} validating...")
        await asyncio.sleep(0.5)
        errors = []

        # Example validation: file type must be pdf, image, or video
        allowed_types = ["application/pdf", "image/jpeg", "image/png", "video/mp4"]
        if state["content_type"] not in allowed_types:
            errors.append(f"Unsupported file type: {state['content_type']}")

        # Example checksum validation (simulate failure if checksum ends with '0')
        if state["checksum_sha256"].endswith("0"):
            errors.append("Checksum validation failed.")

        if errors:
            state["status"] = "failed"
            state["step"] = "validate_file_failed"
            state["metadata"] = {"errors": errors}

        else:
            state["status"] = "success"
            state["step"] = "validate_file_done"
            state["metadata"] = {"validation": "passed"}

        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        print(f"[Worker:validate_file] Job {state['job_id']} validation done. State: {state}")
        return state

    @staticmethod
    def _current_timestamp():
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "validation"}


# ----------------------------------------------------------------------------------------------
# Redis listener to subscribe to validation tasks
# ----------------------------------------------------------------------------------------------
async def redis_listener(validation_service: ValidationService):
    """Redis listener using shared RedisManager."""
    redis_client = await validation_service.redis_manager.get_redis_client()
    pubsub = redis_client.pubsub()

    try:
        await pubsub.subscribe(VALIDATION_QUEUE)
        print(f"[ValidationService] Listening on '{VALIDATION_QUEUE}'...")

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    task = json.loads(message["data"])
                    job_id = task.get("job_id", "unknown")
                    print(f"[ValidationService] Processing job: {job_id}")

                    result = await validation_service.process_validation_task(task)

                    # Use shared Redis connection to publish result
                    await redis_client.publish(
                        VALIDATION_CALLBACK_QUEUE,
                        json.dumps({"job_id": job_id, "result": result})
                    )
                    print(f"[ValidationService] Published result for: {job_id}")

                except Exception as e:
                    print(f"[ValidationService] Error: {e}")

    except asyncio.CancelledError:
        print("[ValidationService] Listener cancelled")
    finally:
        await pubsub.unsubscribe(VALIDATION_QUEUE)
        await pubsub.close()
