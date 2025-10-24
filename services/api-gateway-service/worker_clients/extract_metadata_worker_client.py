"""
Extract Metadata Worker Client for Orchestrator
----------------------------------
Lightweight client that publishes extract metadata tasks to Redis and waits for results.
Used by the workflow orchestrator.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

if os.path.exists(os.path.join(BASE_DIR, '.env')):
    load_dotenv()

# Conditional import for shared library usage ----------------------------------------------
USE_SHARED_LIB = os.getenv("USE_SHARED_LIB", False)
if USE_SHARED_LIB:
    from shared_lib.contracts.job_schemas import WorkflowGraphState
    from shared_lib.worker_clients.base_worker_client import BaseWorkerClient
else:
    from contracts.job_schemas import WorkflowGraphState
    from worker_clients.base_worker_client import BaseWorkerClient
# ------------------------------------------------------------------------------------------


# Specific Configuration
EXTRACT_METADATA_WORKER_NAME = os.getenv(
    "EXTRACT_METADATA_WORKER_NAME", "ExtractMetadataWorker"
)
EXTRACT_METADATA_TASK_NAME = os.getenv("EXTRACT_METADATA_TASK_NAME", "extract metadata")
EXTRACT_METADATA_QUEUE = os.getenv("EXTRACT_METADATA_QUEUE", "extract_metadata_queue")
EXTRACT_METADATA_CALLBACK_QUEUE = os.getenv(
    "EXTRACT_METADATA_CALLBACK_QUEUE", "extract_metadata_callback_queue"
)


class ExtractMetadataWorkerClient(BaseWorkerClient):
    """Client for interacting with the extract metadata service."""

    def __init__(self):
        self.worker_name = EXTRACT_METADATA_WORKER_NAME
        self.task_name = EXTRACT_METADATA_TASK_NAME
        self.worker_queue = EXTRACT_METADATA_QUEUE
        self.worker_callback_queue = EXTRACT_METADATA_CALLBACK_QUEUE


extract_metadata_worker_client = ExtractMetadataWorkerClient()


# Backward compatibility - function used by orchestrator graph
async def extract_metadata_from_file_worker_redis(
    state: WorkflowGraphState,
) -> WorkflowGraphState:
    """
    Function called by orchestrator workflow graph.
    Delegates to the extract metadata service via Redis.
    """
    return await extract_metadata_worker_client.process_file_by_the_worker(state)
