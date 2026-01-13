"""File content extraction utilities for agent processing - leverages existing FileStorageService"""

import os
from typing import Dict, List, Optional, Union
from pathlib import Path
import logging

from fastapi import UploadFile

# Document processing
try:
    import PyPDF2
    import pdfplumber
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

try:
    from docx import Document
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

# Image processing
try:
    import pytesseract
    from PIL import Image
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

from ...api.v1.constants import RAGIndexingStatus

logger = logging.getLogger(__name__)

class FileContentExtractionError(Exception):
    """Custom exception for file content extraction errors"""
    pass

class AgentFileProcessor:
    """
    Processes files for agent consumption using existing FileStorageService
    Skips GCS/RAG integration and extracts content directly for agent context
    """

    def __init__(self, file_storage_service):
        self.file_storage = file_storage_service

    async def process_files_for_agent(self, files: List[UploadFile]) -> Dict[str, Union[List[str], List[Dict]]]:
        """
        Process uploaded files for direct agent consumption

        Args:
            files: List of uploaded files

        Returns:
            Dict with:
                - file_ids: List of stored file IDs
                - content: List of extracted content dicts
                - formatted_content: Formatted string for agent prompt
        """
        if not files:
            return {
                "file_ids": [],
                "content": [],
                "formatted_content": ""
            }

        file_ids = []
        extracted_content = []

        for file in files:
            try:
                # Store file using existing service (skip RAG indexing)
                file_id = await self.file_storage.store_file(
                    file=file,
                    ttl_hours=24,  # Files expire after 24 hours
                    indexing_status=RAGIndexingStatus.AGENT_PROCESSING  # Custom status for agents
                )
                file_ids.append(file_id)

                # Extract content from stored file
                content_result = await self.extract_file_content(file_id)
                extracted_content.append(content_result)

                # Reset file position for potential reuse
                await file.seek(0)

            except Exception as e:
                logger.error(f"Error processing file {file.filename}: {str(e)}")
                extracted_content.append({
                    'filename': file.filename,
                    'type': 'error',
                    'content': f"Error processing file: {str(e)}",
                    'size': 0,
                    'file_id': None
                })

        # Format all content for agent prompt
        formatted_content = self.format_content_for_prompt(extracted_content)

        return {
            "file_ids": file_ids,
            "content": extracted_content,
            "formatted_content": formatted_content
        }

    async def extract_file_content(self, file_id: str) -> Dict[str, Union[str, int]]:
        """
        Extract content from a stored file

        Args:
            file_id: ID of stored file

        Returns:
            Dict with extracted content and metadata
        """
        # Get file metadata from existing service
        file_metadata = self.file_storage.get_file_metadata(file_id)
        if not file_metadata:
            raise FileContentExtractionError(f"File with ID {file_id} not found")

        # Get local file path
        local_file_path = self.file_storage.get_file_path(file_id)
        if not local_file_path or not os.path.exists(local_file_path):
            raise FileContentExtractionError(f"File content not accessible for {file_id}")

        # Extract content based on file extension
        file_extension = Path(file_metadata.filename).suffix.lower().lstrip('.')

        try:
            if file_extension == 'pdf':
                content = self.extract_pdf_content(local_file_path)
            elif file_extension in ['docx', 'doc']:
                content = self.extract_docx_content(local_file_path)
            elif file_extension == 'txt':
                content = self.extract_txt_content(local_file_path)
            elif file_extension in ['png', 'jpg', 'jpeg']:
                content = self.extract_image_content(local_file_path)
            else:
                content = f"[Unsupported file type: {file_extension}]"

            return {
                'filename': file_metadata.filename,
                'type': file_extension,
                'content': content,
                'size': file_metadata.file_size,
                'file_id': file_id
            }

        except Exception as e:
            logger.error(f"Content extraction failed for {file_id}: {str(e)}")
            return {
                'filename': file_metadata.filename,
                'type': file_extension,
                'content': f"[Content extraction failed: {str(e)}]",
                'size': file_metadata.file_size,
                'file_id': file_id
            }

    def extract_pdf_content(self, file_path: str) -> str:
        """Extract text from PDF file"""
        if not HAS_PDF:
            return "[PDF processing not available - install PyPDF2 and pdfplumber]"

        try:
            # Try pdfplumber first (better for complex layouts)
            with pdfplumber.open(file_path) as pdf:
                text_parts = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)

                if text_parts:
                    return "\n\n".join(text_parts)

        except Exception as e:
            logger.warning(f"pdfplumber failed for {file_path}: {e}, trying PyPDF2")

        try:
            # Fallback to PyPDF2
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text_parts = []

                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)

                return "\n\n".join(text_parts) if text_parts else "[No text could be extracted from PDF]"

        except Exception as e:
            return f"[PDF extraction failed: {str(e)}]"

    def extract_docx_content(self, file_path: str) -> str:
        """Extract text from DOCX file"""
        if not HAS_DOCX:
            return "[DOCX processing not available - install python-docx]"

        try:
            doc = Document(file_path)
            text_parts = []

            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_parts.append(paragraph.text)

            return "\n\n".join(text_parts) if text_parts else "[No text found in document]"

        except Exception as e:
            return f"[DOCX extraction failed: {str(e)}]"

    def extract_txt_content(self, file_path: str) -> str:
        """Extract text from TXT file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                return content.strip()

        except UnicodeDecodeError:
            try:
                # Try with different encoding
                with open(file_path, 'r', encoding='latin1') as file:
                    content = file.read()
                    return content.strip()
            except Exception as e:
                return f"[Text file reading failed: {str(e)}]"

        except Exception as e:
            return f"[Text extraction failed: {str(e)}]"

    def extract_image_content(self, file_path: str) -> str:
        """Extract text from image using OCR"""
        filename = Path(file_path).name

        if not HAS_OCR:
            return f"[Image: {filename}] - OCR not available. Install pytesseract and PIL for text extraction."

        try:
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image)

            if text.strip():
                return f"[OCR from {filename}]\n\n{text.strip()}"
            else:
                return f"[Image: {filename}] - No text detected"

        except Exception as e:
            return f"[Image: {filename}] - OCR failed: {str(e)}"

    def format_content_for_prompt(self, content_results: List[Dict]) -> str:
        """
        Format extracted file contents for agent prompt inclusion

        Args:
            content_results: List of content extraction results

        Returns:
            Formatted string ready for prompt inclusion
        """
        if not content_results:
            return ""

        formatted_parts = ["## Uploaded Files Analysis\n"]

        for result in content_results:
            filename = result.get('filename', 'Unknown')
            file_type = result.get('type', 'unknown')
            content = result.get('content', '')
            file_id = result.get('file_id', 'N/A')

            # Truncate very long content to avoid context limits
            if len(content) > 3000:
                content = content[:3000] + "\n\n[Content truncated - file continues...]"

            formatted_parts.append(f"### 📄 {filename} ({file_type.upper()})")
            formatted_parts.append(f"**File ID:** {file_id}")
            formatted_parts.append(f"```\n{content}\n```\n")

        return "\n".join(formatted_parts)

    def cleanup_agent_files(self, file_ids: List[str]) -> int:
        """
        Clean up temporary files created for agent processing

        Args:
            file_ids: List of file IDs to clean up

        Returns:
            Number of files successfully cleaned
        """
        cleaned_count = 0
        for file_id in file_ids:
            try:
                if self.file_storage.delete_file(file_id):
                    cleaned_count += 1
            except Exception as e:
                logger.error(f"Failed to cleanup file {file_id}: {e}")

        return cleaned_count


def get_agent_file_processor(file_storage_service) -> AgentFileProcessor:
    """
    Factory function to create AgentFileProcessor with existing FileStorageService

    Args:
        file_storage_service: Existing FileStorageService instance

    Returns:
        Configured AgentFileProcessor
    """
    return AgentFileProcessor(file_storage_service)