import time
import structlog
from pathlib import Path

from ..base_parser import BaseContentParser, ContentParseResult
from ...config import get_settings
from ...services.audio_cache_service import AudioCacheService
from ...services.transcription_service import TranscriptionService
from ...services.llm_service import LLMService
from ...exceptions import ParsingError, ValidationError
from ...utils.url_utils import is_youtube_url

from .video_extractor import VideoExtractor
from .audio_processor import AudioProcessor
from .transcript_processor import TranscriptProcessor

logger = structlog.get_logger(__name__)


class YouTubeParser(BaseContentParser):
    def __init__(self):
        settings = get_settings()
        self.max_duration = settings.max_video_length_minutes * 60

        cache_dir = Path(settings.temp_files_dir) / settings.youtube_audio_cache_dir
        audio_cache = AudioCacheService(
            cache_dir=cache_dir,
            default_ttl_days=settings.youtube_audio_cache_ttl_days
        )

        transcription_service = TranscriptionService(
            openai_api_key=settings.openai_api_key,
            google_api_key=settings.google_api_key
        )

        llm_service = LLMService(
            openai_api_key=settings.openai_api_key,
            anthropic_api_key=settings.anthropic_api_key,
            google_api_key=settings.google_api_key,
            openai_model_name=settings.openai_model_name,
            anthropic_model_name=settings.anthropic_model_name,
            google_model_name=settings.gemini_video_model_name
        )

        self.video_extractor = VideoExtractor(self.max_duration)
        self.audio_processor = AudioProcessor(audio_cache, settings.max_audio_file_size_mb)
        self.transcript_processor = TranscriptProcessor(transcription_service, llm_service)
        self.use_gemini_fallback = settings.youtube_gemini_fallback_enabled

        logger.info("youtube_parser_initialized", max_duration_minutes=settings.max_video_length_minutes)

    async def parse(self, source: str, **kwargs) -> ContentParseResult:
        start_time = time.time()

        try:
            if not is_youtube_url(source):
                raise ValidationError("Invalid YouTube URL")

            video_id = self.video_extractor.extract_video_id(source)
            logger.info("youtube_parse_started", video_id=video_id)

            video_info = await self.video_extractor.extract_video_info(source)
            if not video_info.get("success"):
                raise ParsingError(f"Failed to extract video info: {video_info.get('error')}")

            duration = video_info.get("duration", 0)
            self.video_extractor.validate_duration(duration)

            audio_path = await self.audio_processor.get_audio_file(video_id, source)

            try:
                transcript = await self.transcript_processor.process_transcript(
                    audio_path, source, self.use_gemini_fallback
                )
            finally:
                self.audio_processor.cleanup_temp_file(audio_path)

            metadata = self._build_metadata(video_info, transcript, video_id)

            processing_time = time.time() - start_time
            logger.info("youtube_parse_completed", video_id=video_id, processing_time=round(processing_time, 2))

            return ContentParseResult(
                content=transcript,
                title=video_info.get("title"),
                metadata=metadata
            )

        except (ValidationError, ParsingError) as e:
            logger.error("youtube_parse_failed", error=str(e), url=source)
            return ContentParseResult("", error=str(e))

    def _build_metadata(self, video_info: dict, transcript: str, video_id: str) -> dict:
        return {
            "video_id": video_id,
            "title": video_info.get("title"),
            "duration": video_info.get("duration"),
            "uploader": video_info.get("uploader"),
            "description": video_info.get("description", "")[:500],
            "transcript_length": len(transcript),
            "source_type": "youtube"
        }

    def supports_source(self, source: str) -> bool:
        return is_youtube_url(source)

    @property
    def supported_types(self) -> list[str]:
        return ["youtube"]