"""
Extract Metadata Service
------------------
Standalone service that executes extract metadata tasks.
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
from shared_lib.needs.INeedCloudManager import INeedCloudManagerInterface
from shared_lib.needs.INeedRedisManager import INeedRedisManagerInterface
from shared_lib.needs.ResolveNeedsManager import ResolveNeedsManager
from shared_lib.redis_management.redis_manager import RedisManager
from shared_lib.custom_middleware.error_middleware import ErrorMiddleware
from shared_lib.custom_middleware.logging_middleware import EnhancedLoggingMiddleware
from shared_lib.logging_management.logging_manager import LoggingManager


# Configuration
EXTRACT_METADATA_QUEUE = os.getenv("EXTRACT_METADATA_QUEUE", "extract_metadata_queue")
EXTRACT_METADATA_CALLBACK_QUEUE = os.getenv(
    "EXTRACT_METADATA_CALLBACK_QUEUE", "extract_metadata_callback_queue"
)

USE_AWS = os.getenv("USE_AWS", "false").lower() == "true"
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION = os.getenv("AWS_REGION_NAME", "")

logger = LoggingManager.setup_logging(
    service_name="extract-metadata-service",
    log_file_path="logs/extract_metadata_service.log",
    log_level=logging.INFO,
)


@asynccontextmanager
async def lifespan(app):
    """Lifespan context manager to start/stop Redis listener."""
    logger.info("Starting Extract Metadata Service...")

    # Create RedisManager
    redis_manager = RedisManager()

    # Create extract metadata service and inject needs
    extract_metadata_service = ExtractMetadataService()
    ResolveNeedsManager.resolve_needs(extract_metadata_service)

    # Initialize the cloud client after injection
    extract_metadata_service.cloud_manager.create_s3_client(
        access_key_id=os.getenv("AWS_ACCESS_KEY_ID", ""),
        secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", ""),
        region=os.getenv("AWS_REGION_NAME", "us-east-1"),
    )

    # Store in app.state
    app.state.extract_metadata_service = extract_metadata_service
    app.state.redis_manager = redis_manager

    print("[ExtractMetadataService] Starting Redis listener...")
    logger.info("Starting Redis listener...")
    task = asyncio.create_task(redis_listener(extract_metadata_service))
    yield
    print("[ExtractMetadataService] Shutting down Redis listener.")
    logger.info("Shutting down Redis listener.")
    task.cancel()
    await app.state.redis_manager.close()


app = FastAPI(title="Extract Metadata Service", lifespan=lifespan)
app.add_middleware(ErrorMiddleware)
app.add_middleware(EnhancedLoggingMiddleware, service_name="extract-metadata-service")


class ExtractMetadataService(INeedRedisManagerInterface, INeedCloudManagerInterface):
    """Handles file metadata extraction tasks using shared RedisManager."""

    def __init__(self):
        self.logger = logging.getLogger("extract-metadata-service")

    async def process_extract_metadata_task(self, task_data: dict) -> dict:
        """Process extract metadata task using shared Redis connection."""
        try:
            state = WorkflowGraphState(**task_data)
            result_state = await self._process_extract_metadata_worker(state)
            return dict(result_state)
        except Exception as e:
            self.logger.error(f"Extract metadata failed: {e}")
            return {
                "job_id": task_data.get("job_id"),
                "status": "failed",
                "step": "extract_metadata_from_file_failed",
                "metadata": {"errors": [str(e)]},
                "updated_at": self._current_timestamp(),
            }

    # region Extract Metadata Methods
    async def _extract_universal_metadata(self, state: WorkflowGraphState) -> dict:
        """Extract metadata common to all file types."""
        metadata = {}
        file_path = state["file_path"]

        try:
            # Download from S3 if needed for universal metadata
            local_path = await self.cloud_manager.download_from_s3_if_needed(USE_AWS, file_path)

            try:
                path = Path(local_path)
                stat = path.stat()

                metadata.update(
                    {
                        "file_size": stat.st_size,
                        "file_extension": path.suffix.lower(),
                        "created_timestamp": datetime.fromtimestamp(
                            stat.st_ctime, timezone.utc
                        ).isoformat(),
                        "modified_timestamp": datetime.fromtimestamp(
                            stat.st_mtime, timezone.utc
                        ).isoformat(),
                        "magic_number_verified": await self._verify_magic_number(
                            local_path, state["content_type"]
                        ),
                    }
                )

            finally:
                # Clean up temp file if it was downloaded from S3
                if local_path != file_path and os.path.exists(local_path):
                    os.remove(local_path)

        except Exception as e:
            metadata["universal_metadata_error"] = str(e)

        return metadata

    @staticmethod
    async def _extract_image_metadata(file_path: str) -> dict:
        """Extract image-specific metadata using Pillow."""
        metadata = {}

        try:
            from PIL import Image, ExifTags

            with Image.open(file_path) as img:
                metadata.update(
                    {
                        "dimensions": {
                            "width": img.width,
                            "height": img.height,
                            "aspect_ratio": f"{img.width}:{img.height}",
                        },
                        "color_info": {
                            "mode": img.mode,
                            "has_alpha": img.mode in ("RGBA", "LA", "P"),
                        },
                        "format": img.format,
                    }
                )

                # Extract EXIF data if available
                exif_data = {}
                if hasattr(img, "_getexif") and img._getexif():
                    for tag, value in img._getexif().items():
                        tag_name = ExifTags.TAGS.get(tag, tag)
                        # Convert to string to avoid serialization issues
                        exif_data[tag_name] = str(value)

                if exif_data:
                    metadata["exif_data"] = exif_data

        except Exception as e:
            metadata["image_metadata_error"] = str(e)

        return metadata

    @staticmethod
    async def _extract_video_metadata(file_path: str) -> dict:
        """Extract video metadata using ffprobe."""
        metadata = {}

        try:
            import subprocess
            import json

            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                file_path,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                metadata["video_metadata_error"] = "ffprobe failed to analyze file"
                return metadata

            probe_data = json.loads(result.stdout)

            # Extract basic format info
            format_info = probe_data.get("format", {})
            metadata.update(
                {
                    "duration": float(format_info.get("duration", 0)),
                    "bitrate": int(format_info.get("bit_rate", 0)),
                    "format_name": format_info.get("format_name", "unknown"),
                }
            )

            # Extract stream information
            video_stream = next(
                (
                    s
                    for s in probe_data.get("streams", [])
                    if s.get("codec_type") == "video"
                ),
                None,
            )
            if video_stream:
                metadata["video_stream"] = {
                    "codec": video_stream.get("codec_name"),
                    "width": video_stream.get("width"),
                    "height": video_stream.get("height"),
                    "frame_rate": video_stream.get("r_frame_rate", "unknown"),
                    "pixel_format": video_stream.get("pix_fmt"),
                }

            audio_stream = next(
                (
                    s
                    for s in probe_data.get("streams", [])
                    if s.get("codec_type") == "audio"
                ),
                None,
            )
            if audio_stream:
                metadata["audio_stream"] = {
                    "codec": audio_stream.get("codec_name"),
                    "sample_rate": audio_stream.get("sample_rate"),
                    "channels": audio_stream.get("channels"),
                }

        except Exception as e:
            metadata["video_metadata_error"] = str(e)

        return metadata

    @staticmethod
    async def _extract_pdf_metadata(file_path: str) -> dict:
        """Extract PDF metadata using PyPDF2."""
        metadata = {}

        try:
            import PyPDF2

            with open(file_path, "rb") as file:
                reader = PyPDF2.PdfReader(file)

                metadata.update(
                    {
                        "page_count": len(reader.pages),
                        "is_encrypted": reader.is_encrypted,
                    }
                )

                # Extract document info if available
                if reader.metadata:
                    doc_info = {}
                    for key, value in reader.metadata.items():
                        # Clean up keys (remove leading '/')
                        clean_key = key.lstrip("/")
                        # Handle different value types
                        if hasattr(value, "decode"):
                            try:
                                doc_info[clean_key] = value.decode(
                                    "utf-8", errors="ignore"
                                )
                            except:
                                doc_info[clean_key] = str(value)
                        else:
                            doc_info[clean_key] = str(value) if value else ""

                    if doc_info:
                        metadata["document_info"] = doc_info

        except Exception as e:
            # Provide a more specific error message
            error_msg = str(e)
            if "EOF marker not found" in error_msg:
                error_msg = "PDF appears to be truncated or corrupted"
            elif "invalid literal for int()" in error_msg:
                error_msg = "PDF structure appears to be invalid"

            metadata["pdf_metadata_error"] = error_msg

        return metadata

    @staticmethod
    async def _verify_magic_number(file_path: str, content_type: str) -> bool:
        """Verify file signature matches claimed content type."""
        magic_numbers = {
            "image/jpeg": [b"\xff\xd8\xff"],
            "image/png": [b"\x89PNG\r\n\x1a\n"],
            "image/gif": [b"GIF87a", b"GIF89a"],
            "image/webp": [b"RIFF", b"WEBP"],  # WebP starts with RIFF and contains WEBP
            "application/pdf": [b"%PDF-"],
            "video/mp4": [b"ftyp"],
            "video/avi": [b"RIFF"],
            "video/mov": [b"ftyp", b"moov"],
            "video/webm": [b"\x1a\x45\xdf\xa3"],  # WebM/Matroska
        }

        try:
            with open(file_path, "rb") as f:
                header = f.read(20)  # Read first 20 bytes

            expected_signatures = magic_numbers.get(content_type, [])

            # Special handling for WebP which has WEBP at position 8-12
            if content_type == "image/webp" and header.startswith(b"RIFF"):
                return header[8:12] == b"WEBP"

            return any(header.startswith(sig) for sig in expected_signatures)

        except Exception:
            return False

    # endregion

    async def _process_extract_metadata_worker(
        self, state: WorkflowGraphState
    ) -> WorkflowGraphState:
        """
        Extracting metadata from file.
        Updates the job state with the results of the extracting metadata.
        Args:
            state (WorkflowGraphState): The job state dictionary containing file metadata and path.
        Returns:
            WorkflowGraphState: Updated job state after extracting metadata.
        """
        print(
            f"[Worker:extract_metadata_from_file] Job {state['job_id']} extracting metadata..."
        )
        await asyncio.sleep(0.5)
        errors = []

        # -------------------------------------------------------------------------------
        # The real metadata extraction!
        # -------------------------------------------------------------------------------
        # Initialize metadata if not present
        if "metadata" not in state or state["metadata"] is None:
            state["metadata"] = {}

        content_type = state["content_type"]
        file_path = state["file_path"]

        # 1. Extract universal metadata (applies to all file types)
        universal_metadata = await self._extract_universal_metadata(state)
        if "universal_metadata_error" in universal_metadata:
            errors.append(
                f"Universal metadata extraction failed: {universal_metadata['universal_metadata_error']}"
            )
        else:
            state["metadata"].update(universal_metadata)

        # 2. Extract type-specific metadata
        try:
            # Download from S3 if needed for content-specific metadata extraction
            local_path = await self.cloud_manager.download_from_s3_if_needed(USE_AWS, file_path)

            try:
                if content_type.startswith("image/"):
                    image_metadata = await self._extract_image_metadata(local_path)
                    if "image_metadata_error" in image_metadata:
                        errors.append(
                            f"Image metadata extraction failed: {image_metadata['image_metadata_error']}"
                        )
                    else:
                        state["metadata"].update(image_metadata)

                elif content_type.startswith("video/"):
                    video_metadata = await self._extract_video_metadata(local_path)
                    if "video_metadata_error" in video_metadata:
                        errors.append(
                            f"Video metadata extraction failed: {video_metadata['video_metadata_error']}"
                        )
                    else:
                        state["metadata"].update(video_metadata)

                elif content_type == "application/pdf":
                    pdf_metadata = await self._extract_pdf_metadata(local_path)
                    if "pdf_metadata_error" in pdf_metadata:
                        errors.append(
                            f"PDF metadata extraction failed: {pdf_metadata['pdf_metadata_error']}"
                        )
                    else:
                        state["metadata"].update(pdf_metadata)

            finally:
                # Clean up temp file if it was downloaded from S3
                if local_path != file_path and os.path.exists(local_path):
                    os.remove(local_path)

        except Exception as e:
            errors.append(f"Type-specific metadata extraction failed: {str(e)}")

        # -------------------------------------------------------------------------------
        if errors:
            state["status"] = "failed"
            state["step"] = "extract_metadata_from_file_failed"

            # state["metadata"] = {"errors": errors}
            state["metadata"]["errors"] = errors  # Keep existing metadata but add errors

        else:
            state["status"] = "success"
            state["step"] = "extract_metadata_from_file_done"

            # state["metadata"] = {"extracting_metadata": "passed"}
            state["metadata"][
                "extracting_metadata"
            ] = "passed"  # Just add the success flag

        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        print(
            f"[Worker:extract_metadata_from_file] Job {state['job_id']} extracting metadata done. State: {state}"
        )

        return state

    @staticmethod
    def _current_timestamp():
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "extracting_metadata"}


# ----------------------------------------------------------------------------------------------
# Redis listener to subscribe to validation tasks
# ----------------------------------------------------------------------------------------------
async def redis_listener(extract_metadata_service: ExtractMetadataService):
    """Redis listener using shared RedisManager."""
    redis_client = await extract_metadata_service.redis_manager.get_redis_client()
    pubsub = redis_client.pubsub()

    try:
        await pubsub.subscribe(EXTRACT_METADATA_QUEUE)
        print(f"[ExtractMetadataService] Listening on '{EXTRACT_METADATA_QUEUE}'...")

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    task = json.loads(message["data"])
                    job_id = task.get("job_id", "unknown")
                    print(f"[ExtractMetadataService] Processing job: {job_id}")

                    result = (
                        await extract_metadata_service.process_extract_metadata_task(
                            task
                        )
                    )

                    # Use shared Redis connection to publish result
                    await redis_client.publish(
                        EXTRACT_METADATA_CALLBACK_QUEUE,
                        json.dumps({"job_id": job_id, "result": result}),
                    )
                    print(f"[ExtractMetadataService] Published result for: {job_id}")

                except Exception as e:
                    print(f"[ExtractMetadataService] Error: {e}")

    except asyncio.CancelledError:
        print("[ExtractMetadataService] Listener cancelled")
    finally:
        await pubsub.unsubscribe(EXTRACT_METADATA_QUEUE)
        await pubsub.close()

