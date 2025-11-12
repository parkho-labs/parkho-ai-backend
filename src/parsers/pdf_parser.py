import os
from typing import Dict, Any
import PyPDF2
import pdfplumber

from .base_parser import BaseContentParser, ContentParseResult


class PDFParser(BaseContentParser):

    def __init__(self):
        self.max_file_size = 10 * 1024 * 1024  # 10MB limit

    async def parse(self, source: str, **kwargs) -> ContentParseResult:
        try:
            if not os.path.exists(source):
                return ContentParseResult("", error=f"PDF file not found: {source}")

            file_size = os.path.getsize(source)
            if file_size > self.max_file_size:
                return ContentParseResult(
                    "",
                    error=f"PDF file too large: {file_size} bytes (max: {self.max_file_size})"
                )

            try:
                content, metadata = await self._parse_with_pdfplumber(source)
            except Exception as e:
                content, metadata = await self._parse_with_pypdf2(source)

            if not content.strip():
                return ContentParseResult("", error="No text content found in PDF")

            return ContentParseResult(
                content=content.strip(),
                title=metadata.get("title"),
                metadata=metadata
            )

        except Exception as e:
            return ContentParseResult("", error=f"Failed to parse PDF: {str(e)}")

    async def _parse_with_pdfplumber(self, file_path: str) -> tuple[str, Dict[str, Any]]:
        content_parts = []
        metadata = {}

        with pdfplumber.open(file_path) as pdf:
            # Extract metadata
            if pdf.metadata:
                metadata.update({
                    "title": pdf.metadata.get("Title"),
                    "author": pdf.metadata.get("Author"),
                    "creator": pdf.metadata.get("Creator"),
                    "producer": pdf.metadata.get("Producer"),
                    "subject": pdf.metadata.get("Subject"),
                })

            metadata["page_count"] = len(pdf.pages)
            for page_num, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text()
                if page_text:
                    content_parts.append(f"--- Page {page_num} ---\n{page_text}")

        return "\n\n".join(content_parts), metadata

    async def _parse_with_pypdf2(self, file_path: str) -> tuple[str, Dict[str, Any]]:
        content_parts = []
        metadata = {}

        with open(file_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)

            if pdf_reader.metadata:
                metadata.update({
                    "title": pdf_reader.metadata.get("/Title"),
                    "author": pdf_reader.metadata.get("/Author"),
                    "creator": pdf_reader.metadata.get("/Creator"),
                    "producer": pdf_reader.metadata.get("/Producer"),
                    "subject": pdf_reader.metadata.get("/Subject"),
                })

            metadata["page_count"] = len(pdf_reader.pages)

            for page_num, page in enumerate(pdf_reader.pages, 1):
                page_text = page.extract_text()
                if page_text:
                    content_parts.append(f"--- Page {page_num} ---\n{page_text}")

        return "\n\n".join(content_parts), metadata

    def supports_source(self, source: str) -> bool:
        return source.lower().endswith(".pdf")

    @property
    def supported_types(self) -> list[str]:
        return ["pdf"]