from typing import Optional
from .base_parser import BaseContentParser
from .pdf_parser import PDFParser
from .docx_parser import DOCXParser
from .web_parser import WebParser
from .youtube_parser import YouTubeParser


class ContentParserFactory:
    def __init__(self):
        self._parsers = {
            "pdf": PDFParser(),
            "docx": DOCXParser(),
            "web_url": WebParser(),
            "youtube": YouTubeParser()
        }

    def get_parser(self, input_type: str) -> Optional[BaseContentParser]:
        return self._parsers.get(input_type.lower())

    #REVISIT - can have a better way for this, instead od comparing string.. that takes time. 
    def detect_input_type(self, source: str, filename: Optional[str] = None) -> Optional[str]:
        if filename:
            filename_lower = filename.lower()
            if filename_lower.endswith(".pdf"):
                return "pdf"
            elif filename_lower.endswith((".docx", ".doc")):
                return "docx"

        source_lower = source.lower()

        if source_lower.endswith(".pdf"):
            return "pdf"
        elif source_lower.endswith((".docx", ".doc")):
            return "docx"

        if source_lower.startswith(("http://", "https://")):
            return "web_url"

        return None

    def get_supported_types(self) -> list[str]:
        return list(self._parsers.keys())

    def validate_input_type(self, input_type: str) -> bool:
        return input_type.lower() in self._parsers