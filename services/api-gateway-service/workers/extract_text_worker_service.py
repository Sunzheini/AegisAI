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

# Conditional import for shared library usage ----------------------------------------------
USE_SHARED_LIB = os.getenv("USE_SHARED_LIB", False)
if USE_SHARED_LIB:
    from shared_lib.contracts.job_schemas import WorkflowGraphState
else:
    from contracts.job_schemas import WorkflowGraphState
# ------------------------------------------------------------------------------------------

from custom_middleware.error_middleware import ErrorMiddleware
from needs.INeedRedisManager import INeedRedisManagerInterface
from needs.ResolveNeedsManager import ResolveNeedsManager
from redis_management.redis_manager import RedisManager
from logging_management.logging_manager import LoggingManager
from custom_middleware.logging_middleware import EnhancedLoggingMiddleware


# Configuration
EXTRACT_TEXT_QUEUE = os.getenv("EXTRACT_TEXT_QUEUE", "extract_text_queue")
EXTRACT_TEXT_CALLBACK_QUEUE = os.getenv(
    "EXTRACT_TEXT_CALLBACK_QUEUE", "extract_text_callback_queue"
)

# Upload/raw storage location constant (configurable)
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "storage/raw")).resolve()
PROCESSED_DIR = Path(os.getenv("PROCESSED_DIR", "storage/processed")).resolve()


logger = LoggingManager.setup_logging(
    service_name="extract-text-service",
    log_file_path="logs/extract_text_service.log",
    log_level=logging.INFO,
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
                "updated_at": self._current_timestamp(),
            }

    # region Extract Text Methods
    @staticmethod
    async def _extract_text_from_pdf(file_path: str) -> dict:
        """Extract text from PDF using pdfplumber."""
        result = {
            "extracted_text": "",
            "character_count": 0,
            "page_count": 0,
            "pages_with_text": 0,
            "extraction_errors": [],
        }

        try:
            import pdfplumber

            with pdfplumber.open(file_path) as pdf:
                result["page_count"] = len(pdf.pages)

                for page_num, page in enumerate(pdf.pages):
                    try:
                        page_text = page.extract_text() or ""
                        if page_text.strip():
                            result["pages_with_text"] += 1
                            result[
                                "extracted_text"
                            ] += f"--- Page {page_num + 1} ---\n{page_text}\n\n"
                            result["character_count"] += len(page_text)
                    except Exception as page_error:
                        error_msg = f"Page {page_num + 1}: {str(page_error)}"
                        result["extraction_errors"].append(error_msg)

        except ImportError:
            result["extraction_errors"].append(
                "pdfplumber not installed. Install with: pip install pdfplumber"
            )
        except Exception as e:
            result["extraction_errors"].append(f"PDF extraction failed: {str(e)}")

        return result

    @staticmethod
    async def _save_extracted_text_to_file(
        job_id: str, extracted_text: str, character_count: int
    ) -> str:
        """Save extracted text to a file in processed directory."""
        try:
            # Create text file path
            text_filename = f"{job_id}_extracted_text.txt"
            text_file_path = PROCESSED_DIR / text_filename

            # Save text to file
            with open(text_file_path, "w", encoding="utf-8") as f:
                f.write(extracted_text)

            # Add file stats
            file_stats = {
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "file_size_bytes": os.path.getsize(text_file_path),
                "character_count": character_count,
                "file_path": str(text_file_path),
            }

            return str(text_file_path), file_stats

        except Exception as e:
            raise Exception(f"Failed to save extracted text: {str(e)}")

    @staticmethod
    async def _analyze_text_content(extracted_text: str) -> dict:
        """Perform basic text analysis."""
        analysis = {
            "word_count": 0,
            "paragraph_count": 0,
            "avg_words_per_page": 0,
            "language_indicators": {},
            "content_categories": [],
        }

        if not extracted_text.strip():
            return analysis

        try:
            # Basic word count
            words = extracted_text.split()
            analysis["word_count"] = len(words)

            # Paragraph count (rough estimate)
            paragraphs = [p for p in extracted_text.split("\n\n") if p.strip()]
            analysis["paragraph_count"] = len(paragraphs)

            # Simple content categorization
            text_lower = extracted_text.lower()
            technical_terms = [
                "microcontroller",
                "datasheet",
                "voltage",
                "circuit",
                "processor",
            ]
            analysis_terms = [term for term in technical_terms if term in text_lower]

            if analysis_terms:
                analysis["content_categories"] = ["technical_document", "datasheet"]
            elif len(words) > 1000:
                analysis["content_categories"] = ["long_document"]
            else:
                analysis["content_categories"] = ["general_document"]

        except Exception as e:
            analysis["analysis_errors"] = [f"Text analysis failed: {str(e)}"]

        return analysis

    # endregion

    async def _process_extract_text_worker(
        self, state: WorkflowGraphState
    ) -> WorkflowGraphState:
        """
        Extracting text from file.
        Updates the job state with the results of the extracting text.

        The extracted text will be saved in two places:
        1) in state["metadata"]["text_extraction"]
        2) storage/processed/...txt

        Args:
            state (WorkflowGraphState): The job state dictionary containing file metadata and path.
        Returns:
            WorkflowGraphState: Updated job state after extracting text.
        """
        print(
            f"[Worker:extract_text_from_file] Job {state['job_id']} extracting text..."
        )
        await asyncio.sleep(0.5)
        errors = []

        # -------------------------------------------------------------------------------
        # The real text extraction!
        # -------------------------------------------------------------------------------
        extraction_result = {}

        try:
            # Check if file exists and is PDF
            file_path = state["file_path"]
            if not os.path.exists(file_path):
                errors.append(f"File not found: {file_path}")
            elif state["content_type"] != "application/pdf":
                errors.append(
                    f"Text extraction only supported for PDF files. Got: {state['content_type']}"
                )
            else:
                # Extract text from PDF
                extraction_result = await self._extract_text_from_pdf(file_path)

                if extraction_result["extraction_errors"]:
                    errors.extend(extraction_result["extraction_errors"])

                # Only proceed if we have extracted text
                if extraction_result["character_count"] > 0:

                    # Save extracted text to file
                    text_file_path, file_stats = (
                        await self._save_extracted_text_to_file(
                            state["job_id"],
                            extraction_result["extracted_text"],
                            extraction_result["character_count"],
                        )
                    )

                    # Analyze text content
                    text_analysis = await self._analyze_text_content(
                        extraction_result["extracted_text"]
                    )

                    # Update state metadata with extraction results
                    state["metadata"].update(
                        {
                            "text_extraction": {
                                "success": True,
                                "extracted_character_count": extraction_result[
                                    "character_count"
                                ],
                                "total_pages": extraction_result["page_count"],
                                "pages_with_text": extraction_result["pages_with_text"],
                                "text_file_path": text_file_path,
                                "file_stats": file_stats,
                                "content_analysis": text_analysis,
                                "extraction_time": datetime.now(
                                    timezone.utc
                                ).isoformat(),
                            }
                        }
                    )

                    # Add preview of first 500 characters
                    preview_text = extraction_result["extracted_text"][:500]
                    if len(extraction_result["extracted_text"]) > 500:
                        preview_text += "..."
                    state["metadata"]["text_extraction"]["text_preview"] = preview_text

                else:
                    errors.append("No text could be extracted from the PDF")

        except Exception as e:
            errors.append(f"Text extraction process failed: {str(e)}")

        # -------------------------------------------------------------------------------
        if errors:
            state["status"] = "failed"
            state["step"] = "extract_text_failed"
            state["metadata"][
                "errors"
            ] = errors  # Preserve existing metadata but add errors

            if (
                extraction_result
            ):  # Still include any partial extraction results if available
                state["metadata"]["text_extraction"] = {
                    "success": False,
                    "errors": errors,
                    "partial_results": extraction_result,
                }

        else:
            state["status"] = "success"
            state["step"] = "extract_text_done"
            state["metadata"][
                "extract_text"
            ] = "passed"  # Don't overwrite m-data, add success flag

        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        print(
            f"[Worker:extract_text] Job {state['job_id']} extracting text done. State: {state}"
        )
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
                        json.dumps({"job_id": job_id, "result": result}),
                    )
                    print(f"[ExtractTextService] Published result for: {job_id}")

                except Exception as e:
                    print(f"[ExtractTextService] Error: {e}")

    except asyncio.CancelledError:
        print("[ExtractTextService] Listener cancelled")
    finally:
        await pubsub.unsubscribe(EXTRACT_TEXT_QUEUE)
        await pubsub.close()
