import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from src.parsers.youtube import YouTubeParser


class TestYouTubeParser:
    @pytest.fixture(autouse=True)
    def setup_parser(self, mock_settings):
        with patch('src.parsers.youtube.youtube_parser.get_settings') as mock_settings_func:
            mock_settings_func.return_value = mock_settings
            self.parser = YouTubeParser()

    @pytest.mark.parametrize("url,expected_id", [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ")
    ])
    def test_extract_video_id_valid_urls(self, url, expected_id):
        result = self.parser.video_extractor.extract_video_id(url)
        assert result == expected_id

    def test_extract_video_id_invalid_url(self):
        with pytest.raises(Exception):
            self.parser.video_extractor.extract_video_id("https://example.com/video")

    @patch('yt_dlp.YoutubeDL')
    @pytest.mark.asyncio
    async def test_extract_video_info_success(self, mock_youtubedl):
        mock_instance = MagicMock()
        mock_instance.extract_info.return_value = {
            "title": "Test Video",
            "duration": 120,
            "description": "Test description"
        }
        mock_youtubedl.return_value.__enter__.return_value = mock_instance

        result = await self.parser.video_extractor.extract_video_info("https://youtu.be/test123")

        assert result["success"]
        assert result["title"] == "Test Video"
        assert result["duration"] == 120

    @patch('yt_dlp.YoutubeDL')
    @pytest.mark.asyncio
    async def test_extract_video_info_failure(self, mock_youtubedl):
        mock_instance = MagicMock()
        mock_instance.extract_info.side_effect = Exception("Download error")
        mock_youtubedl.return_value.__enter__.return_value = mock_instance

        result = await self.parser.video_extractor.extract_video_info("https://youtu.be/test123")

        assert not result["success"]

    @pytest.mark.asyncio
    async def test_parse_video_too_long(self):
        with patch.object(self.parser.video_extractor, 'extract_video_info') as mock_extract:
            mock_extract.return_value = {
                "success": True,
                "title": "Long Video",
                "duration": 3600,  # 60 minutes
                "description": "Test"
            }

            result = await self.parser.parse("https://youtu.be/dQw4w9WgXcQ")

        assert not result.success
        assert "too long" in result.error.lower()

    def test_parse_srt_to_text(self):
        srt_content = """1
00:00:01,000 --> 00:00:03,000
First line

2
00:00:04,000 --> 00:00:06,000
Second line"""

        result = self.parser.transcript_processor.parse_srt_content(srt_content)
        assert "First line" in result
        assert "Second line" in result

    @pytest.mark.parametrize("response,expected", [
        ({"transcript": "Test transcript"}, "Test transcript"),
        ("Direct string", "Direct string"),
    ])
    def test_extract_transcript_from_gemini_response(self, response, expected):
        result = self.parser.transcript_processor.gemini_strategy._extract_transcript_from_response(response)
        assert result == expected

    @pytest.mark.parametrize("url,expected", [
        ("https://youtube.com/watch?v=dQw4w9WgXcQ", True),
        ("https://youtu.be/dQw4w9WgXcQ", True),
        ("https://vimeo.com/123", False),
    ])
    def test_supports_source(self, url, expected):
        assert self.parser.supports_source(url) == expected

    def test_supported_types(self):
        assert self.parser.supported_types == ["youtube"]