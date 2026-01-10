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
        self.service_account_email = settings.service_account_email
        try:
            if settings.firebase_service_account_path and os.path.exists(settings.firebase_service_account_path):
                 try:
                     logger.info("Loading GCP credentials from service account file", path=settings.firebase_service_account_path)
                     self.credentials = service_account.Credentials.from_service_account_file(
                         settings.firebase_service_account_path
                     )
                     self.client = storage.Client(credentials=self.credentials, project=self.project_id)
                     self.service_account_email = self.credentials.service_account_email
                 except Exception as e:
                     logger.warning("Failed to load service account file, falling back to ADC", error=str(e))
                     self._init_adc()
            else:
                logger.info("No service account file found or configured, using ADC")
                self._init_adc()
                
        except Exception as e:
            logger.error("Failed to initialize GCP Storage Client", error=str(e))
            self.client = None

    def _init_adc(self):
        import google.auth
        import requests
        logger.info("Initializing GCP Storage Client using ADC")
        credentials, project = google.auth.default()
        self.client = storage.Client(credentials=credentials, project=self.project_id)
        
        self.service_account_email = getattr(credentials, "service_account_email", None)
        
        # Metadata Server Fallback for Cloud Run / GCE
        if not self.service_account_email:
             logger.info("Service account email not found in ADC credentials, attempting Metadata Server lookup")
             try:
                 # Metadata server URL for default service account email
                 metadata_url = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email"
                 headers = {"Metadata-Flavor": "Google"}
                 response = requests.get(metadata_url, headers=headers, timeout=2)
                 if response.status_code == 200:
                     self.service_account_email = response.text.strip()
                     logger.info("Successfully retrieved service account email from Metadata Server", email=self.service_account_email)
                 else:
                     logger.warning("Metadata server lookup failed", status_code=response.status_code)
             except Exception as e:
                 logger.warning("Metadata server lookup raised exception", error=str(e))
        
        if self.service_account_email:
            logger.info("GCP Service initialized with service account", email=self.service_account_email)
        else:
            logger.warning("Could not determine service account email. IAM signing will fail if no private key is present.")

    def generate_upload_signed_url(
        self, 
        blob_name: str, 
        content_type: str, 
        expiration_minutes: int = 15
    ) -> str:
        if not self.client:
            raise ValueError("GCP Client not initialized")

        try:
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(blob_name)

            kwargs = {
                "version": "v4",
                "expiration": datetime.timedelta(minutes=expiration_minutes),
                "method": "PUT",
                "content_type": content_type,
            }
            
            # If using ADC without a private key (like on Cloud Run), we MUST provide the service account email
            if self.service_account_email:
                kwargs["service_account_email"] = self.service_account_email

            return blob.generate_signed_url(**kwargs)
        except Exception as e:
            logger.error("Failed to generate signed URL", error=str(e), service_account=self.service_account_email)
            # Re-raise with context
            raise Exception(f"URL Generation Failed: {str(e)} (Email: {self.service_account_email})")

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
            
            kwargs = {
                "version": "v4",
                "expiration": datetime.timedelta(minutes=expiration_minutes),
                "method": "GET",
            }
            if self.service_account_email:
                kwargs["service_account_email"] = self.service_account_email

            return blob.generate_signed_url(**kwargs)
        except Exception as e:
            logger.error("Failed to generate download signed URL", error=str(e), service_account=self.service_account_email)
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

    def upload_file_from_bytes(self, blob_name: str, file_bytes: bytes, content_type: str) -> Optional[str]:
        """
        Uploads file bytes to GCS and returns the public URL.
        Used for downloading and storing images.
        """
        if not self.client:
            return None
        try:
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(blob_name)
            blob.upload_from_string(file_bytes, content_type=content_type)
            logger.info("Uploaded file from bytes to GCS", blob_name=blob_name, size=len(file_bytes))
            return self.get_public_url(blob_name)
        except Exception as e:
            logger.error("Failed to upload file from bytes to GCS", error=str(e), blob_name=blob_name)
            return None
