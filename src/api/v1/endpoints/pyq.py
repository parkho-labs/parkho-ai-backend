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


# =============================================================================
# EXAM-SPECIFIC ROUTES (MPSET and UGC NET)
# =============================================================================

@router.get("/mpset/papers", response_model=PaperListResponse)
async def get_mpset_papers(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db=Depends(get_db)
) -> PaperListResponse:
    """Get all MPSET exam papers"""
    try:
        pyq_service = PYQService(db)
        all_papers = pyq_service.get_all_papers(limit=200, offset=0)  # Get all first
        
        # Filter MPSET papers
        mpset_papers = [p for p in all_papers["papers"] if p["exam_name"] == "MPSET"]
        
        # Apply pagination
        paginated = mpset_papers[offset:offset+limit]
        
        result = {
            "papers": paginated,
            "summary": {
                "total_papers": len(mpset_papers),
                "available_years": sorted(list(set(p["year"] for p in mpset_papers)), reverse=True),
                "available_exams": ["MPSET"],
                "year_range": {
                    "earliest": min(p["year"] for p in mpset_papers) if mpset_papers else None,
                    "latest": max(p["year"] for p in mpset_papers) if mpset_papers else None
                }
            },
            "pagination": {"limit": limit, "offset": offset, "total": len(mpset_papers)}
        }
        
        logger.info("Retrieved MPSET papers", count=len(paginated))
        return result
        
    except Exception as e:
        logger.error("Failed to get MPSET papers", error=str(e), exc_info=e)
        raise HTTPException(status_code=500, detail="Failed to retrieve MPSET papers")


@router.get("/ugcnet/papers", response_model=PaperListResponse)
async def get_ugcnet_papers(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db=Depends(get_db)
) -> PaperListResponse:
    """Get all UGC NET exam papers"""
    try:
        pyq_service = PYQService(db)
        all_papers = pyq_service.get_all_papers(limit=200, offset=0)
        
        # Filter UGC NET papers
        ugcnet_papers = [p for p in all_papers["papers"] if p["exam_name"] == "UGC NET"]
        
        # Apply pagination
        paginated = ugcnet_papers[offset:offset+limit]
        
        result = {
            "papers": paginated,
            "summary": {
                "total_papers": len(ugcnet_papers),
                "available_years": sorted(list(set(p["year"] for p in ugcnet_papers)), reverse=True),
                "available_exams": ["UGC NET"],
                "year_range": {
                    "earliest": min(p["year"] for p in ugcnet_papers) if ugcnet_papers else None,
                    "latest": max(p["year"] for p in ugcnet_papers) if ugcnet_papers else None
                }
            },
            "pagination": {"limit": limit, "offset": offset, "total": len(ugcnet_papers)}
        }
        
        logger.info("Retrieved UGC NET papers", count=len(paginated))
        return result
        
    except Exception as e:
        logger.error("Failed to get UGC NET papers", error=str(e), exc_info=e)
        raise HTTPException(status_code=500, detail="Failed to retrieve UGC NET papers")


@router.get("/mpset/papers/{paper_id}", response_model=ExamPaperDetail)
async def get_mpset_paper(
    paper_id: int,
    include_questions: bool = Query(default=False),
    db=Depends(get_db)
) -> ExamPaperDetail:
    """Get specific MPSET paper details"""
    try:
        pyq_service = PYQService(db)
        result = pyq_service.get_paper_by_id(paper_id, include_questions=include_questions)
        
        if result["exam_name"] != "MPSET":
            raise HTTPException(status_code=404, detail="Paper is not an MPSET paper")
        
        logger.info("Retrieved MPSET paper", paper_id=paper_id)
        return result
        
    except HTTPException:
        raise
    except ParkhoError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Failed to get MPSET paper", paper_id=paper_id, error=str(e), exc_info=e)
        raise HTTPException(status_code=500, detail="Failed to retrieve MPSET paper")


@router.get("/ugcnet/papers/{paper_id}", response_model=ExamPaperDetail)
async def get_ugcnet_paper(
    paper_id: int,
    include_questions: bool = Query(default=False),
    db=Depends(get_db)
) -> ExamPaperDetail:
    """Get specific UGC NET paper details"""
    try:
        pyq_service = PYQService(db)
        result = pyq_service.get_paper_by_id(paper_id, include_questions=include_questions)
        
        if result["exam_name"] != "UGC NET":
            raise HTTPException(status_code=404, detail="Paper is not a UGC NET paper")
        
        logger.info("Retrieved UGC NET paper", paper_id=paper_id)
        return result
        
    except HTTPException:
        raise
    except ParkhoError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Failed to get UGC NET paper", paper_id=paper_id, error=str(e), exc_info=e)
        raise HTTPException(status_code=500, detail="Failed to retrieve UGC NET paper")



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


# =============================================================================
# PDF PARSING ENDPOINTS (Admin/Dev Data Ingestion)
# =============================================================================

@router.post("/parse-pdf", response_model=dict)
async def parse_pdf(
    request: dict,
    db=Depends(get_db)
) -> dict:
    """
    Parse PDF from URL and return structured exam paper data (preview only).
    
    This endpoint is for admin/dev use to preview parsed questions before importing.
    Does NOT save to database.
    
    Request body:
        - url: URL of the PDF file
        - title: Optional exam title
        - year: Optional exam year
        - exam_name: Optional exam name
        - time_limit_minutes: Optional time limit (default: 180)
    """
    try:
        from ..schemas import ParsePDFRequest, ParsePDFResponse
        
        # Validate request
        parse_request = ParsePDFRequest(**request)
        
        pyq_service = PYQService(db)
        
        # Build metadata
        metadata = {}
        if parse_request.title:
            metadata["title"] = parse_request.title
        if parse_request.year:
            metadata["year"] = parse_request.year
        if parse_request.exam_name:
            metadata["exam_name"] = parse_request.exam_name
        if parse_request.time_limit_minutes:
            metadata["time_limit_minutes"] = parse_request.time_limit_minutes
        
        # Parse PDF
        parsed_data = await pyq_service.parse_pdf_from_url(
            parse_request.url,
            metadata=metadata if metadata else None
        )
        
        logger.info(
            "PDF parsed successfully (preview)",
            url=parse_request.url,
            questions=parsed_data.get("total_questions", 0)
        )
        
        return {
            "success": True,
            "parsed_data": parsed_data,
            "questions_found": parsed_data.get("total_questions", 0),
            "total_marks": parsed_data.get("total_marks", 0),
            "message": f"Successfully parsed {parsed_data.get('total_questions', 0)} questions from PDF"
        }

    except ParkhoError as e:
        logger.error("Failed to parse PDF", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error parsing PDF", error=str(e), exc_info=e)
        raise HTTPException(status_code=500, detail=f"Failed to parse PDF: {str(e)}")


@router.post("/papers/import", response_model=dict)
async def import_paper_from_pdf(
    request: dict,
    db=Depends(get_db)
) -> dict:
    """
    Parse PDF from URL and import it as an exam paper into the database.
    
    This endpoint is for admin/dev use to import question papers from PDFs.
    
    Request body:
        - url: URL of the PDF file
        - title: Optional exam title
        - year: Optional exam year
        - exam_name: Optional exam name
        - time_limit_minutes: Optional time limit (default: 180)
        - activate: Whether to activate the paper immediately (default: true)
    """
    try:
        from ..schemas import ImportPaperRequest, ImportPaperResponse
        
        # Validate request
        import_request = ImportPaperRequest(**request)
        
        pyq_service = PYQService(db)
        
        # Build metadata
        metadata = {}
        if import_request.title:
            metadata["title"] = import_request.title
        if import_request.year:
            metadata["year"] = import_request.year
        if import_request.exam_name:
            metadata["exam_name"] = import_request.exam_name
        if import_request.time_limit_minutes:
            metadata["time_limit_minutes"] = import_request.time_limit_minutes
        
        # Import paper
        result = await pyq_service.import_paper_from_pdf(
            import_request.url,
            metadata=metadata if metadata else None,
            activate=import_request.activate
        )
        
        logger.info(
            "Paper imported from PDF",
            paper_id=result["paper_id"],
            title=result["title"],
            questions=result["questions_imported"]
        )
        
        return {
            "success": True,
            "paper_id": result["paper_id"],
            "title": result["title"],
            "questions_imported": result["questions_imported"],
            "total_marks": result["total_marks"],
            "message": f"Successfully imported paper '{result['title']}' with {result['questions_imported']} questions"
        }

    except ParkhoError as e:
        logger.error("Failed to import paper from PDF", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error importing paper from PDF", error=str(e), exc_info=e)
        raise HTTPException(status_code=500, detail=f"Failed to import paper: {str(e)}")