import os
import tempfile
import asyncio
import structlog
from typing import Dict, Any
import yt_dlp

from .base_parser import BaseContentParser, ContentParseResult
from ..config import get_settings
from ..services.transcription_service import TranscriptionService

settings = get_settings()
logger = structlog.get_logger(__name__)


class YouTubeParser(BaseContentParser):

    def __init__(self):
        self.max_duration = settings.max_video_length_minutes * 60
        self.transcription_service = TranscriptionService(
            openai_api_key=settings.openai_api_key,
            google_api_key=settings.google_api_key
        )

    async def parse(self, source: str, **kwargs) -> ContentParseResult:
        try:
            video_info = await self._extract_video_info(source)
            if not video_info["success"]:
                return ContentParseResult("", error=video_info["error"])

            if video_info["duration"] > self.max_duration:
                return ContentParseResult("", error=f"Video too long: {video_info['duration']/60:.1f} minutes (max: {self.max_duration/60} minutes)")

            audio_path = await self._download_audio(source)


            transcript = await self.transcription_service.transcribe_with_fallback(audio_path)

            os.unlink(audio_path)

            return ContentParseResult(
                content=transcript,
                title=video_info["title"],
                metadata={
                    "duration": video_info["duration"],
                    "url": source,
                    "description": video_info.get("description", ""),
                    "source_type": "youtube"
                }
            )
        except Exception as e:
            return ContentParseResult("", error=f"YouTube processing failed: {str(e)}")

    async def _extract_video_info(self, url: str) -> Dict[str, Any]:
        def extract_info():
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "extractor_retries": 3,
                "fragment_retries": 3,
                "http_chunk_size": 10485760,
                "socket_timeout": 30,
                # Anti-bot detection measures
                "sleep_interval": 1,
                "sleep_interval_requests": 1,
                "http_headers": {
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-us,en;q=0.5",
                    "Accept-Encoding": "gzip, deflate",
                    "DNT": "1",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                },
            }

            # Removed cookiesfrombrowser configuration to fix "no such table: meta" error
            # YouTube public content doesn't require browser cookies

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)

        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, extract_info)
            return {
                "success": True,
                "title": info.get("title", ""),
                "duration": info.get("duration", 0),
                "description": info.get("description", "")
            }
        except Exception as e:
            logger.error(f"yt-dlp info extraction failed: {str(e)}")
            return {"success": False, "error": str(e)}


    async def _download_audio(self, url: str) -> str:
        def download():
            with tempfile.NamedTemporaryFile(suffix=".%(ext)s", delete=False) as temp_file:
                output_template = temp_file.name.replace(".%(ext)s", "")

            #REVISIT - Duplicate Code, make it a single method
            ydl_opts = {
                "format": "worstaudio[ext=m4a]/worst[ext=mp4]/bestaudio/best",
                "outtmpl": f"{output_template}.%(ext)s",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "64"
                }],
                "quiet": True,
                "no_warnings": True,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "extractor_retries": 3,
                "fragment_retries": 3,
                "http_chunk_size": 10485760,
                "socket_timeout": 30,
                "retries": 5,
                # Anti-bot detection measures
                "sleep_interval": 1,
                "sleep_interval_requests": 1,
                "http_headers": {
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-us,en;q=0.5",
                    "Accept-Encoding": "gzip, deflate",
                    "DNT": "1",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                },
            }

            # Removed cookiesfrombrowser configuration to fix "no such table: meta" error
            # YouTube public content doesn't require browser cookies

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            return f"{output_template}.mp3"

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, download)


    def supports_source(self, source: str) -> bool:
        return "youtube.com" in source or "youtu.be" in source

    @property
    def supported_types(self) -> list[str]:
        return ["youtube"]