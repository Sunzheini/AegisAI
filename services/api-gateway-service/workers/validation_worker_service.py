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
from pathlib import Path

from botocore.exceptions import ClientError
from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

# Conditional import for shared library usage ----------------------------------------------
USE_SHARED_LIB = os.getenv("USE_SHARED_LIB", False)
if USE_SHARED_LIB:
    from shared_lib.contracts.job_schemas import WorkflowGraphState
    from shared_lib.needs.INeedCloudManager import INeedCloudManagerInterface
    from shared_lib.needs.INeedRedisManager import INeedRedisManagerInterface
    from shared_lib.needs.ResolveNeedsManager import ResolveNeedsManager
    from shared_lib.redis_management.redis_manager import RedisManager
    from shared_lib.custom_middleware.error_middleware import ErrorMiddleware
    from shared_lib.custom_middleware.logging_middleware import EnhancedLoggingMiddleware
    from shared_lib.logging_management.logging_manager import LoggingManager
else:
    from contracts.job_schemas import WorkflowGraphState
    from needs.INeedCloudManager import INeedCloudManagerInterface
    from needs.INeedRedisManager import INeedRedisManagerInterface
    from needs.ResolveNeedsManager import ResolveNeedsManager
    from redis_management.redis_manager import RedisManager
    from custom_middleware.error_middleware import ErrorMiddleware
    from custom_middleware.logging_middleware import EnhancedLoggingMiddleware
    from logging_management.logging_manager import LoggingManager
# ------------------------------------------------------------------------------------------


# Configuration
VALIDATION_QUEUE = os.getenv("VALIDATION_QUEUE", "validation_queue")
VALIDATION_CALLBACK_QUEUE = os.getenv(
    "VALIDATION_CALLBACK_QUEUE", "validation_callback_queue"
)

USE_AWS = os.getenv("USE_AWS", "false").lower() == "true"
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION = os.getenv("AWS_REGION_NAME", "")

if not USE_AWS:
    UPLOAD_DIR = Path(os.getenv("RAW_DIR", "storage/raw")).resolve()
else:
    UPLOAD_DIR = os.getenv("RAW_DIR_AWS", "aegisai-raw-danielzorov")

# Validation constraints
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 100 * 1024 * 1024))  # 100MB default
MAX_IMAGE_DIMENSION = int(os.getenv("MAX_IMAGE_DIMENSION", 10000))  # 10k pixels
MAX_VIDEO_DURATION = int(os.getenv("MAX_VIDEO_DURATION", 3600))  # 1 hour in seconds
ALLOWED_EXTENSIONS = {
    "application/pdf": [".pdf"],
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
    "image/gif": [".gif"],
    "image/webp": [".webp"],
    "video/mp4": [".mp4"],
    "video/avi": [".avi"],
    "video/mov": [".mov"],
    "video/webm": [".webm"],
}

logger = LoggingManager.setup_logging(
    service_name="validation-service",
    log_file_path="logs/validation_service.log",
    log_level=logging.INFO,
)


@asynccontextmanager
async def lifespan(app):
    """Lifespan context manager to start/stop Redis listener."""
    logger.info("Starting Validation Service...")

    # Create RedisManager
    redis_manager = RedisManager()

    # Create validation service and inject needs
    validation_service = ValidationService()
    ResolveNeedsManager.resolve_needs(validation_service)

    # Initialize the cloud client after injection
    validation_service.cloud_manager.create_s3_client(
        access_key_id=os.getenv("AWS_ACCESS_KEY_ID", ""),
        secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", ""),
        region=os.getenv("AWS_REGION_NAME", "us-east-1"),
    )

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


class ValidationService(INeedRedisManagerInterface, INeedCloudManagerInterface):
    """Handles file validation tasks using shared RedisManager."""

    def __init__(self):
        self.logger = logging.getLogger("validation-service")

        # Instance-level configuration
        self.MAX_FILE_SIZE = MAX_FILE_SIZE
        self.MAX_IMAGE_DIMENSION = MAX_IMAGE_DIMENSION
        self.MAX_VIDEO_DURATION = MAX_VIDEO_DURATION
        self.ALLOWED_EXTENSIONS = ALLOWED_EXTENSIONS

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
                "updated_at": self._current_timestamp(),
            }

    # region Validation Methods
    async def _validate_file_access(self, state: WorkflowGraphState) -> list:
        """Validate that file exists and is accessible."""
        errors = []
        file_path = state["file_path"]

        try:
            # Todo: changed
            if not USE_AWS:
                path = Path(file_path)

                # Check if file exists
                if not path.exists():
                    errors.append(f"File does not exist: {file_path}")
                    return errors

                # Check if it's actually a file
                if not path.is_file():
                    errors.append(f"Path is not a file: {file_path}")

                # Check read permissions
                if not os.access(file_path, os.R_OK):
                    errors.append(f"No read permission for file: {file_path}")

            else:
                bucket_name, key = self.cloud_manager.parse_s3_path(file_path)
                try:
                    self.cloud_manager.s3_client.head_object(Bucket=bucket_name, Key=key)
                except ClientError as e:
                    errors.append(f"S3 file does not exist or inaccessible: {file_path} - {e}")

        except Exception as e:
            errors.append(f"File access validation failed: {str(e)}")

        return errors

    async def _validate_basic_metadata(self, state: WorkflowGraphState) -> list:
        """Validate basic metadata like content type and checksum."""
        errors = []

        allowed_types = list(self.ALLOWED_EXTENSIONS.keys())
        if state["content_type"] not in allowed_types:
            errors.append(
                f"Unsupported file type: {state['content_type']}. Allowed types: {', '.join(allowed_types)}"
            )

        # Checksum validation
        checksum = state.get("checksum_sha256", "")
        if not checksum:
            errors.append("Missing checksum")
        elif len(checksum) != 64:  # SHA256 should be 64 characters
            errors.append("Invalid checksum format: must be 64 characters for SHA256")
        elif checksum.endswith("0"):  # Your existing rule
            errors.append("Checksum validation failed: checksum ends with 0")

        return errors

    async def _validate_file_size(self, state: WorkflowGraphState) -> list:
        """Validate file size constraints."""
        errors = []
        file_path = state["file_path"]

        try:
            # Todo: changed
            if not USE_AWS:
                file_size = os.path.getsize(file_path)
            else:
                bucket_name, key = self.cloud_manager.parse_s3_path(file_path)
                response = self.cloud_manager.s3_client.head_object(Bucket=bucket_name, Key=key)
                file_size = response['ContentLength']

            if file_size > self.MAX_FILE_SIZE:
                errors.append(
                    f"File size {file_size} exceeds maximum allowed size {self.MAX_FILE_SIZE}"
                )

            # Check minimum file size (avoid empty files)
            if file_size == 0:
                errors.append("File is empty")

            # Add file size to metadata for downstream processing
            # Ensure metadata exists and is a dictionary
            if "metadata" not in state or state["metadata"] is None:
                state["metadata"] = {}
            state["metadata"]["file_size"] = file_size

        except Exception as e:
            errors.append(f"File size validation failed: {str(e)}")

        return errors

    async def _validate_file_extension(self, state: WorkflowGraphState) -> list:
        """Validate that file extension matches content type."""
        errors = []
        file_path = state["file_path"]
        content_type = state["content_type"]

        try:
            path = Path(file_path)
            file_extension = path.suffix.lower()

            allowed_extensions = self.ALLOWED_EXTENSIONS.get(content_type, [])
            if allowed_extensions and file_extension not in allowed_extensions:
                errors.append(
                    f"File extension {file_extension} does not match content type {content_type}. "
                    f"Allowed extensions: {', '.join(allowed_extensions)}"
                )

        except Exception as e:
            errors.append(f"File extension validation failed: {str(e)}")

        return errors

    async def _validate_content_specific_rules(self, state: WorkflowGraphState) -> list:
        """Apply content-type specific validation rules."""
        content_type = state["content_type"]
        file_path = state["file_path"]
        errors = []

        try:
            # ToDo: changed
            # Download from S3 if needed for content validation
            local_path = await self.cloud_manager.download_from_s3_if_needed(USE_AWS, file_path)

            try:
                if content_type.startswith("image/"):
                    errors.extend(await self._validate_image_file(local_path))
                elif content_type.startswith("video/"):
                    errors.extend(await self._validate_video_file(local_path))
                elif content_type == "application/pdf":
                    errors.extend(await self._validate_pdf_file(local_path))

            # ToDo: changed
            finally:
                # Clean up temp file if it was downloaded from S3
                if local_path != file_path and os.path.exists(local_path):
                    os.remove(local_path)

        except Exception as e:
            errors.append(f"Content-specific validation failed: {str(e)}")

        return errors

    async def _validate_image_file(self, file_path: str) -> list:
        """Validate image-specific constraints."""
        errors = []

        try:
            file_size = os.path.getsize(file_path)

            # Check if file has basic image structure
            with open(file_path, "rb") as f:
                header = f.read(100)

            # Basic magic number checks
            if header.startswith(b"\xff\xd8\xff"):
                # JPEG - check minimum size for valid JPEG
                if file_size < 100:  # Minimal valid JPEG is around 100 bytes
                    errors.append("JPEG file appears to be too small or corrupted")
            elif header.startswith(b"\x89PNG\r\n\x1a\n"):
                # PNG - check minimum size
                if file_size < 67:  # Minimal valid PNG is around 67 bytes
                    errors.append("PNG file appears to be too small or corrupted")
            elif header.startswith(b"GIF8"):
                # GIF - check minimum size
                if file_size < 35:  # Minimal valid GIF is around 35 bytes
                    errors.append("GIF file appears to be too small or corrupted")
            elif header.startswith(b"RIFF") and header[8:12] == b"WEBP":
                # WebP
                if file_size < 45:  # Minimal valid WebP
                    errors.append("WebP file appears to be too small or corrupted")
            else:
                errors.append("File does not appear to be a valid image format")

            # Check if image dimensions are reasonable
            if (
                    file_size > self.MAX_IMAGE_DIMENSION * self.MAX_IMAGE_DIMENSION * 4
            ):  # Rough estimate: width * height * 4 bytes
                errors.append(
                    f"Image file size suggests dimensions may exceed maximum allowed {self.MAX_IMAGE_DIMENSION}x{self.MAX_IMAGE_DIMENSION}"
                )

        except Exception as e:
            errors.append(f"Image validation failed: {str(e)}")

        return errors

    async def _validate_video_file(self, file_path: str) -> list:
        """Validate video-specific constraints."""
        errors = []

        try:
            file_size = os.path.getsize(file_path)

            # Check minimum video file size
            if file_size < 1024:  # 1KB minimum for video files
                errors.append("Video file appears to be too small or corrupted")

            # Basic video file check
            with open(file_path, "rb") as f:
                header = f.read(100)

            # Check for common video file signatures
            video_signatures = [
                b"ftyp",  # MP4
                b"RIFF",  # AVI, WAV
                b"\x00\x00\x00 ftyp",  # Another MP4 variant
                b"\x1a\x45\xdf\xa3",  # WebM/Matroska
                b"\x00\x00\x01\xba",  # MPEG
            ]

            if not any(sig in header for sig in video_signatures):
                errors.append("File does not appear to be a valid video format")

            # Estimate video duration from file size (very rough estimate)
            # Assuming average bitrate of 1-2 Mbps for compressed video
            estimated_duration = file_size * 8 / (1.5 * 1024 * 1024)  # seconds
            if estimated_duration > self.MAX_VIDEO_DURATION:
                errors.append(
                    f"Estimated video duration ({estimated_duration:.1f}s) may exceed maximum allowed {self.MAX_VIDEO_DURATION}s"
                )

        except Exception as e:
            errors.append(f"Video validation failed: {str(e)}")

        return errors

    @staticmethod
    async def _validate_pdf_file(file_path: str) -> list:
        """Validate PDF-specific constraints."""
        errors = []

        try:
            with open(file_path, "rb") as f:
                header = f.read(10)
                footer = f.seek(-10, 2)  # Seek to last 10 bytes
                footer = f.read(10)

            # Check PDF header and footer
            if not header.startswith(b"%PDF-"):
                errors.append("Invalid PDF file: missing PDF header")

            if b"%%EOF" not in footer:
                errors.append("Invalid PDF file: missing EOF marker")

        except Exception as e:
            errors.append(f"PDF validation failed: {str(e)}")

        return errors

    @staticmethod
    async def _validate_security_aspects(state: WorkflowGraphState) -> list:
        """Perform security-related validations."""
        errors = []
        file_path = state["file_path"]

        try:
            # Check for suspicious characters in the file path regardless of file existence
            if any(char in file_path for char in [";", "|", "&", "$", "`"]):
                errors.append("File path contains potentially dangerous characters")

            # Check for path traversal attempts
            if ".." in file_path:
                errors.append("Invalid file path: potential path traversal attack")

            # Check for double extensions in the filename
            path = Path(file_path)
            filename = path.name
            if len(filename.split(".")) > 2:
                # This might be legitimate, but worth logging
                print(f"Warning: File {filename} has multiple extensions")

        except Exception as e:
            errors.append(f"Security validation failed: {str(e)}")

        return errors

    # endregion

    async def _validate_file_worker(
            self, state: WorkflowGraphState
    ) -> WorkflowGraphState:
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

        # -------------------------------------------------------------------------------
        # The real validation!
        # -------------------------------------------------------------------------------
        # Basic validations
        errors.extend(await self._validate_basic_metadata(state))

        # File existence and accessibility
        errors.extend(await self._validate_file_access(state))

        # File size validation
        errors.extend(await self._validate_file_size(state))

        # File extension consistency
        errors.extend(await self._validate_file_extension(state))

        # Content-type specific validations
        errors.extend(await self._validate_content_specific_rules(state))

        # Security checks
        errors.extend(await self._validate_security_aspects(state))

        # -------------------------------------------------------------------------------
        if errors:
            state["status"] = "failed"
            state["step"] = "validate_file_failed"
            state["metadata"] = {"errors": errors}

        else:
            state["status"] = "success"
            state["step"] = "validate_file_done"
            state["metadata"] = {"validation": "passed"}

        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        print(
            f"[Worker:validate_file] Job {state['job_id']} validation done. State: {state}"
        )
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
                        json.dumps({"job_id": job_id, "result": result}),
                    )
                    print(f"[ValidationService] Published result for: {job_id}")

                except Exception as e:
                    print(f"[ValidationService] Error: {e}")

    except asyncio.CancelledError:
        print("[ValidationService] Listener cancelled")
    finally:
        await pubsub.unsubscribe(VALIDATION_QUEUE)
        await pubsub.close()
