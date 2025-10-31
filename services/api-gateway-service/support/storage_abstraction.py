"""
Abstraction layer for file storage and job/asset metadata management.

This module provides interfaces and local implementations for:
- FileStorage: Abstracts file saving, retrieval, and copying (local or cloud).
- JobAssetStore: Abstracts job and asset metadata storage (in-memory or persistent).

Usage:
- Use LocalFileStorage for local development (stores files on disk).
- Use InMemoryJobAssetStore for local development (stores metadata in memory).
- For AWS migration, implement FileStorage and JobAssetStore for S3 and DynamoDB.

Classes:
- FileStorage (ABC): Interface for file operations.
- LocalFileStorage: Local disk implementation of FileStorage.
- JobAssetStore (ABC): Interface for job/asset metadata operations.
- InMemoryJobAssetStore: In-memory implementation of JobAssetStore.

Example:
    # Local usage
    file_storage = LocalFileStorage("./storage/raw")
    job_store = InMemoryJobAssetStore()

    # Save a file
    await file_storage.save_file(upload_file, "filename.png")

    # Create a job
    job_store.create_job({"job_id": "123", ...})

    # Get job
    job = job_store.get_job("123")

    # For AWS, implement S3FileStorage and DynamoDBJobAssetStore
"""
import os
import shutil
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


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


class LocalFileStorage(FileStorage):
    """
    Local disk implementation of FileStorage.
    Stores files in a specified root directory on the local filesystem.
    """

    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        os.makedirs(self.root_dir, exist_ok=True)

    async def save_file(self, file_obj, filename: str) -> str:
        """
        Save a file object to the local disk under the given filename.
        Returns the full path to the saved file.
        """
        dst_path = os.path.join(self.root_dir, filename)

        async def write_file_sync():
            with open(dst_path, "wb") as out:
                while True:
                    chunk = await file_obj.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
            await file_obj.close()

        await asyncio.to_thread(write_file_sync)

        return dst_path

    def get_file_path(self, filename: str) -> str:
        """
        Get the full path for a file stored in the local directory.
        """
        return os.path.join(self.root_dir, filename)

    async def copy_file(self, src: str, dst: str) -> None:
        """
        Copy a file from src to dst on the local filesystem asynchronously.
        """
        await asyncio.to_thread(shutil.copy2, src, dst)


class JobAssetStore(ABC):
    """
    Abstract base class for job and asset metadata storage.
    Implementations can provide in-memory or persistent storage (e.g., DynamoDB).
    """

    @abstractmethod
    def create_job(self, job_data: Dict[str, Any]) -> None:
        """
        Store a new job record.
        """

    @abstractmethod
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a job record by job_id.
        """

    @abstractmethod
    def update_job(self, job_id: str, updates: Dict[str, Any]) -> None:
        """
        Update fields of an existing job record.
        """

    @abstractmethod
    def create_asset(self, asset_data: Dict[str, Any]) -> None:
        """
        Store a new asset record.
        """

    @abstractmethod
    def get_asset(self, asset_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve an asset record by asset_id.
        """


class InMemoryJobAssetStore(JobAssetStore):
    """
    In-memory implementation of JobAssetStore for local development and testing.
    Stores job and asset metadata in Python dictionaries.
    """

    def __init__(self):
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.assets: Dict[str, Dict[str, Any]] = {}

    def create_job(self, job_data: Dict[str, Any]) -> None:
        """
        Store a new job record in memory.
        """
        self.jobs[job_data["job_id"]] = job_data

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a job record from memory by job_id.
        """
        return self.jobs.get(job_id)

    def update_job(self, job_id: str, updates: Dict[str, Any]) -> None:
        """
        Update fields of an existing job record in memory.
        """
        if job_id in self.jobs:
            self.jobs[job_id].update(updates)

    def create_asset(self, asset_data: Dict[str, Any]) -> None:
        """
        Store a new asset record in memory.
        """
        self.assets[asset_data["asset_id"]] = asset_data

    def get_asset(self, asset_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve an asset record from memory by asset_id.
        """
        return self.assets.get(asset_id)
