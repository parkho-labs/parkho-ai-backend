import pytest
from unittest.mock import patch, MagicMock

from src.parsers.pdf_parser import PDFParser
from src.exceptions import ValidationError


class TestPDFParser:
    @pytest.fixture(autouse=True)
    def setup_parser(self):
        self.parser = PDFParser()

    @patch('fitz.open')
    @patch('pymupdf4llm.to_markdown')
    @patch('os.path.getsize')
    @patch('os.path.exists')
    @pytest.mark.asyncio
    async def test_parse_valid_pdf(self, mock_exists, mock_getsize, mock_markdown, mock_fitz_open):
        mock_exists.return_value = True
        mock_getsize.return_value = 1024
        mock_markdown.return_value = "# Sample PDF\n\nContent here"
        mock_doc = MagicMock()
        mock_doc.page_count = 5
        mock_fitz_open.return_value.__enter__.return_value = mock_doc

        result = await self.parser.parse("test.pdf")

        assert result.success
        assert "Sample PDF" in result.content
        assert result.metadata["source_type"] == "pdf"
        assert result.metadata["page_count"] == 5
        assert result.title == "test"

    @patch('os.path.exists')
    @pytest.mark.asyncio
    async def test_parse_file_not_found(self, mock_exists):
        mock_exists.return_value = False

        result = await self.parser.parse("/nonexistent/file.pdf")

        assert not result.success
        assert "not found" in result.error.lower()

    @patch('os.path.getsize')
    @patch('os.path.exists')
    @pytest.mark.asyncio
    async def test_parse_file_too_large(self, mock_exists, mock_getsize):
        mock_exists.return_value = True
        mock_getsize.return_value = 11 * 1024 * 1024

        result = await self.parser.parse("large.pdf")

        assert not result.success
        assert "too large" in result.error.lower()

    @patch('fitz.open')
    @patch('pymupdf4llm.to_markdown')
    @patch('os.path.getsize')
    @patch('os.path.exists')
    @pytest.mark.asyncio
    async def test_parse_empty_content(self, mock_exists, mock_getsize, mock_markdown, mock_fitz_open):
        mock_exists.return_value = True
        mock_getsize.return_value = 1024
        mock_markdown.return_value = ""
        mock_doc = MagicMock()
        mock_doc.page_count = 0
        mock_fitz_open.return_value.__enter__.return_value = mock_doc

        with pytest.raises(ValidationError, match="No text content found in PDF"):
            await self.parser.parse("empty.pdf")

    def test_build_metadata(self):
        content = "Page 1\n\n-----\n\nPage 2"
        metadata = self.parser._build_metadata("/test/document.pdf", 1024, content, page_count=2)

        assert metadata["file_name"] == "document.pdf"
        assert metadata["file_size"] == 1024
        assert metadata["page_count"] == 2
        assert metadata["title"] == "document"
        assert metadata["source_type"] == "pdf"

    def test_supports_source(self):
        assert self.parser.supports_source("document.pdf")
        assert self.parser.supports_source("DOCUMENT.PDF")
        assert not self.parser.supports_source("document.docx")

    def test_supported_types(self):
        assert self.parser.supported_types == ["pdf"]