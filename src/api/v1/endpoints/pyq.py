"""
Previous Year Questions (PYQ) API Endpoints

Provides endpoints for exam paper management and user attempt tracking
"""

import structlog
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query

from ...dependencies import get_db
from ..schemas import (
    PaperListResponse,
    ExamPaperDetail,
    StartAttemptResponse,
    ExamAnswers,
    SubmitAttemptResponse,
    AttemptResultsResponse,
    UserHistoryResponse,
    PaperStatsResponse,
    AvailableFiltersResponse
)
from ....services.pyq_service import PYQService
from ....exceptions import ParkhoError

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/papers", response_model=PaperListResponse)
async def get_exam_papers(
    limit: int = Query(default=50, ge=1, le=100, description="Number of papers to return"),
    offset: int = Query(default=0, ge=0, description="Number of papers to skip"),
    db=Depends(get_db)
) -> PaperListResponse:
    """
    Get all available exam papers with summary information.

    Returns paginated list of exam papers along with summary statistics.
    """
    try:
        pyq_service = PYQService(db)
        result = pyq_service.get_all_papers(limit=limit, offset=offset)

        logger.info("Retrieved exam papers", count=len(result["papers"]), limit=limit, offset=offset)
        return result

    except ParkhoError as e:
        logger.error("Failed to get exam papers", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error getting exam papers", error=str(e), exc_info=e)
        raise HTTPException(status_code=500, detail="Failed to retrieve exam papers")


@router.get("/papers/{paper_id}", response_model=ExamPaperDetail)
async def get_exam_paper(
    paper_id: int,
    include_questions: bool = Query(default=False, description="Include questions in response"),
    db=Depends(get_db)
) -> ExamPaperDetail:
    """
    Get specific exam paper details.

    Optionally include questions (without correct answers for security).
    """
    try:
        pyq_service = PYQService(db)
        result = pyq_service.get_paper_by_id(paper_id, include_questions=include_questions)

        logger.info("Retrieved exam paper", paper_id=paper_id, include_questions=include_questions)
        return result

    except ParkhoError as e:
        logger.error("Failed to get exam paper", paper_id=paper_id, error=str(e))
        raise HTTPException(status_code=404 if "not found" in str(e).lower() else 400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error getting exam paper", paper_id=paper_id, error=str(e), exc_info=e)
        raise HTTPException(status_code=500, detail="Failed to retrieve exam paper")


@router.post("/papers/{paper_id}/start", response_model=StartAttemptResponse)
async def start_exam_attempt(
    paper_id: int,
    user_id: Optional[str] = Query(default=None, description="Optional user identifier"),
    db=Depends(get_db)
) -> StartAttemptResponse:
    """
    Start a new exam attempt.

    Creates a new attempt record and returns questions without correct answers.
    """
    try:
        pyq_service = PYQService(db)
        result = pyq_service.start_exam_attempt(paper_id, user_identifier=user_id)

        logger.info("Started exam attempt", paper_id=paper_id, attempt_id=result["attempt_id"], user_id=user_id)
        return result

    except ParkhoError as e:
        logger.error("Failed to start exam attempt", paper_id=paper_id, user_id=user_id, error=str(e))
        raise HTTPException(status_code=404 if "not found" in str(e).lower() else 400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error starting exam attempt", paper_id=paper_id, user_id=user_id, error=str(e), exc_info=e)
        raise HTTPException(status_code=500, detail="Failed to start exam attempt")


@router.post("/attempts/{attempt_id}/submit", response_model=SubmitAttemptResponse)
async def submit_exam_attempt(
    attempt_id: int,
    answers: ExamAnswers,
    db=Depends(get_db)
) -> SubmitAttemptResponse:
    """
    Submit exam answers and get results.

    Calculates score and provides detailed results with correct answers.
    """
    try:
        pyq_service = PYQService(db)
        result = pyq_service.submit_exam_attempt(attempt_id, answers.answers)

        logger.info(
            "Submitted exam attempt",
            attempt_id=attempt_id,
            score=result["score"],
            percentage=result["percentage"],
            total_answers=len(answers.answers)
        )
        return result

    except ParkhoError as e:
        logger.error("Failed to submit exam attempt", attempt_id=attempt_id, error=str(e))
        raise HTTPException(
            status_code=404 if "not found" in str(e).lower() else 400,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Unexpected error submitting exam attempt", attempt_id=attempt_id, error=str(e), exc_info=e)
        raise HTTPException(status_code=500, detail="Failed to submit exam attempt")


@router.get("/attempts/{attempt_id}/results", response_model=AttemptResultsResponse)
async def get_attempt_results(
    attempt_id: int,
    db=Depends(get_db)
) -> AttemptResultsResponse:
    """
    Get detailed results for a completed attempt.

    Returns score breakdown and question-wise analysis.
    """
    try:
        pyq_service = PYQService(db)
        result = pyq_service.get_attempt_results(attempt_id)

        logger.info("Retrieved attempt results", attempt_id=attempt_id, score=result["score"])
        return result

    except ParkhoError as e:
        logger.error("Failed to get attempt results", attempt_id=attempt_id, error=str(e))
        raise HTTPException(
            status_code=404 if "not found" in str(e).lower() else 400,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Unexpected error getting attempt results", attempt_id=attempt_id, error=str(e), exc_info=e)
        raise HTTPException(status_code=500, detail="Failed to retrieve attempt results")


@router.get("/history", response_model=UserHistoryResponse)
async def get_user_attempt_history(
    user_id: str = Query(..., description="User identifier"),
    limit: int = Query(default=20, ge=1, le=100, description="Number of attempts to return"),
    offset: int = Query(default=0, ge=0, description="Number of attempts to skip"),
    db=Depends(get_db)
) -> UserHistoryResponse:
    """
    Get user's exam attempt history with performance statistics.

    Returns paginated list of attempts and overall performance metrics.
    """
    try:
        pyq_service = PYQService(db)
        result = pyq_service.get_user_attempt_history(user_id, limit=limit, offset=offset)

        logger.info("Retrieved user history", user_id=user_id, attempts_count=len(result["attempts"]))
        return result

    except ParkhoError as e:
        logger.error("Failed to get user history", user_id=user_id, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error getting user history", user_id=user_id, error=str(e), exc_info=e)
        raise HTTPException(status_code=500, detail="Failed to retrieve user history")


@router.get("/papers/{paper_id}/stats", response_model=PaperStatsResponse)
async def get_paper_performance_stats(
    paper_id: int,
    db=Depends(get_db)
) -> PaperStatsResponse:
    """
    Get performance statistics for a specific exam paper.

    Returns aggregate statistics across all attempts for this paper.
    """
    try:
        pyq_service = PYQService(db)
        result = pyq_service.get_paper_performance_stats(paper_id)

        logger.info("Retrieved paper stats", paper_id=paper_id, total_attempts=result["statistics"]["total_attempts"])
        return result

    except ParkhoError as e:
        logger.error("Failed to get paper stats", paper_id=paper_id, error=str(e))
        raise HTTPException(
            status_code=404 if "not found" in str(e).lower() else 400,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Unexpected error getting paper stats", paper_id=paper_id, error=str(e), exc_info=e)
        raise HTTPException(status_code=500, detail="Failed to retrieve paper statistics")


@router.get("/search")
async def search_papers(
    q: str = Query(..., min_length=1, description="Search term"),
    db=Depends(get_db)
) -> List[dict]:
    """
    Search exam papers by title or exam name.

    Returns matching papers based on search term.
    """
    try:
        pyq_service = PYQService(db)
        result = pyq_service.search_papers(q)

        logger.info("Searched papers", search_term=q, results_count=len(result))
        return result

    except ParkhoError as e:
        logger.error("Failed to search papers", search_term=q, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error searching papers", search_term=q, error=str(e), exc_info=e)
        raise HTTPException(status_code=500, detail="Failed to search papers")


@router.get("/filters", response_model=AvailableFiltersResponse)
async def get_available_filters(
    db=Depends(get_db)
) -> AvailableFiltersResponse:
    """
    Get available filter options for papers.

    Returns unique years and exam names for filtering.
    """
    try:
        pyq_service = PYQService(db)
        result = pyq_service.get_available_filters()

        logger.info("Retrieved filter options", years_count=len(result["years"]), exams_count=len(result["exam_names"]))
        return result

    except ParkhoError as e:
        logger.error("Failed to get filter options", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error getting filter options", error=str(e), exc_info=e)
        raise HTTPException(status_code=500, detail="Failed to retrieve filter options")