import asyncio
import structlog
from typing import Dict, Any, Optional

from ...exceptions import TranscriptionError, LLMServiceError
from ...services.transcription_service import TranscriptionService
from ...services.llm_service import LLMService
from ...utils.string_utils import parse_srt_to_text, clean_text
from pathlib import Path

logger = structlog.get_logger(__name__)


class WhisperTranscriptionStrategy:
    def __init__(self, transcription_service: TranscriptionService):
        self.transcription_service = transcription_service

    async def transcribe(self, audio_path: Path) -> str:
        try:
            transcript = await self.transcription_service.transcribe_with_fallback(str(audio_path))
            if not transcript or len(transcript.strip()) < 10:
                raise TranscriptionError("Whisper returned empty or very short transcript")
            return clean_text(transcript)
        except Exception as e:
            raise TranscriptionError(f"Whisper transcription failed: {str(e)}")


class GeminiTranscriptionStrategy:
    TRANSCRIPT_PROMPT = """
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

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    async def transcribe(self, video_url: str) -> str:
        try:
            response = await self.llm_service.generate_video_content(
                video_url=video_url,
                prompt=self.TRANSCRIPT_PROMPT
            )

            transcript = self._extract_transcript_from_response(response)

            if not transcript or len(transcript.strip()) < 10:
                raise LLMServiceError("Gemini returned empty or very short transcript")

            return clean_text(transcript)

        except Exception as e:
            raise LLMServiceError(f"Gemini transcription failed: {str(e)}")

    def _extract_transcript_from_response(self, response: Any) -> str:
        if isinstance(response, dict) and "transcript" in response:
            return response["transcript"]
        return str(response)


class TranscriptProcessor:
    def __init__(self, transcription_service: TranscriptionService, llm_service: LLMService):
        self.whisper_strategy = WhisperTranscriptionStrategy(transcription_service)
        self.gemini_strategy = GeminiTranscriptionStrategy(llm_service)

    async def process_transcript(self, audio_path: Path, video_url: str, use_gemini_fallback: bool) -> str:
        try:
            transcript = await self.whisper_strategy.transcribe(audio_path)
            logger.info("whisper_transcription_completed", transcript_length=len(transcript))
            return transcript

        except TranscriptionError as e:
            if not use_gemini_fallback:
                raise e

            logger.warning("whisper_failed_trying_gemini", error=str(e))

            try:
                transcript = await self.gemini_strategy.transcribe(video_url)
                logger.info("gemini_transcription_completed", transcript_length=len(transcript))
                return transcript

            except LLMServiceError as gemini_error:
                logger.error("both_transcription_methods_failed", whisper_error=str(e), gemini_error=str(gemini_error))
                raise TranscriptionError(f"Whisper failed: {str(e)}, Gemini failed: {str(gemini_error)}")

    def parse_srt_content(self, srt_content: str) -> str:
        return parse_srt_to_text(srt_content)