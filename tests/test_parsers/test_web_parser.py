import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from src.parsers.web_parser import WebParser


class TestWebParser:
    @pytest.fixture(autouse=True)
    def setup_parser(self):
        self.parser = WebParser()

    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_parse_valid_url(self, mock_client):
        mock_response = MagicMock()
        mock_response.text = "# Sample Web Page\n\nTest content"
        mock_response.headers = {"X-Title": "Test Title", "X-Description": "Test Description"}
        mock_response.raise_for_status = MagicMock()

        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        result = await self.parser.parse("https://example.com")

        assert result.success
        assert "Sample Web Page" in result.content
        assert result.metadata["source_type"] == "web_url"

    @pytest.mark.asyncio
    async def test_parse_invalid_url(self):
        result = await self.parser.parse("invalid-url")

        assert not result.success
        assert "invalid url" in result.error.lower()

    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_parse_timeout(self, mock_client):
        import httpx
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=httpx.TimeoutException("Request timeout")
        )

        result = await self.parser.parse("https://example.com")

        assert not result.success
        assert "timed out" in result.error.lower()

    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_parse_http_error(self, mock_client):
        import httpx
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=httpx.HTTPStatusError("Not found", request=None, response=mock_response)
        )

        result = await self.parser.parse("https://example.com")

        assert not result.success
        assert "404" in result.error

    def test_build_metadata(self):
        mock_response = MagicMock()
        mock_response.headers = {"X-Title": "Test", "X-Description": "Desc"}

        metadata = self.parser._build_metadata("https://example.com", "example.com", mock_response, "content")

        assert metadata["url"] == "https://example.com"
        assert metadata["domain"] == "example.com"
        assert metadata["title"] == "Test"
        assert metadata["source_type"] == "web_url"

    def test_supports_source(self):
        assert self.parser.supports_source("https://example.com")
        assert self.parser.supports_source("http://example.com")
        assert not self.parser.supports_source("example.com")
        assert not self.parser.supports_source("")

    def test_supported_types(self):
        assert self.parser.supported_types == ["web_url"]