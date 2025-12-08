import asyncio
import tempfile
import os
import structlog
import yt_dlp
from pathlib import Path
from typing import Optional

from ...exceptions import ParsingError, TranscriptionError
from ...services.audio_cache_service import AudioCacheService

logger = structlog.get_logger(__name__)


class AudioProcessor:
    def __init__(self, audio_cache: AudioCacheService, max_file_size_mb: int = 500):
        self.audio_cache = audio_cache
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024

    async def get_audio_file(self, video_id: str, url: str) -> Path:
        if self.audio_cache.is_enabled():
            cached_path = await self.audio_cache.get_cached_audio_path(video_id)
            if cached_path and cached_path.exists():
                logger.info("audio_cache_hit", video_id=video_id)
                return cached_path

        audio_path = await self._download_audio(url, video_id)

        if self.audio_cache.is_enabled():
            await self.audio_cache.cache_audio_file(video_id, audio_path)

        return audio_path

    async def _download_audio(self, url: str, video_id: str) -> Path:
        temp_dir = Path(tempfile.mkdtemp())
        output_path = temp_dir / f"{video_id}.mp3"

        def _download_sync():
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': str(output_path),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'quiet': True,
                'no_warnings': True
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _download_sync)

            if not output_path.exists():
                raise ParsingError("Audio download failed - file not created")

            file_size = output_path.stat().st_size
            if file_size > self.max_file_size_bytes:
                output_path.unlink(missing_ok=True)
                size_mb = file_size / (1024 * 1024)
                max_mb = self.max_file_size_bytes / (1024 * 1024)
                raise ParsingError(f"Audio file too large: {size_mb:.1f}MB > {max_mb}MB")

            logger.info("audio_download_completed", video_id=video_id, file_size_mb=round(file_size / (1024 * 1024), 2))
            return output_path

        except Exception as e:
            if output_path.exists():
                output_path.unlink(missing_ok=True)
            raise TranscriptionError(f"Audio download failed: {str(e)}")

    def cleanup_temp_file(self, file_path: Path) -> None:
        try:
            if file_path.exists():
                file_path.unlink()
                parent = file_path.parent
                if parent != Path.cwd() and not any(parent.iterdir()):
                    parent.rmdir()
        except Exception as e:
            logger.warning("temp_file_cleanup_failed", file_path=str(file_path), error=str(e))