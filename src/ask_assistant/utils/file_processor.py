"""File processing utilities for Ask Assistant"""

import os
import tempfile
from typing import Dict, List, Optional, Union
from pathlib import Path
import logging

from fastapi import UploadFile
import aiofiles

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

logger = logging.getLogger(__name__)

class FileProcessorError(Exception):
    """Custom exception for file processing errors"""
    pass

class FileProcessor:
    """Handles file upload and content extraction for various file types"""

    # Supported file types and their MIME types
    SUPPORTED_TYPES = {
        'pdf': ['application/pdf'],
        'docx': ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
        'txt': ['text/plain'],
        'png': ['image/png'],
        'jpg': ['image/jpeg'],
        'jpeg': ['image/jpeg']
    }

    # Maximum file size (10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024

    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()

    async def process_files(self, files: List[UploadFile]) -> List[Dict[str, Union[str, int]]]:
        """
        Process multiple uploaded files and extract their content

        Args:
            files: List of uploaded files

        Returns:
            List of file processing results with content, filename, type, and size
        """
        results = []

        for file in files:
            try:
                result = await self.process_single_file(file)
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing file {file.filename}: {str(e)}")
                results.append({
                    'filename': file.filename,
                    'type': 'error',
                    'content': f"Error processing file: {str(e)}",
                    'size': 0
                })

        return results

    async def process_single_file(self, file: UploadFile) -> Dict[str, Union[str, int]]:
        """
        Process a single uploaded file and extract its content

        Args:
            file: Uploaded file

        Returns:
            Dictionary with file content, metadata
        """
        # Validate file
        self.validate_file(file)

        # Read file content
        content = await file.read()
        file_size = len(content)

        # Reset file position for potential re-reading
        await file.seek(0)

        # Save temporarily for processing
        temp_file_path = os.path.join(self.temp_dir, file.filename)

        async with aiofiles.open(temp_file_path, 'wb') as temp_file:
            await temp_file.write(content)

        try:
            # Extract text content based on file type
            file_extension = Path(file.filename).suffix.lower().lstrip('.')

            if file_extension == 'pdf':
                text_content = await self.extract_pdf_text(temp_file_path)
            elif file_extension == 'docx':
                text_content = await self.extract_docx_text(temp_file_path)
            elif file_extension == 'txt':
                text_content = await self.extract_txt_text(temp_file_path)
            elif file_extension in ['png', 'jpg', 'jpeg']:
                text_content = await self.extract_image_text(temp_file_path)
            else:
                raise FileProcessorError(f"Unsupported file type: {file_extension}")

            return {
                'filename': file.filename,
                'type': file_extension,
                'content': text_content,
                'size': file_size
            }

        finally:
            # Clean up temporary file
            try:
                os.remove(temp_file_path)
            except OSError:
                pass

    def validate_file(self, file: UploadFile) -> None:
        """
        Validate uploaded file for type and size constraints

        Args:
            file: Uploaded file to validate

        Raises:
            FileProcessorError: If file validation fails
        """
        # Check file size
        if hasattr(file, 'size') and file.size and file.size > self.MAX_FILE_SIZE:
            raise FileProcessorError(f"File size {file.size} exceeds maximum allowed size {self.MAX_FILE_SIZE}")

        # Check file extension
        if not file.filename:
            raise FileProcessorError("File must have a filename")

        file_extension = Path(file.filename).suffix.lower().lstrip('.')
        if not file_extension:
            raise FileProcessorError("File must have an extension")

        # Check if file type is supported
        is_supported = False
        for supported_ext, mime_types in self.SUPPORTED_TYPES.items():
            if file_extension == supported_ext:
                is_supported = True
                break

        if not is_supported:
            supported_extensions = list(self.SUPPORTED_TYPES.keys())
            raise FileProcessorError(f"Unsupported file type: {file_extension}. Supported types: {supported_extensions}")

        # Check MIME type if available
        if file.content_type:
            is_valid_mime = False
            for supported_ext, mime_types in self.SUPPORTED_TYPES.items():
                if file_extension == supported_ext and file.content_type in mime_types:
                    is_valid_mime = True
                    break

            if not is_valid_mime:
                logger.warning(f"MIME type {file.content_type} doesn't match extension {file_extension}")

    async def extract_pdf_text(self, file_path: str) -> str:
        """Extract text from PDF file"""
        if not HAS_PDF:
            raise FileProcessorError("PDF processing not available. Install PyPDF2 and pdfplumber")

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

                return "\n\n".join(text_parts) if text_parts else "No text could be extracted from PDF"

        except Exception as e:
            raise FileProcessorError(f"Failed to extract text from PDF: {str(e)}")

    async def extract_docx_text(self, file_path: str) -> str:
        """Extract text from DOCX file"""
        if not HAS_DOCX:
            raise FileProcessorError("DOCX processing not available. Install python-docx")

        try:
            doc = Document(file_path)
            text_parts = []

            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_parts.append(paragraph.text)

            return "\n\n".join(text_parts) if text_parts else "No text found in document"

        except Exception as e:
            raise FileProcessorError(f"Failed to extract text from DOCX: {str(e)}")

    async def extract_txt_text(self, file_path: str) -> str:
        """Extract text from TXT file"""
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as file:
                content = await file.read()
                return content.strip()

        except UnicodeDecodeError:
            # Try with different encoding
            try:
                async with aiofiles.open(file_path, 'r', encoding='latin1') as file:
                    content = await file.read()
                    return content.strip()
            except Exception as e:
                raise FileProcessorError(f"Failed to read text file: {str(e)}")

        except Exception as e:
            raise FileProcessorError(f"Failed to extract text from TXT: {str(e)}")

    async def extract_image_text(self, file_path: str) -> str:
        """Extract text from image using OCR"""
        if not HAS_OCR:
            return f"[Image: {Path(file_path).name}] - OCR not available. Install pytesseract and PIL for text extraction."

        try:
            image = Image.open(file_path)

            # Perform OCR
            text = pytesseract.image_to_string(image)

            if text.strip():
                return f"[Text extracted from image: {Path(file_path).name}]\n\n{text.strip()}"
            else:
                return f"[Image: {Path(file_path).name}] - No text detected in image"

        except Exception as e:
            return f"[Image: {Path(file_path).name}] - Error extracting text: {str(e)}"

    def cleanup(self):
        """Clean up temporary directory"""
        try:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass

    def __del__(self):
        """Cleanup on deletion"""
        self.cleanup()


def format_file_content_for_prompt(file_results: List[Dict[str, Union[str, int]]]) -> str:
    """
    Format extracted file content for inclusion in agent prompt

    Args:
        file_results: List of file processing results

    Returns:
        Formatted string for prompt inclusion
    """
    if not file_results:
        return ""

    formatted_parts = ["## Uploaded Files Content\n"]

    for result in file_results:
        filename = result.get('filename', 'Unknown')
        file_type = result.get('type', 'unknown')
        content = result.get('content', '')

        if file_type == 'error':
            formatted_parts.append(f"### {filename} (Error)\n{content}\n")
        else:
            # Truncate very long content
            if len(content) > 3000:
                content = content[:3000] + "\n... [Content truncated]"

            formatted_parts.append(f"### {filename} ({file_type.upper()})\n```\n{content}\n```\n")

    return "\n".join(formatted_parts)