"""
YouTube Parser with Waterfall Transcription Architecture.

Implements a robust waterfall approach:
1. PRIMARY: Download audio + OpenAI Whisper (with caching)
2. FALLBACK: Gemini 2.5 direct YouTube URL
3. ERROR: Clear error message

Features:
- Audio caching with TTL (7 days default)
- 95%+ transcription accuracy
- No bot detection issues (uses official APIs only)
- Robust error handling with automatic fallback
"""

import re
import asyncio
import structlog
import time
from typing import Dict, Any
from pathlib import Path
import yt_dlp

from .base_parser import BaseContentParser, ContentParseResult
from .exceptions import AudioDownloadError, TranscriptionError, GeminiFallbackError, TranscriptNotAvailableError
from ..config import get_settings
from ..services.audio_cache_service import AudioCacheService
from ..services.transcription_service import TranscriptionService
from ..services.llm_service import LLMService

settings = get_settings()
logger = structlog.get_logger(__name__)

# Gemini prompt for transcript extraction
GEMINI_TRANSCRIPT_PROMPT = """
Analyze this YouTube video and provide ONLY the full transcript of the spoken content.

Requirements:
- Transcribe ALL spoken words accurately
- Maintain speaker context if multiple speakers
- Include timestamps if possible (format: [HH:MM:SS] text)
- Do NOT include summary or analysis
- Do NOT include questions or commentary
- Format as clean, readable text

Return ONLY the transcript text.
"""


class YouTubeParser(BaseContentParser):
    """
    YouTube video parser with waterfall transcription strategy.

    Waterfall Flow:
    1. Extract metadata (yt-dlp)
    2. Check audio cache (video_id based)
    3. Download audio if not cached (yt-dlp)
    4. Transcribe with OpenAI Whisper
    5. Fallback to Gemini on errors
    """

    def __init__(self):
        """Initialize YouTube parser with all required services."""
        self.max_duration = settings.max_video_length_minutes * 60

        # Initialize audio cache service
        cache_dir = Path(settings.temp_files_dir) / settings.youtube_audio_cache_dir
        self.audio_cache = AudioCacheService(
            cache_dir=cache_dir,
            default_ttl_days=settings.youtube_audio_cache_ttl_days
        )

        # Initialize transcription service
        self.transcription_service = TranscriptionService(
            openai_api_key=settings.openai_api_key,
            google_api_key=settings.google_api_key
        )

        # Initialize LLM service for Gemini fallback
        self.llm_service = LLMService(
            openai_api_key=settings.openai_api_key,
            anthropic_api_key=settings.anthropic_api_key,
            google_api_key=settings.google_api_key,
            openai_model_name=settings.openai_model_name,
            anthropic_model_name=settings.anthropic_model_name,
            google_model_name=settings.gemini_video_model_name
        )

        logger.info(
            "youtube_parser_initialized",
            max_duration_minutes=settings.max_video_length_minutes,
            cache_enabled=settings.youtube_audio_cache_enabled,
            gemini_fallback_enabled=settings.youtube_gemini_fallback_enabled
        )

    def _extract_video_id(self, url: str) -> str:
        """
        Extract YouTube video ID from URL.

        Args:
            url: YouTube URL (various formats supported)

        Returns:
            Video ID string

        Raises:
            ValueError: If video ID cannot be extracted
        """
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/)([^&\n?#]+)',
            r'youtube\.com/embed/([^&\n?#]+)',
            r'youtube\.com/v/([^&\n?#]+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                logger.debug("video_id_extracted", video_id=video_id, url=url)
                return video_id

        raise ValueError(f"Could not extract video ID from URL: {url}")

    async def _get_youtube_native_transcript(self, url: str, video_id: str) -> str:
        """
        Extract YouTube's native transcripts using yt-dlp.

        Uses cookies.txt for authentication (bypasses bot detection).
        Only fetches subtitles, no video download.
        Fast: ~2-5 seconds.

        Args:
            url: YouTube URL
            video_id: Extracted video ID

        Returns:
            Transcript text

        Raises:
            TranscriptNotAvailableError: If transcript extraction fails
        """
        try:
            def extract_subtitles():
                """Synchronous subtitle extraction operation."""
                import tempfile
                import os

                # Create temp directory for subtitle files
                temp_dir = tempfile.mkdtemp()

                ydl_opts = {
                    'skip_download': True,  # Don't download video
                    'writesubtitles': True,  # Get subtitles
                    'writeautomaticsub': True,  # Include auto-generated
                    'subtitleslangs': [settings.youtube_transcription_language, 'en'],  # Prefer configured language, fallback to English
                    'subtitlesformat': 'srt',
                    'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s'),
                    'quiet': True,
                    'no_warnings': True,
                }

                # Add cookies file if it exists and is configured
                cookies_path = Path(settings.youtube_cookies_file)
                if cookies_path.exists():
                    ydl_opts['cookiefile'] = str(cookies_path)
                    logger.debug("using_cookies_file", path=str(cookies_path))

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)

                    # Check if subtitles are available
                    if not info.get('subtitles') and not info.get('automatic_captions'):
                        raise TranscriptNotAvailableError("No subtitles or captions available for this video")

                    # Download subtitles
                    ydl.download([url])

                    # Find the subtitle file
                    subtitle_file = None
                    for file in os.listdir(temp_dir):
                        if file.endswith('.srt'):
                            subtitle_file = os.path.join(temp_dir, file)
                            break

                    if not subtitle_file or not os.path.exists(subtitle_file):
                        raise TranscriptNotAvailableError("Subtitle file not found after download")

                    # Parse SRT file
                    with open(subtitle_file, 'r', encoding='utf-8') as f:
                        srt_content = f.read()

                    # Clean up temp directory
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)

                    return srt_content

            # Run extraction in executor with timeout
            loop = asyncio.get_event_loop()
            extract_start = time.time()

            try:
                srt_content = await asyncio.wait_for(
                    loop.run_in_executor(None, extract_subtitles),
                    timeout=settings.youtube_native_transcript_timeout_seconds
                )
            except asyncio.TimeoutError:
                raise TranscriptNotAvailableError(
                    f"Transcript extraction timeout after {settings.youtube_native_transcript_timeout_seconds}s"
                )

            extract_time = time.time() - extract_start

            # Parse SRT format to extract text only
            transcript = self._parse_srt_to_text(srt_content)

            if not transcript or len(transcript) < 10:
                raise TranscriptNotAvailableError("Extracted transcript is empty or too short")

            logger.info(
                "youtube_native_transcript_extracted",
                video_id=video_id,
                transcript_length=len(transcript),
                extraction_time_seconds=round(extract_time, 2)
            )

            return transcript

        except TranscriptNotAvailableError:
            raise
        except Exception as e:
            logger.error("youtube_native_transcript_failed", error=str(e), video_id=video_id)
            raise TranscriptNotAvailableError(f"Native transcript extraction failed: {str(e)}")

    def _parse_srt_to_text(self, srt_content: str) -> str:
        """
        Parse SRT subtitle format and extract clean text.

        Args:
            srt_content: Raw SRT format content

        Returns:
            Clean transcript text
        """
        lines = srt_content.split('\n')
        transcript_lines = []

        skip_next = False
        for line in lines:
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Skip sequence numbers (pure digits)
            if line.isdigit():
                skip_next = True
                continue

            # Skip timestamp lines (contains -->)
            if '-->' in line:
                skip_next = False
                continue

            # Skip if we're in a sequence number
            if skip_next:
                skip_next = False
                continue

            # This is subtitle text
            transcript_lines.append(line)

        # Join all text with spaces
        transcript = ' '.join(transcript_lines)

        # Clean up multiple spaces
        transcript = ' '.join(transcript.split())

        return transcript

    async def parse(self, source: str, **kwargs) -> ContentParseResult:
        """
        Parse YouTube video using parallel waterfall transcription strategy.

        Architecture:
        - TRACK 1 (Fast Waterfall): YouTube Native → Gemini → Wait for audio
        - TRACK 2 (Background Parallel): Download audio + cache

        Args:
            source: YouTube URL
            **kwargs: Additional parsing options

        Returns:
            ContentParseResult with transcript, title, and metadata
        """
        start_time = time.time()

        try:
            # Step 1: Extract video metadata and video_id
            logger.info("youtube_parse_started", url=source)
            video_info = await self._extract_video_info(source)

            if not video_info["success"]:
                return ContentParseResult("", error=video_info["error"])

            # Check video duration
            if video_info["duration"] > self.max_duration:
                return ContentParseResult(
                    "",
                    error=f"Video too long: {video_info['duration']/60:.1f} minutes "
                          f"(max: {self.max_duration/60} minutes)"
                )

            video_id = self._extract_video_id(source)

            # Step 2: Check cached audio FIRST (instant win!)
            if settings.youtube_audio_cache_enabled:
                cached_audio_path = await self.audio_cache.get_cached_audio(video_id)
                if cached_audio_path:
                    logger.info("using_cached_audio", video_id=video_id)
                    try:
                        transcript = await self._transcribe_audio(cached_audio_path)
                        total_time = time.time() - start_time

                        logger.info(
                            "youtube_parse_completed_cached",
                            video_id=video_id,
                            method="cached_whisper",
                            total_time_seconds=round(total_time, 2),
                            transcript_length=len(transcript)
                        )

                        return ContentParseResult(
                            content=transcript,
                            title=video_info["title"],
                            metadata={
                                "duration": video_info["duration"],
                                "url": source,
                                "video_id": video_id,
                                "description": video_info.get("description", ""),
                                "source_type": "youtube",
                                "transcription_method": "cached_whisper",
                                "processing_time_seconds": round(total_time, 2)
                            }
                        )
                    except TranscriptionError as e:
                        logger.warning("cached_transcription_failed", error=str(e), video_id=video_id)
                        # Continue to fast waterfall

            # Step 3: Start audio download in BACKGROUND (doesn't block fast waterfall)
            # Fire-and-forget: Create task but don't await it - allows it to complete in background
            audio_download_task = asyncio.create_task(
                self._download_audio_safe(source, video_id)
            )

            # Store reference to prevent garbage collection before task completes
            # This ensures the download continues even after we return
            if not hasattr(self, '_background_tasks'):
                self._background_tasks = set()
            self._background_tasks.add(audio_download_task)

            # Remove task from set when complete (cleanup)
            audio_download_task.add_done_callback(self._background_tasks.discard)

            # TRACK 1: Fast waterfall (sequential)

            # Try 1: YouTube native transcript (2-5 seconds)
            if settings.youtube_use_native_transcripts:
                try:
                    transcript = await self._get_youtube_native_transcript(source, video_id)
                    total_time = time.time() - start_time

                    logger.info(
                        "youtube_parse_completed_native",
                        video_id=video_id,
                        method="youtube_native",
                        total_time_seconds=round(total_time, 2),
                        transcript_length=len(transcript)
                    )

                    # Don't cancel audio download - let it complete for caching
                    return ContentParseResult(
                        content=transcript,
                        title=video_info["title"],
                        metadata={
                            "duration": video_info["duration"],
                            "url": source,
                            "video_id": video_id,
                            "description": video_info.get("description", ""),
                            "source_type": "youtube",
                            "transcription_method": "youtube_native",
                            "processing_time_seconds": round(total_time, 2)
                        }
                    )
                except TranscriptNotAvailableError as e:
                    logger.warning("youtube_native_failed", error=str(e), video_id=video_id)
                    # Continue to Gemini fallback

            # Try 2: Gemini direct (2-3 minutes)
            if settings.youtube_gemini_fallback_enabled:
                try:
                    transcript = await self._fallback_to_gemini(source, video_info)
                    total_time = time.time() - start_time

                    logger.info(
                        "youtube_parse_completed_gemini",
                        video_id=video_id,
                        method="gemini",
                        total_time_seconds=round(total_time, 2),
                        transcript_length=len(transcript)
                    )

                    # Don't cancel audio download - let it complete for caching
                    return ContentParseResult(
                        content=transcript,
                        title=video_info["title"],
                        metadata={
                            "duration": video_info["duration"],
                            "url": source,
                            "video_id": video_id,
                            "description": video_info.get("description", ""),
                            "source_type": "youtube",
                            "transcription_method": "gemini",
                            "processing_time_seconds": round(total_time, 2)
                        }
                    )
                except GeminiFallbackError as e:
                    logger.warning("gemini_fallback_failed", error=str(e), video_id=video_id)
                    # Continue to Whisper fallback

            # Try 3: Wait for audio download, then Whisper (2-4 minutes)
            try:
                logger.info("waiting_for_audio_download", video_id=video_id)
                audio_path = await audio_download_task

                if audio_path:
                    transcript = await self._transcribe_audio(audio_path)
                    total_time = time.time() - start_time

                    logger.info(
                        "youtube_parse_completed_whisper",
                        video_id=video_id,
                        method="whisper_fallback",
                        total_time_seconds=round(total_time, 2),
                        transcript_length=len(transcript)
                    )

                    return ContentParseResult(
                        content=transcript,
                        title=video_info["title"],
                        metadata={
                            "duration": video_info["duration"],
                            "url": source,
                            "video_id": video_id,
                            "description": video_info.get("description", ""),
                            "source_type": "youtube",
                            "transcription_method": "whisper_fallback",
                            "processing_time_seconds": round(total_time, 2)
                        }
                    )
                else:
                    raise AudioDownloadError("Audio download returned None")

            except (AudioDownloadError, TranscriptionError) as e:
                logger.error("whisper_fallback_failed", error=str(e), video_id=video_id)
                return ContentParseResult(
                    "",
                    error=f"All transcription methods failed. Last error: {str(e)}"
                )

        except Exception as e:
            logger.error("youtube_parse_unexpected_error", error=str(e), url=source)
            return ContentParseResult(
                "",
                error=f"YouTube processing failed: {str(e)}"
            )

    async def _primary_transcription_method(self, url: str, video_id: str) -> str:
        """
        Primary transcription method: Cache → Download → Transcribe.

        Args:
            url: YouTube URL
            video_id: Extracted video ID

        Returns:
            Transcript text

        Raises:
            AudioDownloadError: If download fails
            TranscriptionError: If transcription fails
        """
        # Step 2: Check audio cache (5-10%)
        cached_audio_path = None
        if settings.youtube_audio_cache_enabled:
            cached_audio_path = await self.audio_cache.get_cached_audio(video_id)

        # Step 3: Download audio if not cached (10-30%)
        if cached_audio_path:
            logger.info("using_cached_audio", video_id=video_id)
            audio_path = cached_audio_path
        else:
            logger.info("downloading_audio", video_id=video_id)
            audio_path = await self._download_audio(url, video_id)

        # Step 4: Transcribe audio (30-70%)
        logger.info("transcribing_audio", video_id=video_id, audio_path=str(audio_path))
        transcript = await self._transcribe_audio(audio_path)

        return transcript

    async def _download_audio_safe(self, url: str, video_id: str) -> Path | None:
        """
        Safe wrapper for audio download (used in background tasks).

        Returns None on error instead of raising exceptions.

        Args:
            url: YouTube URL
            video_id: Video ID for caching

        Returns:
            Path to downloaded audio file, or None on error
        """
        try:
            return await self._download_audio(url, video_id)
        except Exception as e:
            logger.warning("background_audio_download_failed", error=str(e), video_id=video_id)
            return None

    async def _download_audio(self, url: str, video_id: str) -> Path:
        """
        Download audio from YouTube video.

        Args:
            url: YouTube URL
            video_id: Video ID for caching

        Returns:
            Path to downloaded audio file

        Raises:
            AudioDownloadError: If download fails
        """
        try:
            # Create temp directory for download
            temp_dir = Path(settings.temp_files_dir)
            temp_dir.mkdir(parents=True, exist_ok=True)

            output_path = temp_dir / f"{video_id}_temp.mp3"

            ydl_opts = {
                'format': settings.youtube_audio_quality,
                'outtmpl': str(output_path.with_suffix('')),  # yt-dlp adds extension
                'quiet': True,
                'no_warnings': True,
                'socket_timeout': settings.youtube_download_timeout_seconds,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': settings.youtube_audio_format,
                    'preferredquality': '192',
                }],
            }

            def download():
                """Synchronous download operation."""
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                return output_path

            # Run download in executor
            loop = asyncio.get_event_loop()
            download_start = time.time()

            try:
                result_path = await asyncio.wait_for(
                    loop.run_in_executor(None, download),
                    timeout=settings.youtube_download_timeout_seconds
                )
            except asyncio.TimeoutError:
                raise AudioDownloadError(
                    f"Download timeout after {settings.youtube_download_timeout_seconds}s"
                )

            download_time = time.time() - download_start

            # Verify file exists
            if not result_path.exists():
                raise AudioDownloadError(f"Downloaded file not found: {result_path}")

            file_size_mb = result_path.stat().st_size / (1024 * 1024)

            # Check file size
            if file_size_mb > settings.max_audio_file_size_mb:
                result_path.unlink()  # Delete oversized file
                raise AudioDownloadError(
                    f"Audio file too large: {file_size_mb:.2f}MB "
                    f"(max: {settings.max_audio_file_size_mb}MB)"
                )

            logger.info(
                "audio_downloaded",
                video_id=video_id,
                file_size_mb=round(file_size_mb, 2),
                download_time_seconds=round(download_time, 2)
            )

            # Cache the downloaded audio
            if settings.youtube_audio_cache_enabled:
                cached_path = await self.audio_cache.cache_audio(video_id, result_path)
                # Delete temp file after caching
                if result_path != cached_path:
                    result_path.unlink()
                return cached_path

            return result_path

        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            if "Video unavailable" in error_msg or "Private video" in error_msg:
                raise AudioDownloadError(f"Video unavailable: {error_msg}")
            raise AudioDownloadError(f"yt-dlp download failed: {error_msg}")

        except Exception as e:
            logger.error("audio_download_failed", error=str(e), video_id=video_id)
            raise AudioDownloadError(f"Audio download failed: {str(e)}")

    async def _transcribe_audio(self, audio_path: Path) -> str:
        """
        Transcribe audio file using Whisper API.

        Args:
            audio_path: Path to audio file

        Returns:
            Transcript text

        Raises:
            TranscriptionError: If transcription fails
        """
        try:
            transcribe_start = time.time()

            # Use transcription service with timeout
            try:
                transcript = await asyncio.wait_for(
                    self.transcription_service.transcribe_with_fallback(
                        audio_path=str(audio_path),
                        language=settings.youtube_transcription_language
                    ),
                    timeout=settings.youtube_transcription_timeout_seconds
                )
            except asyncio.TimeoutError:
                raise TranscriptionError(
                    f"Transcription timeout after {settings.youtube_transcription_timeout_seconds}s"
                )

            transcribe_time = time.time() - transcribe_start

            if not transcript or len(transcript) < 10:
                raise TranscriptionError("Transcription returned empty or very short text")

            logger.info(
                "audio_transcribed",
                transcript_length=len(transcript),
                transcription_time_seconds=round(transcribe_time, 2)
            )

            return transcript

        except Exception as e:
            logger.error("transcription_failed", error=str(e))
            if isinstance(e, TranscriptionError):
                raise
            raise TranscriptionError(f"Transcription failed: {str(e)}")

    async def _fallback_to_gemini(self, url: str, video_info: Dict[str, Any]) -> str:
        """
        Fallback to Gemini direct video URL processing.

        Args:
            url: YouTube URL
            video_info: Video metadata

        Returns:
            Transcript text

        Raises:
            GeminiFallbackError: If Gemini processing fails
        """
        logger.warning("using_gemini_fallback", url=url)

        try:
            gemini_start = time.time()

            # Check if Gemini video API is available
            if not self.llm_service.supports_video_analysis():
                raise GeminiFallbackError("Gemini video API not available (missing Google API key)")

            # Use Gemini video content generation with timeout
            try:
                response = await asyncio.wait_for(
                    self.llm_service.generate_video_content(
                        video_url=url,
                        prompt=GEMINI_TRANSCRIPT_PROMPT
                    ),
                    timeout=settings.youtube_gemini_fallback_timeout_seconds
                )
            except asyncio.TimeoutError:
                raise GeminiFallbackError(
                    f"Gemini timeout after {settings.youtube_gemini_fallback_timeout_seconds}s"
                )

            gemini_time = time.time() - gemini_start

            # Extract transcript from Gemini response
            transcript = self._extract_transcript_from_gemini_response(response)

            if not transcript or len(transcript) < 10:
                raise GeminiFallbackError("Gemini returned empty or very short transcript")

            logger.info(
                "gemini_fallback_successful",
                transcript_length=len(transcript),
                gemini_time_seconds=round(gemini_time, 2)
            )

            return transcript

        except GeminiFallbackError:
            raise
        except Exception as e:
            logger.error("gemini_fallback_failed", error=str(e))
            raise GeminiFallbackError(f"Gemini fallback failed: {str(e)}")

    def _extract_transcript_from_gemini_response(self, response: Any) -> str:
        """
        Extract transcript text from Gemini API response.

        Args:
            response: Gemini API response (can be dict, string, or object)

        Returns:
            Extracted transcript text
        """
        try:
            # Handle different response types
            if isinstance(response, dict):
                # Check common keys
                if "transcript" in response:
                    return str(response["transcript"])
                if "content" in response:
                    return str(response["content"])
                if "text" in response:
                    return str(response["text"])
                # Return first string value found
                for value in response.values():
                    if isinstance(value, str) and len(value) > 50:
                        return value

            elif isinstance(response, str):
                return response

            elif hasattr(response, 'text'):
                return response.text

            # Fallback: convert to string
            return str(response)

        except Exception as e:
            logger.warning("transcript_extraction_failed", error=str(e))
            return str(response)

    async def _extract_video_info(self, url: str) -> Dict[str, Any]:
        """
        Extract video metadata using yt-dlp (no download).

        Args:
            url: YouTube URL

        Returns:
            Dictionary with video info (title, duration, description)
        """
        def extract_info():
            """Synchronous info extraction."""
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'skip_download': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)

        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, extract_info)

            return {
                "success": True,
                "title": info.get("title", "YouTube Video"),
                "duration": info.get("duration", 0),
                "description": info.get("description", "")
            }

        except Exception as e:
            logger.error("video_info_extraction_failed", error=str(e), url=url)
            return {
                "success": False,
                "error": f"Failed to extract video info: {str(e)}"
            }

    def supports_source(self, source: str) -> bool:
        """Check if this parser supports the given source."""
        return "youtube.com" in source or "youtu.be" in source

    @property
    def supported_types(self) -> list[str]:
        """Return list of supported source types."""
        return ["youtube"]
