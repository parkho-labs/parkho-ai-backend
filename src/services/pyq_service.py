from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import structlog
from datetime import datetime

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