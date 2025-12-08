import pytest
from unittest.mock import MagicMock, AsyncMock
import httpx
from pathlib import Path


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.max_video_length_minutes = 30
    settings.youtube_audio_cache_enabled = True
    settings.youtube_audio_cache_ttl_days = 7
    settings.youtube_use_native_transcripts = False
    settings.youtube_gemini_fallback_enabled = True
    settings.youtube_download_timeout_seconds = 300
    settings.youtube_transcription_timeout_seconds = 300
    settings.youtube_gemini_fallback_timeout_seconds = 180
    settings.youtube_native_transcript_timeout_seconds = 30
    settings.max_audio_file_size_mb = 500
    settings.youtube_audio_quality = "bestaudio"
    settings.youtube_audio_format = "mp3"
    settings.openai_api_key = "test-openai-key"
    settings.google_api_key = "test-google-key"
    settings.anthropic_api_key = "test-anthropic-key"
    settings.gemini_video_model_name = "gemini-2.5-flash"
    return settings


@pytest.fixture
def sample_pdf_content():
    return "# Sample PDF Document\n\nThis is test content from a PDF file.\n\n## Section 1\n\nSome content here."


@pytest.fixture
def sample_web_content():
    return "# Sample Web Page\n\nThis is test content from a web page.\n\nSome additional content here."


@pytest.fixture
def mock_youtube_metadata():
    return {
        "success": True,
        "title": "Test Video Title",
        "duration": 120,
        "description": "Test video description"
    }


@pytest.fixture
def mock_httpx_response():
    response = MagicMock(spec=httpx.Response)
    response.text = "# Sample Web Content\n\nTest content from Jina API"
    response.headers = {
        "X-Title": "Sample Web Title",
        "X-Description": "Sample description"
    }
    response.raise_for_status = MagicMock()
    return response


@pytest.fixture
def mock_audio_cache_service():
    cache = MagicMock()
    cache.get_cached_audio_path = AsyncMock(return_value=None)
    cache.cache_audio_file = AsyncMock(return_value=True)
    cache.is_valid = MagicMock(return_value=True)
    return cache


@pytest.fixture
def mock_transcription_service():
    service = MagicMock()
    service.transcribe_with_fallback = AsyncMock(return_value="Sample transcribed text")
    return service


@pytest.fixture
def mock_llm_service():
    service = MagicMock()
    service.generate_video_content = AsyncMock(return_value="Sample Gemini response with transcript")
    return service


@pytest.fixture
def sample_video_path(tmp_path):
    video_file = tmp_path / "test_video.mp4"
    video_file.write_bytes(b"fake video content")
    return video_file


@pytest.fixture
def sample_audio_path(tmp_path):
    audio_file = tmp_path / "test_audio.mp3"
    audio_file.write_bytes(b"fake audio content")
    return audio_file