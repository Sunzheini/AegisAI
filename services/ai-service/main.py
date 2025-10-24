"""
AI Service
------------------
Standalone service that executes tasks using LLM calls.
Uses RedisManager for consistent connection management.
"""
import os
import json
import asyncio
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

from shared_lib.contracts.job_schemas import WorkflowGraphState
from shared_lib.needs.INeedRedisManager import INeedRedisManagerInterface
from shared_lib.needs.ResolveNeedsManager import ResolveNeedsManager
from shared_lib.redis_management.redis_manager import RedisManager
from shared_lib.custom_middleware.error_middleware import ErrorMiddleware
from shared_lib.custom_middleware.logging_middleware import EnhancedLoggingMiddleware
from shared_lib.logging_management.logging_manager import LoggingManager


# Configuration
AI_QUEUE = os.getenv("AI_QUEUE", "ai_queue")
AI_CALLBACK_QUEUE = os.getenv("AI_CALLBACK_QUEUE", "ai_callback_queue")

# Upload/raw storage location constant (configurable)
UPLOAD_DIR = Path(os.getenv("PROCESSED_DIR", "storage/processed")).resolve()

# ai processing constraints


logger = LoggingManager.setup_logging(
    service_name="ai-service",
    log_file_path="logs/ai_service.log",
    log_level=logging.INFO,
)


@asynccontextmanager
async def lifespan(app):
    """Lifespan context manager to start/stop Redis listener."""
    logger.info("Starting AI Service...")

    # Create RedisManager
    redis_manager = RedisManager()

    # Create ai service and inject RedisManager
    ai_service = AIService()
    ResolveNeedsManager.resolve_needs(ai_service)

    # Store in app.state
    app.state.extract_text_service = ai_service
    app.state.redis_manager = redis_manager

    print("[AIService] Starting Redis listener...")
    logger.info("Starting Redis listener...")
    task = asyncio.create_task(redis_listener(ai_service))
    yield
    print("[AIService] Shutting down Redis listener.")
    logger.info("Shutting down Redis listener.")
    task.cancel()
    await app.state.redis_manager.close()


app = FastAPI(title="AI Service", lifespan=lifespan)
app.add_middleware(ErrorMiddleware)
app.add_middleware(EnhancedLoggingMiddleware, service_name="ai-service")


class AIService(INeedRedisManagerInterface):
    """Handles ai processing tasks using shared RedisManager."""

    def __init__(self):
        self.logger = logging.getLogger("ai-service")

        # Instance-level configuration

    async def process_ai_task(self, task_data: dict) -> dict:
        """Process ai task using shared Redis connection."""
        try:
            state = WorkflowGraphState(**task_data)
            result_state = await self._process_ai_worker(state)
            return dict(result_state)
        except Exception as e:
            self.logger.error(f"AI processing failed: {e}")
            return {
                "job_id": task_data.get("job_id"),
                "status": "failed",
                "step": "ai_processing_failed",
                "metadata": {"errors": [str(e)]},
                "updated_at": self._current_timestamp(),
            }

    # region AI Processing Methods

    # endregion

    async def _process_ai_worker(self, state: WorkflowGraphState) -> WorkflowGraphState:
        """
        Processing with AI.
        Updates the job state with the results of the ai processing.
        Args:
            state (WorkflowGraphState): The job state dictionary containing file metadata and path.
        Returns:
            WorkflowGraphState: Updated job state after ai processing.
        """
        print(f"[Worker:ai_processing_file] Job {state['job_id']} ai processing...")
        await asyncio.sleep(0.5)
        errors = []

        # -------------------------------------------------------------------------------
        # The real AI processing!
        # -------------------------------------------------------------------------------

        # -------------------------------------------------------------------------------
        if errors:
            state["status"] = "failed"
            state["step"] = "ai_processing_failed"
            state["metadata"] = {"errors": errors}

        else:
            state["status"] = "success"
            state["step"] = "ai_processing_done"
            state["metadata"] = {"ai_processing": "passed"}

        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        print(
            f"[Worker:ai_processing] Job {state['job_id']} ai processing done. State: {state}"
        )
        return state

    @staticmethod
    def _current_timestamp():
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ai_processing"}


# ----------------------------------------------------------------------------------------------
# Redis listener to subscribe to validation tasks
# ----------------------------------------------------------------------------------------------
async def redis_listener(ai_service: AIService):
    """Redis listener using shared RedisManager."""
    redis_client = await ai_service.redis_manager.get_redis_client()
    pubsub = redis_client.pubsub()

    try:
        await pubsub.subscribe(AI_QUEUE)
        print(f"[AIService] Listening on '{AI_QUEUE}'...")

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    task = json.loads(message["data"])
                    job_id = task.get("job_id", "unknown")
                    print(f"[AIService] Processing job: {job_id}")

                    result = await ai_service.process_ai_task(task)

                    # Use shared Redis connection to publish result
                    await redis_client.publish(
                        AI_CALLBACK_QUEUE,
                        json.dumps({"job_id": job_id, "result": result}),
                    )
                    print(f"[AIService] Published result for: {job_id}")

                except Exception as e:
                    print(f"[AIService] Error: {e}")

    except asyncio.CancelledError:
        print("[AIService] Listener cancelled")
    finally:
        await pubsub.unsubscribe(AI_QUEUE)
        await pubsub.close()
