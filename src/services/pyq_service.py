from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import structlog
from datetime import datetime
import json
import re
from pathlib import Path

from ..models.exam_paper import ExamPaper
from ..models.user_attempt import UserAttempt
from ..repositories.exam_paper_repository import ExamPaperRepository
from ..repositories.user_attempt_repository import UserAttemptRepository
from ..exceptions import ParkhoError

logger = structlog.get_logger(__name__)


class PYQService:
    """
    Business logic service for Previous Year Questions (PYQ) system
    """

    def __init__(self, session: Session):
        self.session = session
        self.exam_paper_repo = ExamPaperRepository(session)
        self.user_attempt_repo = UserAttemptRepository(session)

    def get_all_papers(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Get all available exam papers with summary info"""
        try:
            papers = self.exam_paper_repo.get_all_active(limit=limit, offset=offset)
            stats = self.exam_paper_repo.get_paper_summary_stats()

            papers_data = []
            for paper in papers:
                papers_data.append({
                    "id": paper.id,
                    "title": paper.title,
                    "year": paper.year,
                    "exam_name": paper.exam_name,
                    "total_questions": paper.total_questions,
                    "total_marks": paper.total_marks,
                    "time_limit_minutes": paper.time_limit_minutes,
                    "display_name": paper.display_name,
                    "description": paper.description,
                    "created_at": paper.created_at.isoformat() if paper.created_at else None
                })

            return {
                "papers": papers_data,
                "summary": stats,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "total": stats["total_papers"]
                }
            }

        except Exception as e:
            logger.error("Failed to get exam papers", error=str(e), exc_info=e)
            raise ParkhoError(f"Failed to retrieve exam papers: {str(e)}")

    def get_paper_by_id(self, paper_id: int, include_questions: bool = False) -> Dict[str, Any]:
        """Get specific exam paper details"""
        try:
            paper = self.exam_paper_repo.get_by_id(paper_id)
            if not paper:
                raise ParkhoError(f"Exam paper with ID {paper_id} not found")

            paper_data = {
                "id": paper.id,
                "title": paper.title,
                "year": paper.year,
                "exam_name": paper.exam_name,
                "total_questions": paper.total_questions,
                "total_marks": paper.total_marks,
                "time_limit_minutes": paper.time_limit_minutes,
                "display_name": paper.display_name,
                "description": paper.description,
                "created_at": paper.created_at.isoformat() if paper.created_at else None
            }

            if include_questions:
                questions = paper.questions
                if questions:
                    # Remove correct answers from questions for security
                    safe_questions = []
                    for q in questions:
                        safe_q = {k: v for k, v in q.items() if k != "correct_answer"}
                        safe_questions.append(safe_q)
                    paper_data["questions"] = safe_questions
                else:
                    paper_data["questions"] = []

            return paper_data

        except ParkhoError:
            raise
        except Exception as e:
            logger.error("Failed to get exam paper", paper_id=paper_id, error=str(e), exc_info=e)
            raise ParkhoError(f"Failed to retrieve exam paper: {str(e)}")

    def start_exam_attempt(self, paper_id: int, user_identifier: Optional[str] = None) -> Dict[str, Any]:
        """Start a new exam attempt for a user"""
        try:
            # Check if paper exists
            paper = self.exam_paper_repo.get_by_id(paper_id)
            if not paper:
                raise ParkhoError(f"Exam paper with ID {paper_id} not found")

            # Create new attempt
            attempt = self.user_attempt_repo.start_new_attempt(paper_id, user_identifier)

            logger.info("Started new exam attempt", attempt_id=attempt.id, paper_id=paper_id, user=user_identifier)

            return {
                "attempt_id": attempt.id,
                "paper_id": paper_id,
                "paper_title": paper.title,
                "exam_name": paper.exam_name,
                "year": paper.year,
                "total_questions": paper.total_questions,
                "total_marks": paper.total_marks,
                "time_limit_minutes": paper.time_limit_minutes,
                "started_at": attempt.started_at.isoformat() if attempt.started_at else None,
                "questions": self._get_safe_questions(paper)
            }

        except ParkhoError:
            raise
        except Exception as e:
            logger.error("Failed to start exam attempt", paper_id=paper_id, user=user_identifier, error=str(e), exc_info=e)
            raise ParkhoError(f"Failed to start exam attempt: {str(e)}")

    def submit_exam_attempt(self, attempt_id: int, answers: Dict[int, str]) -> Dict[str, Any]:
        """Submit exam answers and calculate score"""
        try:
            # Get attempt with exam paper
            attempt = self.user_attempt_repo.get_by_id(attempt_id)
            if not attempt:
                raise ParkhoError(f"Exam attempt with ID {attempt_id} not found")

            if attempt.is_submitted:
                raise ParkhoError("This attempt has already been submitted")

            paper = attempt.exam_paper
            if not paper:
                raise ParkhoError("Associated exam paper not found")

            # Get correct answers from paper
            correct_answers = paper.get_correct_answers()

            # Submit attempt and calculate score
            attempt.submit_attempt(answers, correct_answers)
            updated_attempt = self.user_attempt_repo.update(attempt)

            # Get detailed results
            questions = paper.questions or []
            detailed_results = updated_attempt.get_detailed_results(questions)

            logger.info(
                "Exam attempt submitted",
                attempt_id=attempt_id,
                score=updated_attempt.score,
                percentage=updated_attempt.percentage,
                time_taken=updated_attempt.time_taken_seconds
            )

            return {
                "attempt_id": attempt_id,
                "submitted": True,
                "score": updated_attempt.score,
                "total_marks": updated_attempt.total_marks,
                "percentage": updated_attempt.percentage,
                "time_taken_seconds": updated_attempt.time_taken_seconds,
                "display_time": updated_attempt.display_time_taken,
                "submitted_at": updated_attempt.submitted_at.isoformat() if updated_attempt.submitted_at else None,
                "paper_info": {
                    "id": paper.id,
                    "title": paper.title,
                    "exam_name": paper.exam_name,
                    "year": paper.year
                },
                "detailed_results": detailed_results
            }

        except ParkhoError:
            raise
        except Exception as e:
            logger.error("Failed to submit exam attempt", attempt_id=attempt_id, error=str(e), exc_info=e)
            raise ParkhoError(f"Failed to submit exam attempt: {str(e)}")

    def get_attempt_results(self, attempt_id: int) -> Dict[str, Any]:
        """Get detailed results for a completed attempt"""
        try:
            attempt = self.user_attempt_repo.get_by_id(attempt_id)
            if not attempt:
                raise ParkhoError(f"Exam attempt with ID {attempt_id} not found")

            if not attempt.is_submitted:
                raise ParkhoError("This attempt has not been submitted yet")

            paper = attempt.exam_paper
            if not paper:
                raise ParkhoError("Associated exam paper not found")

            questions = paper.questions or []
            detailed_results = attempt.get_detailed_results(questions)

            return {
                "attempt_id": attempt_id,
                "score": attempt.score,
                "total_marks": attempt.total_marks,
                "percentage": attempt.percentage,
                "time_taken_seconds": attempt.time_taken_seconds,
                "display_time": attempt.display_time_taken,
                "started_at": attempt.started_at.isoformat() if attempt.started_at else None,
                "submitted_at": attempt.submitted_at.isoformat() if attempt.submitted_at else None,
                "paper_info": {
                    "id": paper.id,
                    "title": paper.title,
                    "exam_name": paper.exam_name,
                    "year": paper.year
                },
                "detailed_results": detailed_results
            }

        except ParkhoError:
            raise
        except Exception as e:
            logger.error("Failed to get attempt results", attempt_id=attempt_id, error=str(e), exc_info=e)
            raise ParkhoError(f"Failed to retrieve attempt results: {str(e)}")

    def get_user_attempt_history(
        self,
        user_identifier: str,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get user's exam attempt history"""
        try:
            attempts = self.user_attempt_repo.get_user_attempts(user_identifier, limit, offset)
            performance_stats = self.user_attempt_repo.get_user_performance_stats(user_identifier)

            attempts_data = []
            for attempt in attempts:
                attempts_data.append({
                    "attempt_id": attempt.id,
                    "paper_id": attempt.paper_id,
                    "paper_title": attempt.exam_paper.title if attempt.exam_paper else "Unknown",
                    "exam_name": attempt.exam_paper.exam_name if attempt.exam_paper else "Unknown",
                    "year": attempt.exam_paper.year if attempt.exam_paper else None,
                    "score": attempt.score,
                    "total_marks": attempt.total_marks,
                    "percentage": attempt.percentage,
                    "time_taken_seconds": attempt.time_taken_seconds,
                    "display_time": attempt.display_time_taken,
                    "is_completed": attempt.is_completed,
                    "started_at": attempt.started_at.isoformat() if attempt.started_at else None,
                    "submitted_at": attempt.submitted_at.isoformat() if attempt.submitted_at else None
                })

            return {
                "attempts": attempts_data,
                "performance_stats": performance_stats,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "total": performance_stats["total_attempts"]
                }
            }

        except Exception as e:
            logger.error("Failed to get user attempt history", user=user_identifier, error=str(e), exc_info=e)
            raise ParkhoError(f"Failed to retrieve attempt history: {str(e)}")

    def get_paper_performance_stats(self, paper_id: int) -> Dict[str, Any]:
        """Get performance statistics for a specific paper"""
        try:
            paper = self.exam_paper_repo.get_by_id(paper_id)
            if not paper:
                raise ParkhoError(f"Exam paper with ID {paper_id} not found")

            stats = self.user_attempt_repo.get_paper_performance_stats(paper_id)

            return {
                "paper_id": paper_id,
                "paper_title": paper.title,
                "exam_name": paper.exam_name,
                "year": paper.year,
                "statistics": stats
            }

        except ParkhoError:
            raise
        except Exception as e:
            logger.error("Failed to get paper performance stats", paper_id=paper_id, error=str(e), exc_info=e)
            raise ParkhoError(f"Failed to retrieve performance statistics: {str(e)}")

    def search_papers(self, search_term: str) -> List[Dict[str, Any]]:
        """Search exam papers by title or exam name"""
        try:
            papers = self.exam_paper_repo.search_papers(search_term)

            papers_data = []
            for paper in papers:
                papers_data.append({
                    "id": paper.id,
                    "title": paper.title,
                    "year": paper.year,
                    "exam_name": paper.exam_name,
                    "total_questions": paper.total_questions,
                    "total_marks": paper.total_marks,
                    "time_limit_minutes": paper.time_limit_minutes,
                    "display_name": paper.display_name,
                    "description": paper.description
                })

            return papers_data

        except Exception as e:
            logger.error("Failed to search papers", search_term=search_term, error=str(e), exc_info=e)
            raise ParkhoError(f"Failed to search papers: {str(e)}")

    def get_available_filters(self) -> Dict[str, Any]:
        """Get available filter options (years, exam names)"""
        try:
            return {
                "years": self.exam_paper_repo.get_years_available(),
                "exam_names": self.exam_paper_repo.get_exam_names_available()
            }

        except Exception as e:
            logger.error("Failed to get filter options", error=str(e), exc_info=e)
            raise ParkhoError(f"Failed to retrieve filter options: {str(e)}")

    def _get_safe_questions(self, paper: ExamPaper) -> List[Dict[str, Any]]:
        """Get questions without correct answers for exam taking"""
        questions = paper.questions or []
        safe_questions = []

        for q in questions:
            # Remove correct_answer and any solution-related fields
            safe_q = {k: v for k, v in q.items() if k not in ["correct_answer", "explanation", "solution"]}
            safe_questions.append(safe_q)

        return safe_questions

    async def parse_pdf_from_url(
        self,
        url: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Parse PDF from URL and return structured exam paper data.
        
        Args:
            url: URL of the PDF file
            metadata: Optional metadata (title, year, exam_name, etc.)
            
        Returns:
            Dictionary with parsed exam paper data
            
        Raises:
            ParkhoError: If parsing fails
        """
        try:
            from ..services.pdf_parser_service import get_pdf_parser_service
            
            logger.info("Parsing PDF from URL", url=url)
            
            pdf_parser = get_pdf_parser_service()
            result = await pdf_parser.parse_pdf_from_url(url, metadata)
            
            logger.info(
                "PDF parsing successful",
                url=url,
                questions=result.get("total_questions", 0)
            )
            
            return result
            
        except Exception as e:
            logger.error("Failed to parse PDF", url=url, error=str(e), exc_info=e)
            raise ParkhoError(f"Failed to parse PDF: {str(e)}")

    async def import_paper_from_pdf(
        self,
        url: str,
        metadata: Optional[Dict[str, Any]] = None,
        activate: bool = True
    ) -> Dict[str, Any]:
        """
        Parse PDF and import it as an exam paper into the database.
        
        Args:
            url: URL of the PDF file
            metadata: Optional metadata (title, year, exam_name, etc.)
            activate: Whether to activate the paper immediately
            
        Returns:
            Dictionary with imported paper information
            
        Raises:
            ParkhoError: If import fails
        """
        try:
            logger.info("Importing paper from PDF", url=url, activate=activate)
            
            # Step 1: Parse PDF
            parsed_data = await self.parse_pdf_from_url(url, metadata)
            
            # Step 2: Validate parsed data
            self.validate_parsed_paper(parsed_data)
            
            # Step 3: Create ExamPaper instance
            import json
            exam_paper = ExamPaper(
                title=parsed_data["title"],
                year=parsed_data["year"],
                exam_name=parsed_data["exam_name"],
                total_questions=parsed_data["total_questions"],
                total_marks=parsed_data["total_marks"],
                time_limit_minutes=parsed_data["time_limit_minutes"],
                description=parsed_data.get("description"),
                is_active=activate,
                question_data=json.dumps(parsed_data["question_data"])  # Convert dict to JSON string
            )
            
            # Step 4: Save to database
            created_paper = self.exam_paper_repo.create(exam_paper)
            
            logger.info(
                "Paper imported successfully",
                paper_id=created_paper.id,
                title=created_paper.title,
                questions=created_paper.total_questions
            )
            
            return {
                "success": True,
                "paper_id": created_paper.id,
                "title": created_paper.title,
                "questions_imported": created_paper.total_questions,
                "total_marks": created_paper.total_marks,
                "activated": created_paper.is_active
            }
            
        except ParkhoError:
            raise
        except Exception as e:
            logger.error("Failed to import paper from PDF", url=url, error=str(e), exc_info=e)
            raise ParkhoError(f"Failed to import paper: {str(e)}")

    def validate_parsed_paper(self, paper_data: Dict[str, Any]) -> None:
        """
        Validate parsed paper data structure.
        
        Args:
            paper_data: Parsed exam paper data
            
        Raises:
            ParkhoError: If validation fails
        """
        required_fields = ["title", "year", "exam_name", "total_questions", "total_marks", "question_data"]
        
        for field in required_fields:
            if field not in paper_data:
                raise ParkhoError(f"Missing required field: {field}")
        
        # Validate question_data structure
        question_data = paper_data.get("question_data", {})
        if not isinstance(question_data, dict):
            raise ParkhoError("question_data must be a dictionary")
        
        questions = question_data.get("questions", [])
        if not isinstance(questions, list):
            raise ParkhoError("questions must be a list")
        
        if len(questions) == 0:
            raise ParkhoError("No questions found in parsed data")
        
        # Validate each question has required fields
        for i, question in enumerate(questions):
            if not isinstance(question, dict):
                raise ParkhoError(f"Question {i+1} is not a dictionary")
            
            required_q_fields = ["id", "type", "question_text", "options", "correct_answer"]
            for field in required_q_fields:
                if field not in question:
                    raise ParkhoError(f"Question {i+1} missing required field: {field}")
        
        logger.debug("Paper data validation successful", questions_count=len(questions))

    # =============================================================================
    # FOLDER-BASED PAPER DISCOVERY (Auto-discovery from pyq_json folder)
    # =============================================================================

    def scan_papers_from_folder(self, exam_type: str) -> List[Dict[str, Any]]:
        """
        Scan papers from pyq_json/{exam_type}/ folder structure.

        Args:
            exam_type: "UGC_NET" or "MPSET"

        Returns:
            List of paper metadata dictionaries
        """
        try:
            folder_path = Path(f"pyq_json/{exam_type}")

            if not folder_path.exists():
                logger.warning(f"Papers folder does not exist: {folder_path}")
                return []

            papers = []

            for json_file in folder_path.glob("*.json"):
                try:
                    # Validate and extract metadata from JSON file
                    paper_metadata = self._extract_paper_metadata(json_file, exam_type)
                    if paper_metadata:
                        papers.append(paper_metadata)

                except Exception as e:
                    logger.error(f"Failed to process file {json_file}: {e}")
                    continue

            # Sort by year (descending) then by filename - handle None years properly
            papers.sort(key=lambda x: (x.get('year') or 0, x['filename']), reverse=True)

            logger.info(f"Scanned papers from folder",
                       exam_type=exam_type,
                       papers_found=len(papers))

            return papers

        except Exception as e:
            logger.error(f"Failed to scan papers from folder: {e}", exc_info=e)
            raise ParkhoError(f"Failed to scan papers for {exam_type}: {str(e)}")

    def _extract_paper_metadata(self, json_file: Path, exam_type: str) -> Optional[Dict[str, Any]]:
        """
        Extract metadata from a JSON paper file.

        Args:
            json_file: Path to the JSON file
            exam_type: Type of exam (UGC_NET, MPSET)

        Returns:
            Dictionary with paper metadata
        """
        try:
            # Load and validate JSON structure
            with open(json_file, 'r', encoding='utf-8') as f:
                questions_data = json.load(f)

            # Validate it's a list of questions
            if not isinstance(questions_data, list):
                logger.error(f"Invalid JSON structure in {json_file}: expected list")
                return None

            if not questions_data:
                logger.warning(f"Empty questions list in {json_file}")
                return None

            # Validate first question structure
            sample_question = questions_data[0]
            required_fields = ["id", "type", "question", "options", "correct_answer"]
            missing_fields = [field for field in required_fields if field not in sample_question]

            if missing_fields:
                logger.error(f"Invalid question structure in {json_file}: missing {missing_fields}")
                return None

            # Extract metadata
            filename = json_file.name
            file_stat = json_file.stat()

            # Smart metadata extraction
            year = self._extract_year_from_filename(filename)
            title = self._generate_title_from_filename(filename, exam_type)
            subject = self._extract_subject_from_filename(filename)

            # Analyze question types
            question_types = self._analyze_question_types(questions_data)

            metadata = {
                "filename": filename,
                "file_path": str(json_file),
                "exam_type": exam_type,
                "title": title,
                "year": year,
                "subject": subject,
                "total_questions": len(questions_data),
                "total_marks": len(questions_data),  # Assume 1 mark per question
                "time_limit_minutes": 180,  # Default 3 hours
                "display_name": title,
                "description": f"{exam_type} {subject} paper with {len(questions_data)} questions",
                "question_types": question_types,
                "file_size": file_stat.st_size,
                "last_modified": datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                "is_valid": True,
                "created_at": datetime.fromtimestamp(file_stat.st_mtime).isoformat()
            }

            logger.debug(f"Extracted metadata from {filename}",
                        title=title, year=year, questions=len(questions_data))

            return metadata

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {json_file}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to extract metadata from {json_file}: {e}")
            return None

    def _extract_year_from_filename(self, filename: str) -> Optional[int]:
        """Extract year from filename like 'ugc-net-paper-ii-december-2024-law'"""
        year_match = re.search(r'20\d{2}', filename)
        return int(year_match.group()) if year_match else None

    def _generate_title_from_filename(self, filename: str, exam_type: str) -> str:
        """Generate a readable title from filename"""
        # Remove extension and clean up
        name = Path(filename).stem
        title = name.replace('-', ' ').replace('_', ' ')

        # Capitalize words
        title = ' '.join(word.capitalize() for word in title.split())

        # Clean up common patterns
        title = title.replace('Ugc Net', 'UGC NET')
        title = title.replace('Mpset', 'MPSET')
        title = title.replace('Paper Ii', 'Paper II')
        title = title.replace('Paper I ', 'Paper I ')
        title = title.replace('Solved Paper', '')

        return title.strip()

    def _extract_subject_from_filename(self, filename: str) -> str:
        """Extract subject from filename"""
        filename_lower = filename.lower()

        if 'law' in filename_lower:
            return 'Law'
        elif 'teaching' in filename_lower or 'research' in filename_lower:
            return 'Teaching & Research Aptitude'
        elif 'general' in filename_lower:
            return 'General'
        elif 'english' in filename_lower:
            return 'English'
        elif 'hindi' in filename_lower:
            return 'Hindi'
        elif 'computer' in filename_lower:
            return 'Computer Science'
        else:
            return 'General'

    def _analyze_question_types(self, questions_data: List[Dict]) -> Dict[str, int]:
        """Analyze distribution of question types"""
        types_count = {}

        for question in questions_data:
            q_type = question.get('type', 'standard')
            types_count[q_type] = types_count.get(q_type, 0) + 1

        return types_count

    def load_paper_from_file(self, exam_type: str, filename: str, include_answers: bool = False) -> Dict[str, Any]:
        """
        Load full paper content from JSON file.

        Args:
            exam_type: "UGC_NET" or "MPSET"
            filename: JSON filename
            include_answers: Whether to include correct answers

        Returns:
            Complete paper data with questions
        """
        try:
            file_path = Path(f"pyq_json/{exam_type}/{filename}")

            if not file_path.exists():
                raise ParkhoError(f"Paper file not found: {file_path}")

            # Get metadata
            metadata = self._extract_paper_metadata(file_path, exam_type)
            if not metadata:
                raise ParkhoError(f"Invalid paper file: {filename}")

            # Load questions
            with open(file_path, 'r', encoding='utf-8') as f:
                questions = json.load(f)

            # Process questions based on include_answers parameter
            if not include_answers:
                # Remove correct answers for exam mode
                processed_questions = []
                for question in questions:
                    q_copy = question.copy()
                    q_copy.pop("correct_answer", None)
                    processed_questions.append(q_copy)
                questions = processed_questions

            paper_data = {
                "metadata": metadata,
                "questions": questions,
                "total_questions": len(questions),
                "answers_included": include_answers,
                "loaded_at": datetime.now().isoformat()
            }

            logger.info(f"Loaded paper from file",
                       exam_type=exam_type,
                       filename=filename,
                       questions=len(questions),
                       answers_included=include_answers)

            return paper_data

        except ParkhoError:
            raise
        except Exception as e:
            logger.error(f"Failed to load paper from file: {e}", exc_info=e)
            raise ParkhoError(f"Failed to load paper {filename}: {str(e)}")

    def get_folder_based_papers_summary(self) -> Dict[str, Any]:
        """
        Get summary of all papers available in pyq_json folders.

        Returns:
            Summary with papers organized by exam type
        """
        try:
            exam_types = ["UGC_NET", "MPSET"]
            summary = {
                "exam_types": {},
                "totals": {
                    "total_exam_types": 0,
                    "total_papers": 0,
                    "total_questions": 0
                },
                "year_range": {
                    "earliest": None,
                    "latest": None
                },
                "scanned_at": datetime.now().isoformat()
            }

            all_years = []
            total_papers = 0
            total_questions = 0

            for exam_type in exam_types:
                papers = self.scan_papers_from_folder(exam_type)

                if papers:
                    summary["exam_types"][exam_type] = {
                        "papers": papers,
                        "count": len(papers),
                        "total_questions": sum(p.get("total_questions", 0) for p in papers),
                        "years": sorted(list(set(p.get("year") for p in papers if p.get("year"))), reverse=True)
                    }

                    # Collect years for overall range
                    exam_years = [p.get("year") for p in papers if p.get("year")]
                    all_years.extend(exam_years)

                    total_papers += len(papers)
                    total_questions += sum(p.get("total_questions", 0) for p in papers)

            # Update totals
            summary["totals"]["total_exam_types"] = len([et for et in summary["exam_types"] if summary["exam_types"][et]["papers"]])
            summary["totals"]["total_papers"] = total_papers
            summary["totals"]["total_questions"] = total_questions

            # Update year range
            if all_years:
                summary["year_range"]["earliest"] = min(all_years)
                summary["year_range"]["latest"] = max(all_years)

            logger.info("Generated folder-based papers summary",
                       total_papers=total_papers,
                       total_questions=total_questions,
                       exam_types=len(summary["exam_types"]))

            return summary

        except Exception as e:
            logger.error(f"Failed to generate papers summary: {e}", exc_info=e)
            raise ParkhoError(f"Failed to generate papers summary: {str(e)}")