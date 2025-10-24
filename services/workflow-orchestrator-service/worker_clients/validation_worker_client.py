"""
Validation Worker Client for Orchestrator
----------------------------------
Lightweight client that publishes validation tasks to Redis and waits for results.
Used by the workflow orchestrator.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from shared_lib.contracts.job_schemas import WorkflowGraphState
from shared_lib.worker_clients.base_worker_client import BaseWorkerClient

BASE_DIR = Path(__file__).resolve().parent

if os.path.exists(os.path.join(BASE_DIR, '.env')):
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
