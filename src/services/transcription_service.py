import structlog
from typing import Optional
from enum import Enum

import openai
from google.cloud import speech
import google.generativeai as genai

logger = structlog.get_logger(__name__)


class TranscriptionProvider(str, Enum):
    OPENAI = "openai"
    GOOGLE = "google"
    LOCAL_WHISPER = "local_whisper"


class TranscriptionService:
    def __init__(self, openai_api_key: Optional[str] = None, google_api_key: Optional[str] = None):
        self.openai_api_key = openai_api_key
        self.google_api_key = google_api_key

        if google_api_key:
            try:
                genai.configure(api_key=google_api_key)
                self.google_client = speech.SpeechClient()
            except Exception:
                self.google_client = None
        else:
            self.google_client = None

    async def transcribe_with_fallback(self, audio_path: str, language: str = "en") -> str:
        if self.openai_api_key:
            try:
                return await self._transcribe_openai(audio_path, language)
            except Exception as e:
                logger.warning(f"OpenAI failed: {e}")

        if self.google_client and self.google_api_key:
            try:
                return await self._transcribe_google(audio_path, language)
            except Exception as e:
                logger.warning(f"Google failed: {e}")

        try:
            return await self._transcribe_local_whisper(audio_path, language)
        except Exception as e:
            raise ValueError(f"All transcription providers failed: {e}")

    async def _transcribe_openai(self, audio_path: str, language: str) -> str:
        """Transcribe using OpenAI Whisper API."""
        import asyncio

        def transcribe():
            if not self.openai_api_key:
                raise ValueError("OpenAI API key not available")

            client = openai.OpenAI(api_key=self.openai_api_key)
            with open(audio_path, "rb") as audio_file:
                response = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=language
                )
            return response.text

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, transcribe)
        logger.info("OpenAI transcription completed", transcript_length=len(result))
        return result

    async def _transcribe_google(self, audio_path: str, language: str) -> str:
        """Transcribe using Google Speech-to-Text."""
        import asyncio

        def transcribe():
            if not self.google_client:
                raise ValueError("Google Speech client not available")

            # Read audio file
            with open(audio_path, "rb") as audio_file:
                content = audio_file.read()

            # Configure recognition
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.MP3,
                sample_rate_hertz=16000,
                language_code=f"{language}-US" if language == "en" else language,
            )

            audio = speech.RecognitionAudio(content=content)

            # Perform transcription
            response = self.google_client.recognize(config=config, audio=audio)

            # Extract text
            transcript = ""
            for result in response.results:
                transcript += result.alternatives[0].transcript + " "

            return transcript.strip()

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, transcribe)
        logger.info("Google transcription completed", transcript_length=len(result))
        return result

    async def _transcribe_local_whisper(self, audio_path: str, language: str) -> str:
        """Transcribe using local faster-whisper."""
        import asyncio

        def transcribe():
            try:
                from faster_whisper import WhisperModel
            except ImportError:
                raise ValueError("faster-whisper not installed. Install with: pip install faster-whisper")

            # Initialize model (downloads on first use)
            model = WhisperModel("base", device="cpu", compute_type="int8")

            # Transcribe
            segments, info = model.transcribe(audio_path, language=language)

            # Combine segments
            transcript = " ".join([segment.text for segment in segments])
            return transcript

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, transcribe)
        logger.info("Local Whisper transcription completed", transcript_length=len(result))
        return result

    def get_available_providers(self) -> list[TranscriptionProvider]:
        """Get list of available transcription providers."""
        providers = []

        if self.openai_api_key:
            providers.append(TranscriptionProvider.OPENAI)

        if self.google_client and self.google_api_key:
            providers.append(TranscriptionProvider.GOOGLE)

        # Local Whisper always available (if package installed)
        try:
            import faster_whisper
            providers.append(TranscriptionProvider.LOCAL_WHISPER)
        except ImportError:
            pass

        return providers