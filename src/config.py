from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    api_host: str = Field(default="localhost", description="API host")
    api_port: int = Field(default=8000, description="API port")
    debug: bool = Field(default=False, description="Debug mode")
    
    database_url: str = Field(
        default="sqlite:///./test.db",
        description="Database URL",
        examples=["sqlite:///./test.db"]
    )
    db_host: str = Field(default="localhost", description="Database host")
    db_port: int = Field(default=5432, description="Database port")
    db_name: str = Field(default="ai_video_tutor", description="Database name")
    db_user: str = Field(default="test_user", description="Database user")
    db_password: str = Field(default="test_password", description="Database password")
    
    # LLM Provider API Keys
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API key")
    google_api_key: Optional[str] = Field(default=None, description="Google API key for Gemini and Speech-to-Text")

    firebase_service_account_path: str = Field(default="parkhoai-864b2-firebase-adminsdk-fbsvc-f3da414502.json", description="Firebase service account JSON file path")
    firebase_project_id: str = Field(default="parkhoai-864b2", description="Firebase project ID")
    firebase_web_client_id: str = Field(default="846780462763-41qfms7hjen9er8ak9j4n5cevc8pkoti.apps.googleusercontent.com", description="Firebase web client ID")
    
    max_video_length_minutes: int = Field(default=30, description="Maximum video length in minutes")
    max_concurrent_jobs: int = Field(default=5, description="Maximum concurrent processing jobs")
    job_timeout_minutes: int = Field(default=10, description="Job timeout in minutes")
    temp_files_dir: str = Field(default="/tmp/ai_video_tutor", description="Temporary files directory")
    file_storage_dir: str = Field(default="./uploaded_files", description="Persistent file storage directory")
    
    whisper_model: str = Field(default="base", description="Whisper model to use")
    audio_chunk_duration_minutes: int = Field(default=10, description="Audio chunk duration in minutes")
    
    secret_key: str = Field(default="test_secret_key_change_in_production", description="Secret key for session management")
    allowed_origins: list[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:5173",
            "https://parkho-ai-frontend-846780462763.us-central1.run.app"
        ],
        description="Allowed CORS origins"
    )
    
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json or text)")
    
    rate_limit_per_minute: int = Field(default=10, description="Rate limit per minute")
    rate_limit_per_hour: int = Field(default=100, description="Rate limit per hour")

    # Analytics Configuration
    analytics_enabled: bool = Field(default=True, description="Enable analytics tracking")
    analytics_retention_days: int = Field(default=365, description="Analytics data retention in days")

    # GCP Configuration
    gcp_project_id: str = Field(default="parkhoai-864b2", description="GCP Project ID")
    storage_bucket: str = Field(default="parkhoai-content-storage", description="GCS bucket for file storage")
    use_cloud_storage: bool = Field(default=False, description="Use Cloud Storage instead of local storage")
    use_secret_manager: bool = Field(default=False, description="Use Secret Manager for API keys")

    # RAG Engine Configuration
    rag_engine_url: str = Field(default="http://localhost:8001/api/v1", description="RAG Engine API base URL")

    # Analytics Dashboard Configuration
    analytics_provider: str = Field(default="google_studio", description="Analytics dashboard provider")

    # Google Data Studio Configuration
    google_studio_learning_report_id: str = Field(default="", description="Google Data Studio learning analytics report ID")
    google_studio_quiz_report_id: str = Field(default="", description="Google Data Studio quiz performance report ID")
    google_studio_content_report_id: str = Field(default="", description="Google Data Studio content analytics report ID")
    google_studio_user_report_id: str = Field(default="", description="Google Data Studio user insights report ID")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()