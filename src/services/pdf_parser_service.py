"""
PDF Parser Service for PYQ System

Handles downloading and parsing PDF question papers from URLs.
Uses PyMuPDF (fitz) for PDF text extraction and AI for question extraction.
"""

import tempfile
import structlog
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx
import fitz  # PyMuPDF
from datetime import datetime

from ..exceptions import ParkhoError
from ..config import get_settings
from ..services.llm_client import LlmClient


logger = structlog.get_logger(__name__)


class PDFParserService:
    """Service for parsing PDF question papers"""

    def __init__(self):
        self.settings = get_settings()
        self.llm_client = LlmClient()
        self.max_pdf_size_mb = 50

    async def download_pdf_from_url(self, url: str) -> Path:
        """
        Download PDF from URL to temporary file.
        
        Args:
            url: URL of the PDF file
            
        Returns:
            Path to downloaded temporary file
            
        Raises:
            ParkhoError: If download fails or file is too large
        """
        try:
            logger.info("Downloading PDF from URL", url=url)
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
                
                # Check content type
                content_type = response.headers.get("content-type", "")
                if "pdf" not in content_type.lower():
                    logger.warning("URL may not be a PDF", content_type=content_type, url=url)
                
                # Check file size
                content_length = len(response.content)
                size_mb = content_length / (1024 * 1024)
                
                if size_mb > self.max_pdf_size_mb:
                    raise ParkhoError(
                        f"PDF file too large: {size_mb:.2f}MB (max: {self.max_pdf_size_mb}MB)"
                    )
                
                # Save to temporary file
                temp_file = tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=".pdf",
                    prefix="pyq_"
                )
                temp_file.write(response.content)
                temp_file.close()
                
                temp_path = Path(temp_file.name)
                logger.info(
                    "PDF downloaded successfully",
                    path=str(temp_path),
                    size_mb=f"{size_mb:.2f}"
                )
                
                return temp_path
                
        except httpx.HTTPError as e:
            logger.error("Failed to download PDF", error=str(e), url=url)
            raise ParkhoError(f"Failed to download PDF from URL: {str(e)}")
        except Exception as e:
            logger.error("Unexpected error downloading PDF", error=str(e), url=url)
            raise ParkhoError(f"Unexpected error downloading PDF: {str(e)}")

    def extract_text_from_pdf(self, pdf_path: Path) -> str:
        """
        Extract text from PDF using PyMuPDF.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Extracted text content
            
        Raises:
            ParkhoError: If PDF extraction fails
        """
        try:
            logger.info("Extracting text from PDF", path=str(pdf_path))
            
            doc = fitz.open(pdf_path)
            text_parts = []
            
            for page_num, page in enumerate(doc, start=1):
                page_text = page.get_text()
                if page_text.strip():
                    text_parts.append(f"--- Page {page_num} ---\n{page_text}")
            
            doc.close()
            
            full_text = "\n\n".join(text_parts)
            
            logger.info(
                "Text extracted successfully",
                pages=len(text_parts),
                characters=len(full_text)
            )
            
            return full_text
            
        except Exception as e:
            logger.error("Failed to extract text from PDF", error=str(e), path=str(pdf_path))
            raise ParkhoError(f"Failed to extract text from PDF: {str(e)}")

    async def extract_questions_from_text(
        self,
        text: str,
        exam_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract structured questions from PDF text using AI.
        
        Args:
            text: Extracted PDF text
            exam_metadata: Optional metadata about the exam (title, year, etc.)
            
        Returns:
            List of structured question dictionaries
            
        Raises:
            ParkhoError: If question extraction fails
        """
        try:
            logger.info("Extracting questions from text", text_length=len(text))
            
            # Build prompt for LLM
            metadata_str = ""
            if exam_metadata:
                metadata_str = f"""
Exam Metadata:
- Title: {exam_metadata.get('title', 'Unknown')}
- Year: {exam_metadata.get('year', 'Unknown')}
- Exam Name: {exam_metadata.get('exam_name', 'Unknown')}
"""
            
            prompt = f"""You are an expert at extracting questions from exam papers. 

{metadata_str}

Extract all questions from the following exam paper text and format them as a JSON array.

Each question should have this structure:
{{
  "id": <number>,
  "type": "mcq" | "assertion_reasoning" | "true_false",
  "question_text": "<the question text>",
  "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
  "correct_answer": "<A, B, C, or D>",
  "marks": <number>,
  "explanation": "<optional explanation if provided>"
}}

For assertion-reasoning questions, also include:
{{
  "assertion": "<assertion text>",
  "reason": "<reason text>",
  "options": [
    "A) Both A and R are true and R is the correct explanation of A.",
    "B) Both A and R are true but R is not the correct explanation of A.",
    "C) A is true but R is false.",
    "D) A is false but R is true."
  ]
}}

Guidelines:
1. Extract ONLY the questions, not instructions or metadata
2. Clean up any OCR errors or formatting issues
3. Preserve the original question numbering
4. If correct answers are provided in the text, include them. Otherwise, set to "A"
5. Default marks to 1 if not specified
6. Return ONLY a valid JSON array, no other text

Exam Paper Text:
{text[:15000]}

Return JSON array of questions:"""

            # Call LLM to extract questions
            response = await self.llm_client.generate_content(prompt)
            
            # Parse JSON response
            import json
            import re
            
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find raw JSON array
                json_match = re.search(r'(\[.*\])', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = response
            
            questions = json.loads(json_str)
            
            logger.info(
                "Questions extracted successfully",
                count=len(questions)
            )
            
            return questions
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response as JSON", error=str(e))
            raise ParkhoError("Failed to parse questions from AI response. The response was not valid JSON.")
        except Exception as e:
            logger.error("Failed to extract questions", error=str(e))
            raise ParkhoError(f"Failed to extract questions from text: {str(e)}")

    def format_as_exam_paper(
        self,
        questions: List[Dict[str, Any]],
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Format parsed questions into ExamPaper structure.
        
        Args:
            questions: List of parsed questions
            metadata: Exam metadata (title, year, exam_name, etc.)
            
        Returns:
            Dictionary matching ExamPaper model structure
        """
        total_marks = sum(q.get("marks", 1) for q in questions)
        
        return {
            "title": metadata.get("title", "Parsed Question Paper"),
            "year": metadata.get("year", datetime.now().year),
            "exam_name": metadata.get("exam_name", "General Exam"),
            "time_limit_minutes": metadata.get("time_limit_minutes", 180),
            "total_questions": len(questions),
            "total_marks": total_marks,
            "description": metadata.get("description", f"Parsed from PDF on {datetime.now().strftime('%Y-%m-%d')}"),
            "question_data": {
                "questions": questions,
                "instructions": metadata.get("instructions", "Read all questions carefully before answering."),
                "marking_scheme": metadata.get("marking_scheme", {
                    "positive_marks": 1,
                    "negative_marks": 0,
                    "notes": "No negative marking"
                })
            }
        }

    async def parse_pdf_from_url(
        self,
        url: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Complete workflow: Download PDF, extract text, parse questions, format result.
        
        Args:
            url: URL of the PDF file
            metadata: Optional exam metadata
            
        Returns:
            Formatted exam paper data ready for database
            
        Raises:
            ParkhoError: If any step fails
        """
        pdf_path = None
        
        try:
            # Step 1: Download PDF
            pdf_path = await self.download_pdf_from_url(url)
            
            # Step 2: Extract text
            text = self.extract_text_from_pdf(pdf_path)
            
            if not text.strip():
                raise ParkhoError("No text could be extracted from the PDF")
            
            # Step 3: Extract questions using AI
            questions = await self.extract_questions_from_text(text, metadata)
            
            if not questions:
                raise ParkhoError("No questions could be extracted from the PDF")
            
            # Step 4: Format as exam paper
            exam_paper_data = self.format_as_exam_paper(
                questions,
                metadata or {}
            )
            
            logger.info(
                "PDF parsing completed successfully",
                url=url,
                questions_count=len(questions),
                total_marks=exam_paper_data["total_marks"]
            )
            
            return exam_paper_data
            
        finally:
            # Clean up temporary file
            if pdf_path and pdf_path.exists():
                try:
                    pdf_path.unlink()
                    logger.debug("Temporary PDF file deleted", path=str(pdf_path))
                except Exception as e:
                    logger.warning("Failed to delete temporary PDF", error=str(e), path=str(pdf_path))


# Singleton instance
_pdf_parser_service: Optional[PDFParserService] = None


def get_pdf_parser_service() -> PDFParserService:
    """Get singleton instance of PDF parser service"""
    global _pdf_parser_service
    if _pdf_parser_service is None:
        _pdf_parser_service = PDFParserService()
    return _pdf_parser_service
