"""
Contains the CloudManager class responsible for managing interactions with AWS, GCP, etc.
"""
import os
import tempfile

import boto3
from botocore.exceptions import ClientError


class CloudManager:
    """Manages Cloud interactions and provides cloud related helper methods."""

    def __init__(self):
        self._s3_client = None

    @property
    def s3_client(self):
        return self._s3_client

    def create_s3_client(self, access_key_id, secret_access_key, region) -> None:
        """Create an S3 client using Boto3."""
        self._s3_client = boto3.client(
        's3',
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name=region,
    )

    @staticmethod
    def parse_s3_path(file_path: str) -> tuple:
        """Parse S3 URI into bucket and key."""
        bucket_key = file_path[5:]  # Remove 's3://'
        bucket_name, key = bucket_key.split('/', 1)
        return bucket_name, key

    async def download_from_s3_if_needed(self, use_aws: bool, file_path: str) -> str:
        """Download file from S3 if path is an S3 URI, return local temp path."""
        if not use_aws or not file_path.startswith('s3://'):
            return file_path

        bucket_name, key = self.parse_s3_path(file_path)
        temp_dir = tempfile.gettempdir()
        local_path = os.path.join(temp_dir, os.path.basename(key))

        try:
            self._s3_client.download_file(bucket_name, key, local_path)
            return local_path
        except ClientError as e:
            raise Exception(f"S3 download failed: {e}")
