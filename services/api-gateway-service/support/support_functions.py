"""
Support functions for the API Gateway Service.
"""

import os
from pathlib import Path


def sanitize_filename(name: str) -> str:
    """Sanitize file name to be filesystem-safe."""
    keep = [c if c.isalnum() or c in (".", "-", "_") else "_" for c in name]
    return "".join(keep) or "file"


async def resolve_file_path(file_path: str, job_id: str) -> str:
    """Resolve file path to actual location with job_id prefix."""
    path = Path(file_path)

    # Use the same storage paths as the services
    storage_root = Path(os.getenv("STORAGE_ROOT", "storage"))
    upload_dir = Path(os.getenv("RAW_DIR", storage_root / "raw"))

    # If path is already absolute and exists, use it
    if path.is_absolute() and path.exists():
        return str(path)

    # Try job-prefixed filename
    prefixed = upload_dir / f"{job_id}_{path.name}"
    if prefixed.exists():
        return str(prefixed)

    # Fallback to original path (will fail validation with clear error)
    return str(upload_dir / path.name)
