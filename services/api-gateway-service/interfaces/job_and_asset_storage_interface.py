"""
Abstraction layer for job/asset metadata management.

This module provides an interface for:
- JobAndAssetStorage: Abstracts job and asset metadata storage (in-memory or persistent).

Usage:
- Use InMemoryJobAssetStore for local development (stores metadata in memory).
- For AWS migration, implement FileStorage and JobAssetStore for S3 and DynamoDB.

Classes:
- JobAssetStore (ABC): Interface for job/asset metadata operations.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class JobAndAssetStorage(ABC):
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
