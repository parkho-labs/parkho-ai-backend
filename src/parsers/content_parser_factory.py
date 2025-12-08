from typing import Optional
from .base_parser import BaseContentParser
from .pdf_parser import PDFParser
from .docx_parser import DOCXParser
from .web_parser import WebParser
from .youtube import YouTubeParser
from .collection_parser import CollectionParser


class ContentParserFactory:
    def __init__(self):
        self._parsers = {
            "pdf": PDFParser(),
            "docx": DOCXParser(),
            "web_url": WebParser(),
            "youtube": YouTubeParser(),
            "collection": CollectionParser()
        }

    def get_parser(self, input_type: str) -> Optional[BaseContentParser]:
        return self._parsers.get(input_type.lower())

    def detect_input_type(self, source: str, filename: Optional[str] = None) -> Optional[str]:
        for parser_type, parser in self._parsers.items():
            if parser.supports_source(filename or source):
                return parser_type
        return None

    def get_supported_types(self) -> list[str]:
        return list(self._parsers.keys())

    def validate_input_type(self, input_type: str) -> bool:
        return input_type.lower() in self._parsers