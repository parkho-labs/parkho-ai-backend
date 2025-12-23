"""
PYQ GCS API Endpoints
Simple endpoints to fetch JSON papers directly from Google Cloud Storage
"""

import structlog
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Path
from fastapi.responses import JSONResponse

from ....services.pyq_storage_service import PYQStorageService
from ....services.gcp_service import GCPService
from ....config import get_settings

logger = structlog.get_logger(__name__)

router = APIRouter()

# Initialize services
settings = get_settings()
gcp_service = GCPService(settings)
pyq_storage = PYQStorageService(gcp_service)


@router.get("/papers")
async def list_all_papers(
    exam_type: Optional[str] = Query(None, description="Filter by exam type (UGC_NET, MPSET)")
):
    """
    List all available PYQ papers from GCS

    Returns paper metadata and download information.
    """
    try:
        papers = pyq_storage.list_papers(exam_type)
        summary = pyq_storage.get_paper_summary()

        logger.info("Listed PYQ papers from GCS",
                   exam_type=exam_type or "all",
                   count=len(papers))

        return {
            "papers": papers,
            "summary": summary,
            "total": len(papers)
        }

    except Exception as e:
        logger.error("Failed to list papers from GCS", error=str(e), exc_info=e)
        raise HTTPException(status_code=500, detail="Failed to retrieve papers")


@router.get("/papers/{exam_type}")
async def list_papers_by_exam(
    exam_type: str = Path(..., description="Exam type (UGC_NET, MPSET)")
):
    """
    List all papers for a specific exam type
    """
    try:
        papers = pyq_storage.list_papers(exam_type)

        logger.info("Listed papers for exam type",
                   exam_type=exam_type,
                   count=len(papers))

        return {
            "exam_type": exam_type,
            "papers": papers,
            "total": len(papers)
        }

    except Exception as e:
        logger.error("Failed to list papers by exam type",
                    exam_type=exam_type, error=str(e), exc_info=e)
        raise HTTPException(status_code=500, detail="Failed to retrieve papers")


@router.get("/papers/{exam_type}/{filename}")
async def get_paper_json(
    exam_type: str = Path(..., description="Exam type (UGC_NET, MPSET)"),
    filename: str = Path(..., description="JSON filename"),
    include_answers: bool = Query(False, description="Include correct answers (for practice mode)")
):
    """
    Get the actual JSON content of a specific paper

    Returns the exact JSON structure as stored in GCS.
    """
    try:
        paper_data = pyq_storage.get_paper(exam_type, filename)

        if not paper_data:
            raise HTTPException(status_code=404, detail="Paper not found")

        # Get the questions
        questions = paper_data["questions"]

        # Remove correct answers if not requested (for exam mode)
        if not include_answers and isinstance(questions, list):
            safe_questions = []
            for q in questions:
                safe_q = {k: v for k, v in q.items() if k != "correct_answer"}
                safe_questions.append(safe_q)
            questions = safe_questions

        response_data = {
            **paper_data["metadata"],
            "questions": questions,
            "total_questions": paper_data["total_questions"]
        }

        logger.info("Retrieved paper JSON from GCS",
                   exam_type=exam_type,
                   filename=filename,
                   include_answers=include_answers,
                   questions_count=len(questions))

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get paper JSON",
                    exam_type=exam_type,
                    filename=filename,
                    error=str(e), exc_info=e)
        raise HTTPException(status_code=500, detail="Failed to retrieve paper")


@router.get("/papers/{exam_type}/{filename}/raw")
async def get_paper_raw_json(
    exam_type: str = Path(..., description="Exam type (UGC_NET, MPSET)"),
    filename: str = Path(..., description="JSON filename")
):
    """
    Get the raw JSON array exactly as stored (for debugging/admin)

    Returns the pure JSON array without any metadata wrapper.
    """
    try:
        paper_data = pyq_storage.get_paper(exam_type, filename)

        if not paper_data:
            raise HTTPException(status_code=404, detail="Paper not found")

        # Return just the questions array
        questions = paper_data["questions"]

        logger.info("Retrieved raw paper JSON from GCS",
                   exam_type=exam_type,
                   filename=filename,
                   questions_count=len(questions) if isinstance(questions, list) else 0)

        return questions

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get raw paper JSON",
                    exam_type=exam_type,
                    filename=filename,
                    error=str(e), exc_info=e)
        raise HTTPException(status_code=500, detail="Failed to retrieve paper")


@router.get("/summary")
async def get_papers_summary():
    """
    Get summary statistics of all papers in GCS
    """
    try:
        summary = pyq_storage.get_paper_summary()

        logger.info("Retrieved papers summary from GCS",
                   total_papers=summary.get("total_papers", 0))

        return summary

    except Exception as e:
        logger.error("Failed to get papers summary", error=str(e), exc_info=e)
        raise HTTPException(status_code=500, detail="Failed to retrieve summary")


@router.post("/upload")
async def upload_paper(
    exam_type: str = Query(..., description="Exam type (UGC_NET, MPSET)"),
    filename: str = Query(..., description="JSON filename"),
    questions: list = Query(..., description="Questions JSON array")
):
    """
    Upload a new paper to GCS (admin endpoint)
    """
    try:
        success = pyq_storage.upload_paper(exam_type, filename, questions)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to upload paper")

        logger.info("Uploaded paper to GCS",
                   exam_type=exam_type,
                   filename=filename,
                   questions_count=len(questions))

        return {
            "success": True,
            "message": f"Paper uploaded successfully to pyq/{exam_type}/{filename}",
            "exam_type": exam_type,
            "filename": filename,
            "questions_count": len(questions)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to upload paper",
                    exam_type=exam_type,
                    filename=filename,
                    error=str(e), exc_info=e)
        raise HTTPException(status_code=500, detail="Failed to upload paper")