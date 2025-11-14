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

# ToDO: changed
import boto3
import tempfile
from botocore.exceptions import ClientError
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
EXTRACT_TEXT_QUEUE = os.getenv("EXTRACT_TEXT_QUEUE", "extract_text_queue")
EXTRACT_TEXT_CALLBACK_QUEUE = os.getenv(
    "EXTRACT_TEXT_CALLBACK_QUEUE", "extract_text_callback_queue"
)

# ToDO: changed
# ------------------------------------------------------------------------------------------
USE_AWS = os.getenv("USE_AWS", "false").lower() == "true"
if not USE_AWS:
    UPLOAD_DIR = Path(os.getenv("RAW_DIR", "storage/raw")).resolve()
    PROCESSED_DIR = Path(os.getenv("PROCESSED_DIR", "storage/processed")).resolve()
else:
    UPLOAD_DIR = os.getenv("RAW_DIR_AWS", "aegisai-raw-danielzorov")
    PROCESSED_DIR = os.getenv("PROCESSED_DIR_AWS", "aegisai-processed-danielzorov")

    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_REGION = os.getenv("AWS_REGION_NAME", "")

    s3_client = boto3.client(
        's3',
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", ""),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", ""),
        region_name=os.getenv("AWS_REGION_NAME", "us-east-1"),
    )

# ------------------------------------------------------------------------------------------
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

        # ToDo: changed
        self.s3_client = s3_client

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

    # Todo: changed
    # region AWS methods
    def _parse_s3_path(self, file_path: str) -> tuple:
        """Parse S3 URI into bucket and key."""
        bucket_key = file_path[5:]  # Remove 's3://'
        bucket_name, key = bucket_key.split('/', 1)
        return bucket_name, key

    async def _download_from_s3_if_needed(self, file_path: str) -> str:
        """Download file from S3 if path is an S3 URI, return local temp path."""
        if not USE_AWS:
            return file_path

        bucket_name, key = self._parse_s3_path(file_path)
        temp_dir = tempfile.gettempdir()
        local_path = os.path.join(temp_dir, os.path.basename(key))

        try:
            self.s3_client.download_file(bucket_name, key, local_path)
            return local_path
        except ClientError as e:
            raise Exception(f"S3 download failed: {e}")

    # endregion

    # region Extract Text Methods
    @staticmethod
    async def _extract_text_from_pdf(file_path: str) -> dict:
        """Extract text from PDF using pdfplumber in a thread pool."""
        result = {
            "extracted_text": "",
            "character_count": 0,
            "page_count": 0,
            "pages_with_text": 0,
            "extraction_errors": [],
        }

        try:
            import pdfplumber

            # Wrap the synchronous PDF processing in a thread
            def extract_pdf_sync():
                pdf_result = {
                    "extracted_text": "",
                    "character_count": 0,
                    "page_count": 0,
                    "pages_with_text": 0,
                    "extraction_errors": [],
                }

                try:
                    with pdfplumber.open(file_path) as pdf:
                        pdf_result["page_count"] = len(pdf.pages)

                        for page_num, page in enumerate(pdf.pages):
                            try:
                                page_text = page.extract_text() or ""
                                if page_text.strip():
                                    pdf_result["pages_with_text"] += 1
                                    pdf_result["extracted_text"] += f"--- Page {page_num + 1} ---\n{page_text}\n\n"
                                    pdf_result["character_count"] += len(page_text)
                            except Exception as page_error:
                                error_msg = f"Page {page_num + 1}: {str(page_error)}"
                                pdf_result["extraction_errors"].append(error_msg)
                except Exception as e:
                    pdf_result["extraction_errors"].append(f"PDF extraction failed: {str(e)}")

                return pdf_result

            # Run the synchronous PDF processing in a thread pool
            result = await asyncio.to_thread(extract_pdf_sync)

        except ImportError:
            result["extraction_errors"].append(
                "pdfplumber not installed. Install with: pip install pdfplumber"
            )
        except Exception as e:
            result["extraction_errors"].append(f"PDF extraction setup failed: {str(e)}")

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

            # Save text to file asynchronously
            def write_file_sync():
                with open(text_file_path, "w", encoding="utf-8") as f:
                    f.write(extracted_text)
                return text_file_path

            text_file_path = await asyncio.to_thread(write_file_sync)

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
