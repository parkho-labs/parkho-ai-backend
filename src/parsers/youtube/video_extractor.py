import asyncio
import structlog
import yt_dlp
from typing import Dict, Any

from ...exceptions import ParsingError, ValidationError
from ...utils.url_utils import extract_youtube_video_id

logger = structlog.get_logger(__name__)


class VideoExtractor:
    def __init__(self, max_duration_seconds: int):
        self.max_duration = max_duration_seconds

    def extract_video_id(self, url: str) -> str:
        try:
            return extract_youtube_video_id(url)
        except ValidationError as e:
            raise ParsingError(str(e))

    async def extract_video_info(self, url: str) -> Dict[str, Any]:
        def _extract_sync():
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'skip_download': True
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)

        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, _extract_sync)

            return {
                "success": True,
                "title": info.get("title", "Unknown"),
                "duration": info.get("duration", 0),
                "description": info.get("description", ""),
                "uploader": info.get("uploader", "Unknown")
            }

        except Exception as e:
            logger.error("video_info_extraction_failed", error=str(e), url=url)
            return {"success": False, "error": str(e)}

    def validate_duration(self, duration_seconds: int) -> None:
        if duration_seconds > self.max_duration:
            duration_minutes = duration_seconds / 60
            max_minutes = self.max_duration / 60
            raise ParsingError(f"Video too long: {duration_minutes:.1f}min > {max_minutes}min")