"""
Support functions for the API Gateway Service.
"""


def sanitize_filename(name: str) -> str:
    """Sanitize file name to be filesystem-safe."""
    keep = [c if c.isalnum() or c in (".", "-", "_") else "_" for c in name]
    return "".join(keep) or "file"
