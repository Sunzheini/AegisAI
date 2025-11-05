"""
Abstraction layer for file storage.

This module provides a interface for:
- FileStorage: Abstracts file saving, retrieval, and copying (local or cloud).

Usage:
- Use LocalFileStorage for local development (stores files on disk).
- For AWS migration, implement FileStorage for S3 and DynamoDB.

Classes:
- FileStorage (ABC): Interface for file operations.
"""
from abc import ABC, abstractmethod


class FileStorage(ABC):
    """
    Abstract base class for file storage operations.
    Implementations can provide local or cloud storage (e.g., filesystem, S3).
    """

    async def save_file(self, file_obj, filename: str) -> str:
        """
        Save a file object to storage under the given filename.
        Returns the path or identifier of the saved file.
        """

    @abstractmethod
    def get_file_path(self, filename: str) -> str:
        """
        Get the full path or identifier for a stored file by filename.
        """

    @abstractmethod
    async def copy_file(self, src: str, dst: str) -> None:
        """
        Copy a file from src to dst within the storage backend.
        """
