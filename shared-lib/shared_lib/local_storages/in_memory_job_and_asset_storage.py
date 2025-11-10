"""
This module provides an implementation for:
- JobAndAssetStorage: Abstracts job and asset metadata storage (in-memory or persistent).

Usage:
- Use InMemoryJobAndAssetStorage for local development (stores metadata in memory).
- For AWS migration, implement FileStorage and JobAssetStore for S3 and DynamoDB.

Classes:
- InMemoryJobAssetStore: In-memory implementation of JobAssetStore.

Example:
    # Create a job
    job_store.create_job({"job_id": "123", ...})

    # Get job
    job = job_store.get_job("123")
"""
from typing import Dict, Any, Optional

from shared_lib.interfaces.job_and_asset_storage_interface import JobAndAssetStorage


class InMemoryJobAndAssetStorage(JobAndAssetStorage):
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
