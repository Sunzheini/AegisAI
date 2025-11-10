"""
This module provides a local implementations for:
- FileStorage: Abstracts file saving, retrieval, and copying (local or cloud).

Usage:
- Use LocalFileStorage for local development (stores files on disk).

Classes:
- LocalFileStorage: Local disk implementation of FileStorage.

Example:
    # Local usage
    file_storage = LocalFileStorage("./storage/raw")
    job_store = InMemoryJobAssetStore()

    # Save a file
    await file_storage.save_file(upload_file, "filename.png")
"""
import os
import shutil
import asyncio

from shared_lib.interfaces.file_storage_interface import FileStorage


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
