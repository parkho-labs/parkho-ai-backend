from datetime import timedelta
import datetime
from typing import Optional
from google.cloud import storage
from google.oauth2 import service_account
import structlog
import os

from src.config import Settings

logger = structlog.get_logger(__name__)


class GCPService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.bucket_name = settings.storage_bucket
        self.project_id = settings.gcp_project_id
        
        # Try to load from service account file first (Production/Configured), fallback to ADC (Local/Dev)
        try:
            if settings.firebase_service_account_path and os.path.exists(settings.firebase_service_account_path):
                 try:
                     logger.info("Loading GCP credentials from service account file", path=settings.firebase_service_account_path)
                     self.credentials = service_account.Credentials.from_service_account_file(
                         settings.firebase_service_account_path
                     )
                     self.client = storage.Client(credentials=self.credentials, project=self.project_id)
                 except Exception as e:
                     logger.warning("Failed to load service account file, falling back to ADC", error=str(e))
                     logger.info("Initializing GCP Storage Client using ADC")
                     self.client = storage.Client(project=self.project_id)
            else:
                logger.info("No service account file found or configured, using ADC")
                self.client = storage.Client(project=self.project_id)
        except Exception as e:
            logger.error("Failed to initialize GCP Storage Client", error=str(e))
            self.client = None

    def generate_upload_signed_url(
        self, 
        blob_name: str, 
        content_type: str, 
        expiration_minutes: int = 15
    ) -> Optional[str]:
        if not self.client:
            logger.error("GCP Client not initialized")
            return None

        try:
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(blob_name)

            return blob.generate_signed_url(
                version="v4",
                expiration=datetime.timedelta(minutes=expiration_minutes),
                method="PUT",
                content_type=content_type,
            )
        except Exception as e:
            logger.error("Failed to generate signed URL", error=str(e))
            return None

    def check_file_exists(self, blob_name: str) -> bool:
        if not self.client:
            return False
            
        try:
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(blob_name)
            return blob.exists()
        except Exception as e:
            logger.error("Failed to check file existence", error=str(e))
            return False
    
    def get_public_url(self, blob_name: str) -> str:
         return f"https://storage.googleapis.com/{self.bucket_name}/{blob_name}"

    def get_gcs_uri(self, blob_name: str) -> str:
         """Returns the gs://bucket/blob URI used by RAG engine."""
         return f"gs://{self.bucket_name}/{blob_name}"

    def generate_download_signed_url(self, blob_name: str, expiration_minutes: int = 60) -> Optional[str]:
        if not self.client:
            return None
        try:
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(blob_name)
            return blob.generate_signed_url(
                version="v4",
                expiration=datetime.timedelta(minutes=expiration_minutes),
                method="GET",
            )
        except Exception as e:
            logger.error("Failed to generate download signed URL", error=str(e))
            return None

    def open_file_stream(self, blob_name: str):
        """Opens a stream to the GCS blob for reading."""
        if not self.client:
            return None
        try:
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(blob_name)
            if not blob.exists():
                return None
            return blob.open("rb")
        except Exception as e:
            logger.error("Failed to open file stream", error=str(e))
            return None

    def delete_file(self, blob_name: str) -> bool:
        """Deletes a file from the GCS bucket."""
        if not self.client:
            return False
            
        try:
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(blob_name)
            if blob.exists():
                blob.delete()
                logger.info("Deleted file from GCS", blob_name=blob_name)
                return True
            logger.warning("File not found in GCS for deletion", blob_name=blob_name)
            return False
        except Exception as e:
            logger.error("Failed to delete file from GCS", error=str(e), blob_name=blob_name)
            return False

    def upload_file(self, blob_name: str, file_obj, content_type: str) -> bool:
        """Uploads a file object to GCS."""
        if not self.client:
            return False
        try:
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(blob_name)
            blob.upload_from_file(file_obj, content_type=content_type)
            logger.info("Uploaded file to GCS", blob_name=blob_name)
            return True
        except Exception as e:
            logger.error("Failed to upload file to GCS", error=str(e), blob_name=blob_name)
            return False

    def upload_file_from_path(self, blob_name: str, local_path: str, content_type: str) -> bool:
        """Uploads a file from a local path to GCS."""
        if not self.client:
            return False
        try:
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(blob_name)
            blob.upload_from_filename(local_path, content_type=content_type)
            logger.info("Uploaded file from path to GCS", blob_name=blob_name, local_path=local_path)
            return True
        except Exception as e:
            logger.error("Failed to upload file from path to GCS", error=str(e), blob_name=blob_name)
            return False
