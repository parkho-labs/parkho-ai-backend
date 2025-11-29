import re
import asyncio
import structlog
import time
from typing import Dict, Any
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi

from .base_parser import BaseContentParser, ContentParseResult
from ..config import get_settings

settings = get_settings()
logger = structlog.get_logger(__name__)


class YouTubeParser(BaseContentParser):

    def __init__(self):
        self.max_duration = settings.max_video_length_minutes * 60

    def _extract_video_id(self, url: str) -> str:
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/)([^&\n?#]+)',
            r'youtube\.com/embed/([^&\n?#]+)',
            r'youtube\.com/v/([^&\n?#]+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        raise ValueError(f"Could not extract video ID from URL: {url}")

    async def parse(self, source: str, **kwargs) -> ContentParseResult:
        try:
            start_time = time.time()

            print(f"[TIMER] Starting YouTube Video Info Extraction...")
            video_info = await self._extract_video_info(source)
            info_time = time.time() - start_time
            print(f"[TIMER] Video Info Extraction: {info_time:.3f}s")

            if not video_info["success"]:
                return ContentParseResult("", error=video_info["error"])

            if video_info["duration"] > self.max_duration:
                return ContentParseResult("", error=f"Video too long: {video_info['duration']/60:.1f} minutes (max: {self.max_duration/60} minutes)")

            caption_start = time.time()
            print(f"[TIMER] Starting YouTube Caption Retrieval...")

            video_id = self._extract_video_id(source)
            logger.info(f"Extracted video ID: {video_id} from URL: {source}")

            def get_transcript():
                try:
                    logger.info(f"Attempting to fetch transcript for video {video_id}")
                    api = YouTubeTranscriptApi()
                    transcript = api.fetch(video_id)
                    logger.info(f"Successfully got transcript with {len(transcript)} entries")
                    return transcript
                except Exception as e:
                    logger.info(f"Direct fetch failed: {str(e)}")
                    try:
                        logger.info(f"Attempting to list transcripts for video {video_id}")
                        api = YouTubeTranscriptApi()
                        transcript_list = api.list(video_id)
                        logger.info(f"Found transcript list")

                        try:
                            logger.info(f"Looking for English transcript")
                            transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
                            return transcript.fetch()
                        except Exception as e3:
                            logger.info(f"English transcript search failed: {str(e3)}")
                            try:
                                logger.info(f"Looking for any available transcript")
                                for transcript in transcript_list:
                                    logger.info(f"Trying transcript: {transcript.language_code}")
                                    return transcript.fetch()
                            except Exception as e4:
                                logger.error(f"Failed to fetch any transcript: {str(e4)}")
                                raise Exception(f"No usable captions found for video {video_id}")

                    except Exception as e2:
                        logger.error(f"List transcripts failed: {str(e2)}")
                        raise Exception(f"No captions available for video {video_id}: {str(e)} | {str(e2)}")

            loop = asyncio.get_event_loop()
            transcript_list = await loop.run_in_executor(None, get_transcript)

            transcript = " ".join([entry.text for entry in transcript_list])
            logger.info(f"Successfully extracted transcript of length: {len(transcript)}")

            caption_time = time.time() - caption_start
            print(f"[TIMER] Caption Retrieval: {caption_time:.3f}s")

            total_time = time.time() - start_time
            print(f"[TIMER] Total YouTube Processing: {total_time:.3f}s")

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




    def supports_source(self, source: str) -> bool:
        return "youtube.com" in source or "youtu.be" in source

    @property
    def supported_types(self) -> list[str]:
        return ["youtube"]