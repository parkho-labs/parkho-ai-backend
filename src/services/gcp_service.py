from datetime import timedelta
import datetime
from typing import Optional
from google.cloud import storage
from google.oauth2 import service_account
import structlog

from src.config import Settings

logger = structlog.get_logger(__name__)


class GCPService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.bucket_name = settings.storage_bucket
        self.project_id = settings.gcp_project_id
        
        try:
            if settings.firebase_service_account_path:
                 self.credentials = service_account.Credentials.from_service_account_file(
                     settings.firebase_service_account_path
                 )
                 self.client = storage.Client(credentials=self.credentials, project=self.project_id)
            else:
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
