from functools import lru_cache
from typing import Optional

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):

    api_host: str = Field(default="localhost", description="API host")
    api_port: int = Field(default=8000, description="API port")
    debug: bool = Field(default=False, description="Debug mode")

    # Authentication Configuration
    authentication_enabled: bool = Field(default=True, description="Enable authentication for all API endpoints")
    
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
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:3001",
            "*",
            "https://parkho-ai-frontend-ku7bn6e62q-uc.a.run.app",
            "https://parkho-ai-frontend-846780462763.us-central1.run.app",
            "http://13.236.51.35:3000"

        ],
        description="Allowed CORS origins",
        validation_alias=AliasChoices("CORS_ALLOWED_ORIGINS", "ALLOWED_ORIGINS"),
    )
    
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json or text)")
    suppress_websocket_logs: bool = Field(
        default=True,
        description="Suppress uvicorn's noisy websocket handshake/access logs"
    )
    
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
    rag_engine_url: str = Field(default="https://rag-engine-api-846780462763.us-central1.run.app/api/v1", description="RAG Engine API base URL")

    # Analytics Dashboard Configuration
    analytics_provider: str = Field(default="google_studio", description="Analytics dashboard provider")

    # Google Data Studio Configuration
    google_studio_learning_report_id: str = Field(default="", description="Google Data Studio learning analytics report ID")
    google_studio_quiz_report_id: str = Field(default="", description="Google Data Studio quiz performance report ID")
    google_studio_content_report_id: str = Field(default="", description="Google Data Studio content analytics report ID")
    google_studio_user_report_id: str = Field(default="", description="Google Data Studio user insights report ID")

    # Question Generation Settings
    structured_response_default: bool = Field(default=True, description="Default value for structured response generation")
    max_questions_per_request: int = Field(default=20, description="Maximum questions allowed per request")
    default_question_score: int = Field(default=1, description="Default score per question")
    default_question_time: int = Field(default=60, description="Default time per question in seconds")
    physics_tutor_enabled: bool = Field(default=True, description="Enable physics tutor agent")
    question_enhancement_enabled: bool = Field(default=True, description="Enable question enhancement service")

    # RAG Intelligence Settings
    rag_intelligence_enabled: bool = Field(default=True, description="Enable intelligent RAG query processing")
    question_extraction_threshold: float = Field(default=0.8, description="Confidence threshold for direct question extraction")
    enable_cost_optimization: bool = Field(default=True, description="Enable cost optimization features (direct extraction)")
    jee_advanced_mode: bool = Field(default=True, description="Enable JEE Advanced specific features")

    # LLM Question Generation
    question_generation_temperature: float = Field(default=0.7, description="LLM temperature for question generation")
    question_generation_max_tokens: int = Field(default=10000, description="Max tokens for question generation")
    preferred_question_provider: str = Field(default="openai", description="Preferred LLM provider for questions")

    # LLM Model Names
    openai_model_name: str = Field(default="gpt-4o-mini", description="OpenAI model name")
    anthropic_model_name: str = Field(default="claude-3-haiku-20240307", description="Anthropic Claude model name")
    google_model_name: str = Field(default="gemini-1.5-flash-latest", description="Google Gemini model name")

    # Demo Mode Configuration
    demo_mode: bool = Field(default=False, description="Enable demo mode for development")
    demo_user_id: str = Field(default="demo-user-123", description="Default demo user ID")

    # YouTube Audio Caching Configuration
    youtube_audio_cache_enabled: bool = Field(
        default=True,
        description="Enable audio caching for YouTube videos"
    )
    youtube_audio_cache_dir: str = Field(
        default="youtube_audio",
        description="Directory name for cached YouTube audio files (relative to temp_files_dir)"
    )
    youtube_audio_cache_ttl_days: int = Field(
        default=7,
        description="Time-to-live for cached audio files in days"
    )
    max_audio_file_size_mb: int = Field(
        default=500,
        description="Maximum audio file size in MB"
    )

    # YouTube Download Settings
    youtube_download_timeout_seconds: int = Field(
        default=180,
        description="Timeout for YouTube audio download (3 minutes)"
    )
    youtube_audio_format: str = Field(
        default="mp3",
        description="Audio format for downloaded files (mp3, m4a)"
    )
    youtube_audio_quality: str = Field(
        default="bestaudio",
        description="Audio quality for yt-dlp (bestaudio, worstaudio)"
    )

    # YouTube Transcription Settings
    youtube_transcription_timeout_seconds: int = Field(
        default=300,
        description="Timeout for audio transcription (5 minutes)"
    )
    youtube_transcription_language: str = Field(
        default="en",
        description="Primary language for transcription"
    )

    # YouTube Fallback Settings
    youtube_gemini_fallback_enabled: bool = Field(
        default=True,
        description="Enable Gemini fallback when audio/transcription fails"
    )
    youtube_gemini_fallback_timeout_seconds: int = Field(
        default=120,
        description="Timeout for Gemini fallback processing (2 minutes)"
    )

    # YouTube Native Transcript Settings
    youtube_use_native_transcripts: bool = Field(
        default=False,
        description="Try YouTube native transcripts first (yt-dlp)"
    )
    youtube_cookies_file: str = Field(
        default="cookies.txt",
        description="Path to cookies.txt for YouTube authentication (bypasses bot detection)"
    )
    youtube_native_transcript_timeout_seconds: int = Field(
        default=30,
        description="Timeout for YouTube native transcript extraction"
    )

    # Cache Management
    youtube_cache_cleanup_enabled: bool = Field(
        default=True,
        description="Enable automatic cache cleanup"
    )
    youtube_cache_cleanup_interval_hours: int = Field(
        default=24,
        description="Interval for automatic cache cleanup in hours"
    )

    # Content Processing Strategy Configuration
    content_processing_strategy: str = Field(
        default="auto",
        description="Content processing strategy: auto, complex_pipeline, direct_gemini"
    )
    enable_strategy_fallback: bool = Field(
        default=True,
        description="Enable fallback to alternative strategy on failure"
    )
    max_pipeline_failures: int = Field(
        default=2,
        description="Maximum failures before switching strategy"
    )
    strategy_fallback_timeout_minutes: int = Field(
        default=5,
        description="Timeout before trying fallback strategy"
    )

    # Gemini Video API Configuration
    gemini_video_api_enabled: bool = Field(
        default=True,
        description="Enable Google Gemini video understanding API"
    )
    gemini_video_model_name: str = Field(
        default="gemini-2.5-flash",
        description="Gemini model for video processing (gemini-2.0-flash-exp supports YouTube URLs)"
    )
    gemini_video_timeout_seconds: int = Field(
        default=180,
        description="Timeout for Gemini video API calls"
    )

    # Strategy Performance Settings
    complex_pipeline_timeout_minutes: int = Field(
        default=10,
        description="Timeout for complex pipeline strategy"
    )
    direct_gemini_timeout_minutes: int = Field(
        default=3,
        description="Timeout for direct Gemini strategy"
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value):
        if value is None:
            return value
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    class Config:
        env_file = [".env", ".env.local"]  # .env.local takes precedence over .env
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()