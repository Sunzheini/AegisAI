"""
AI Worker Client for Orchestrator
----------------------------------
Lightweight client that publishes ai-related (e.g. summarize text) tasks to Redis and waits for results.
Used by the workflow orchestrator.
"""

import os

# Conditional import for shared library usage ----------------------------------------------
USE_SHARED_LIB = os.getenv("USE_SHARED_LIB", False)
if USE_SHARED_LIB:
    from shared_lib.contracts.job_schemas import WorkflowGraphState
else:
    from contracts.job_schemas import WorkflowGraphState
# ------------------------------------------------------------------------------------------

from worker_clients.base_worker_client import BaseWorkerClient


# Specific Configuration
AI_WORKER_NAME = os.getenv("AI_WORKER_NAME", "AIWorker")
AI_TASK_NAME = os.getenv("AI_TASK_NAME", "process by ai")
AI_QUEUE = os.getenv("AI_QUEUE", "ai_queue")
AI_CALLBACK_QUEUE = os.getenv("AI_CALLBACK_QUEUE", "ai_callback_queue")

SPECIFIC_TIMEOUT_SECONDS = 300  # 5 minutes


class AIWorkerClient(BaseWorkerClient):
    """Client for interacting with the ai service."""

    def __init__(self):
        self.worker_name = AI_WORKER_NAME
        self.task_name = AI_TASK_NAME
        self.worker_queue = AI_QUEUE
        self.worker_callback_queue = AI_CALLBACK_QUEUE


ai_worker_client = AIWorkerClient()


# Backward compatibility - function used by orchestrator graph
async def process_file_by_ai_worker_redis(
    state: WorkflowGraphState,
) -> WorkflowGraphState:
    """
    Function called by orchestrator workflow graph.
    Delegates to the ai service via Redis.
    """
    return await ai_worker_client.process_file_by_the_worker(
        state, SPECIFIC_TIMEOUT_SECONDS
    )
