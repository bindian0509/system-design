"""
Result storage abstraction - supports local, S3, and GCS storage.
"""
import os
import json
import logging
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)


class ResultStorage(ABC):
    """Abstract base class for result storage backends."""

    @abstractmethod
    def upload(self, job_id: str, content: bytes, filename: str = "result.json") -> str:
        """
        Upload result to storage.

        Args:
            job_id: Job ID
            content: Result content (bytes)
            filename: Filename to store as

        Returns:
            Storage URL/path
        """
        pass

    @abstractmethod
    def download(self, storage_url: str) -> bytes:
        """
        Download result from storage.

        Args:
            storage_url: Storage URL/path

        Returns:
            Result content (bytes)
        """
        pass

    @abstractmethod
    def delete(self, storage_url: str) -> None:
        """Delete result from storage."""
        pass


class LocalStorage(ResultStorage):
    """Local filesystem storage."""

    def __init__(self, base_path: str = "/tmp/job_results"):
        """Initialize local storage."""
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized local storage at {self.base_path}")

    def upload(self, job_id: str, content: bytes, filename: str = "result.json") -> str:
        """Upload result to local filesystem."""
        job_dir = self.base_path / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        file_path = job_dir / filename
        file_path.write_bytes(content)

        storage_url = f"local://{job_dir}/{filename}"
        logger.debug(f"Uploaded result for job {job_id} to {storage_url}")
        return storage_url

    def download(self, storage_url: str) -> bytes:
        """Download result from local filesystem."""
        # Parse URL: local:///tmp/job_results/job-id/result.json
        path = storage_url.replace("local://", "")
        return Path(path).read_bytes()

    def delete(self, storage_url: str) -> None:
        """Delete result from local filesystem."""
        path = storage_url.replace("local://", "")
        Path(path).unlink(missing_ok=True)


class S3Storage(ResultStorage):
    """Amazon S3 storage backend."""

    def __init__(self, bucket: str, region: str = "us-east-1"):
        """Initialize S3 storage."""
        try:
            import boto3
            self.s3_client = boto3.client('s3', region_name=region)
            self.bucket = bucket
            logger.info(f"Initialized S3 storage (bucket: {bucket}, region: {region})")
        except ImportError:
            raise ImportError("boto3 required for S3 storage. Install with: pip install boto3")

    def upload(self, job_id: str, content: bytes, filename: str = "result.json") -> str:
        """Upload result to S3."""
        key = f"results/{job_id}/{filename}"
        try:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
                ContentType="application/json",
                Metadata={"job-id": job_id},
            )
            storage_url = f"s3://{self.bucket}/{key}"
            logger.debug(f"Uploaded result for job {job_id} to {storage_url}")
            return storage_url
        except Exception as e:
            logger.error(f"Error uploading to S3: {e}")
            raise

    def download(self, storage_url: str) -> bytes:
        """Download result from S3."""
        # Parse URL: s3://bucket/results/job-id/result.json
        parts = storage_url.replace("s3://", "").split("/", 1)
        bucket, key = parts[0], parts[1]

        try:
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            return response['Body'].read()
        except Exception as e:
            logger.error(f"Error downloading from S3: {e}")
            raise

    def delete(self, storage_url: str) -> None:
        """Delete result from S3."""
        parts = storage_url.replace("s3://", "").split("/", 1)
        bucket, key = parts[0], parts[1]

        try:
            self.s3_client.delete_object(Bucket=bucket, Key=key)
        except Exception as e:
            logger.error(f"Error deleting from S3: {e}")


class GCSStorage(ResultStorage):
    """Google Cloud Storage backend."""

    def __init__(self, bucket: str, project: Optional[str] = None):
        """Initialize GCS storage."""
        try:
            from google.cloud import storage
            self.client = storage.Client(project=project)
            self.bucket = self.client.bucket(bucket)
            logger.info(f"Initialized GCS storage (bucket: {bucket})")
        except ImportError:
            raise ImportError("google-cloud-storage required for GCS. Install with: pip install google-cloud-storage")

    def upload(self, job_id: str, content: bytes, filename: str = "result.json") -> str:
        """Upload result to GCS."""
        blob_name = f"results/{job_id}/{filename}"
        try:
            blob = self.bucket.blob(blob_name)
            blob.upload_from_string(
                content,
                content_type="application/json",
                metadata={"job-id": job_id},
            )
            storage_url = f"gs://{self.bucket.name}/{blob_name}"
            logger.debug(f"Uploaded result for job {job_id} to {storage_url}")
            return storage_url
        except Exception as e:
            logger.error(f"Error uploading to GCS: {e}")
            raise

    def download(self, storage_url: str) -> bytes:
        """Download result from GCS."""
        # Parse URL: gs://bucket/results/job-id/result.json
        parts = storage_url.replace("gs://", "").split("/", 1)
        bucket_name, blob_name = parts[0], parts[1]

        try:
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            return blob.download_as_bytes()
        except Exception as e:
            logger.error(f"Error downloading from GCS: {e}")
            raise

    def delete(self, storage_url: str) -> None:
        """Delete result from GCS."""
        parts = storage_url.replace("gs://", "").split("/", 1)
        bucket_name, blob_name = parts[0], parts[1]

        try:
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            blob.delete()
        except Exception as e:
            logger.error(f"Error deleting from GCS: {e}")


def get_storage() -> ResultStorage:
    """
    Get configured storage backend.

    Returns:
        Storage instance based on RESULT_STORAGE_TYPE env var
    """
    from common.config import settings

    storage_type = settings.result_storage_type.lower()

    if storage_type == "s3":
        return S3Storage(bucket=settings.result_storage_bucket)
    elif storage_type == "gcs":
        return GCSStorage(bucket=settings.result_storage_bucket)
    else:
        # Default to local storage
        return LocalStorage(base_path=settings.result_storage_bucket)
