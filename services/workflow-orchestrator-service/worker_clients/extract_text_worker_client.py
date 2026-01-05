"""
Extract Text (e.g. from a .pdf) Worker Client for Orchestrator
----------------------------------
Lightweight client that publishes extract text tasks to Redis and waits for results.
Used by the workflow orchestrator.
"""

import os

from dotenv import load_dotenv

from shared_lib.contracts.job_schemas import WorkflowGraphState
from shared_lib.worker_clients.base_worker_client import BaseWorkerClient


load_dotenv()


# Specific Configuration
EXTRACT_TEXT_WORKER_NAME = os.getenv("EXTRACT_TEXT_WORKER_NAME", "ExtractTextWorker")
EXTRACT_TEXT_TASK_NAME = os.getenv("EXTRACT_TEXT_TASK_NAME", "extract text")
EXTRACT_TEXT_QUEUE = os.getenv("EXTRACT_TEXT_QUEUE", "extract_text_queue")
EXTRACT_TEXT_CALLBACK_QUEUE = os.getenv(
    "EXTRACT_TEXT_CALLBACK_QUEUE", "extract_text_callback_queue"
)

SPECIFIC_TIMEOUT_SECONDS = 300  # 5 minutes


class ExtractTextWorkerClient(BaseWorkerClient):
    """Client for interacting with the extract text service."""

    def __init__(self):
        self.worker_name = EXTRACT_TEXT_WORKER_NAME
        self.task_name = EXTRACT_TEXT_TASK_NAME
        self.worker_queue = EXTRACT_TEXT_QUEUE
        self.worker_callback_queue = EXTRACT_TEXT_CALLBACK_QUEUE


extract_text_worker_client = ExtractTextWorkerClient()


# Backward compatibility - function used by orchestrator graph
async def extract_text_from_file_worker_redis(
    state: WorkflowGraphState,
) -> WorkflowGraphState:
    """
    Function called by orchestrator workflow graph.
    Delegates to the extract text service via Redis.
    """
    return await extract_text_worker_client.process_file_by_the_worker(
        state, SPECIFIC_TIMEOUT_SECONDS
    )
