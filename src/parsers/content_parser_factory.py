from typing import Optional
from .base_parser import BaseContentParser
from .pdf_parser import PDFParser
from .docx_parser import DOCXParser
from .web_parser import WebParser
from .youtube_parser import YouTubeParser


class ContentParserFactory:
    """Factory for creating appropriate content parsers based on input type."""

    def __init__(self):
        self._parsers = {
            "pdf": PDFParser(),
            "docx": DOCXParser(),
            "web_url": WebParser(),
            "youtube": YouTubeParser()
        }

    def get_parser(self, input_type: str) -> Optional[BaseContentParser]:
        """
        Get appropriate parser for the given input type.

        Args:
            input_type: Type of content to parse (pdf, docx, web_url)

        Returns:
            Parser instance or None if type not supported
        """
        return self._parsers.get(input_type.lower())

    def detect_input_type(self, source: str, filename: Optional[str] = None) -> Optional[str]:
        """
        Detect input type from source or filename.

        Args:
            source: Source string (URL or file path)
            filename: Optional filename for uploaded files

        Returns:
            Detected input type or None if cannot determine
        """
        # If filename provided, use extension
        if filename:
            filename_lower = filename.lower()
            if filename_lower.endswith(".pdf"):
                return "pdf"
            elif filename_lower.endswith((".docx", ".doc")):
                return "docx"

        # Check source string
        source_lower = source.lower()

        # Check for file extensions in source
        if source_lower.endswith(".pdf"):
            return "pdf"
        elif source_lower.endswith((".docx", ".doc")):
            return "docx"

        # Check for URLs
        if source_lower.startswith(("http://", "https://")):
            return "web_url"

        return None

    def get_supported_types(self) -> list[str]:
        """Get list of all supported input types."""
        return list(self._parsers.keys())

    def validate_input_type(self, input_type: str) -> bool:
        """Check if input type is supported."""
        return input_type.lower() in self._parsers