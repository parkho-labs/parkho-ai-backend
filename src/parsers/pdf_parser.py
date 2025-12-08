import os
import time
import structlog
import pymupdf4llm

from .base_parser import BaseContentParser, ContentParseResult
from ..exceptions import FileProcessingError, ParsingError
from ..utils.file_utils import validate_file_exists, validate_file_size, extract_filename, extract_title
from ..utils.string_utils import extract_content_from_markdown, count_pages_from_content


logger = structlog.get_logger(__name__)


class PDFParser(BaseContentParser):
    MAX_FILE_SIZE_MB = 10

    async def parse(self, source: str, **kwargs) -> ContentParseResult:
        start_time = time.time()
        file_name = extract_filename(source)

        try:
            self._validate_file(source)
            file_size = os.path.getsize(source)

            logger.info("pdf_parse_started", file_name=file_name)

            md_text = self._extract_markdown(source)
            content = extract_content_from_markdown(md_text)
            metadata = self._build_metadata(source, file_size, content)

            processing_time = time.time() - start_time
            logger.info("pdf_parse_completed", file_name=file_name, processing_time=round(processing_time, 2))

            return ContentParseResult(
                content=content,
                title=extract_title(source),
                metadata=metadata
            )

        except (FileProcessingError, ParsingError) as e:
            logger.error("pdf_parse_failed", error=str(e), file_name=file_name)
            return ContentParseResult("", error=str(e))

    def _validate_file(self, file_path: str) -> None:
        validate_file_exists(file_path)
        validate_file_size(file_path, self.MAX_FILE_SIZE_MB)

    def _extract_markdown(self, file_path: str) -> str:
        try:
            return pymupdf4llm.to_markdown(file_path)
        except Exception as e:
            raise ParsingError(f"Failed to extract text from PDF: {str(e)}")

    def _build_metadata(self, file_path: str, file_size: int, content: str) -> dict:
        return {
            "file_name": extract_filename(file_path),
            "file_size": file_size,
            "page_count": count_pages_from_content(content),
            "title": extract_title(file_path),
            "source_type": "pdf",
            "content_length": len(content)
        }

    def supports_source(self, source: str) -> bool:
        return source.lower().endswith(".pdf")

    @property
    def supported_types(self) -> list[str]:
        return ["pdf"]
