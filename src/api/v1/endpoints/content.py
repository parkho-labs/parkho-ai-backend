import structlog
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Response
from sqlalchemy.orm import Session

from ...dependencies import get_content_job_repository, get_file_storage, get_current_user_optional, get_db
from ..schemas import (
    ContentProcessingRequest,
    ProcessingJobResponse,
    MultiStatusProcessingResponse,
    FileProcessingResult,
    ContentJobResponse,
    ContentResults,
    ContentJobsListResponse,
    SummaryResponse,
    ContentTextResponse,
    FileUploadResponse,
    JobStatus,
)
from ....config import get_settings
from ....services.content_processor import content_processor
from ....services.duplicate_detector import DuplicateDetector
from ....core.exceptions import JobNotFoundError, ValidationError
from ....models.user import User
from ....models.content_job import ContentJob

logger = structlog.get_logger(__name__)
settings = get_settings()

router = APIRouter()


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    file_storage = Depends(get_file_storage)
) -> FileUploadResponse:
    try:
        file_id = await file_storage.store_file(file)

        file_metadata = file_storage.get_file_metadata(file_id)
        if not file_metadata:
            raise HTTPException(status_code=500, detail="Failed to retrieve file metadata")

        logger.info("File uploaded successfully", file_id=file_id, filename=file.filename)

        return FileUploadResponse(
            file_id=file_id,
            filename=file_metadata.filename,
            file_size=file_metadata.file_size,
            content_type=file_metadata.content_type,
            upload_timestamp=file_metadata.upload_timestamp
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to upload file", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to upload file")


@router.post("/process", response_model=List[FileProcessingResult])
async def process_content(
    request: ContentProcessingRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    repo = Depends(get_content_job_repository),
    current_user: Optional[User] = Depends(get_current_user_optional)
) -> List[FileProcessingResult]:
    """
    Process content with 207 Multi-Status response format for duplicate detection.

    Currently supports single file processing only, but returns array format
    for future extensibility to multiple files.
    """
    try:
        results = []

        # Process multimodal input configuration
        user_id = current_user.id if current_user else None
        job = repo.create_job(user_id=user_id)

        # Convert input_config to dict format for storage
        input_config_data = []
        for input_item in request.input_config:
            input_config_data.append({
                "content_type": input_item.content_type.value,
                "id": input_item.id
            })

        job.set_input_config(
            input_config=input_config_data,
            question_types=[qt.value for qt in request.question_types],
            difficulty_level=request.difficulty_level.value,
            num_questions=request.num_questions,
            generate_summary=request.generate_summary,
            llm_provider=request.llm_provider.value
        )
        repo.update_job(job)

        # Start background processing
        background_tasks.add_task(
            content_processor.process_content_background_sync,
            job.id
        )

        results.append(FileProcessingResult(
            file_id="multimodal_content",
            job_id=job.id,
            status=JobStatus.PENDING,
            message="Multimodal content processing started successfully",
            estimated_duration_minutes=5,
            websocket_url=f"ws://localhost:{settings.api_port}/ws/content/{job.id}"
        ))

        logger.info(
            "Multimodal content processing job created",
            job_id=job.id,
            input_config=input_config_data,
            question_types=[qt.value for qt in request.question_types]
        )

        # Set appropriate HTTP status code
        if any(result.status == JobStatus.FAILED for result in results):
            response.status_code = 207  # Multi-Status (some failed)
        elif any(result.status in [JobStatus.PROCESSING, JobStatus.COMPLETED] and result.job_id for result in results):
            response.status_code = 207  # Multi-Status (some duplicates)
        else:
            response.status_code = 207  # Multi-Status (for consistency)

        return results

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to process content request", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process content request")


@router.get("/{job_id}/status", response_model=ContentJobResponse)
async def get_job_status(
    job_id: int,
    repo = Depends(get_content_job_repository)
) -> ContentJobResponse:
    try:
        job = repo.get(job_id)
        if not job:
            raise JobNotFoundError(job_id)

        return ContentJobResponse(
            id=job.id,
            status=job.status,
            progress=job.progress,
            created_at=job.created_at,
            completed_at=job.completed_at,
            title=job.title,
            error_message=job.error_message,
            input_url=job.input_url,
            file_ids=job.file_ids
        )

    except JobNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Failed to get job status", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve job status")


@router.get("/{job_id}/results", response_model=ContentResults)
async def get_job_results(
    job_id: int,
    repo = Depends(get_content_job_repository)
) -> ContentResults:
    try:
        job = repo.get(job_id)
        if not job:
            raise JobNotFoundError(job_id)

        if job.status != "completed":
            raise HTTPException(
                status_code=409,
                detail=f"Job not complete. Current status: {job.status}"
            )

        processing_duration = None
        if job.completed_at and job.created_at:
            processing_duration = int((job.completed_at - job.created_at).total_seconds())

        return ContentResults(
            job_id=job.id,
            status=job.status,
            title=job.title,
            processing_duration_seconds=processing_duration,
            created_at=job.created_at,
            completed_at=job.completed_at,
            summary=job.summary,
            questions=job.questions,
            content_text=job.content_text
        )

    except JobNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get job results", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve job results")


@router.get("/{job_id}/summary", response_model=SummaryResponse)
async def get_job_summary(
    job_id: int,
    repo = Depends(get_content_job_repository)
) -> SummaryResponse:
    try:
        job = repo.get(job_id)
        if not job:
            raise JobNotFoundError(job_id)

        if job.status != "completed":
            raise HTTPException(
                status_code=409,
                detail=f"Job not complete. Current status: {job.status}"
            )

        return SummaryResponse(summary=job.summary)

    except JobNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get summary", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve summary")


@router.get("/{job_id}/content", response_model=ContentTextResponse)
async def get_job_content(
    job_id: int,
    repo = Depends(get_content_job_repository)
) -> ContentTextResponse:
    try:
        job = repo.get(job_id)
        if not job:
            raise JobNotFoundError(job_id)

        if job.status != "completed":
            raise HTTPException(
                status_code=409,
                detail=f"Job not complete. Current status: {job.status}"
            )

        return ContentTextResponse(content_text=job.content_text)

    except JobNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get content", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve content")


@router.get("/jobs", response_model=ContentJobsListResponse)
async def get_jobs_list(
    limit: int = 50,
    offset: int = 0,
    repo = Depends(get_content_job_repository),
    current_user: Optional[User] = Depends(get_current_user_optional)
) -> ContentJobsListResponse:
    try:
        if current_user:
            jobs = repo.get_jobs_by_user(current_user.id, limit=limit, offset=offset)
            total_count = repo.session.query(ContentJob).filter(ContentJob.user_id == current_user.id).count()
        else:
            jobs = repo.get_all_jobs(limit=limit, offset=offset)
            total_count = repo.get_total_jobs_count()

        job_responses = []
        for job in jobs:
            job_responses.append(ContentJobResponse(
                id=job.id,
                status=job.status,
                progress=job.progress,
                created_at=job.created_at,
                completed_at=job.completed_at,
                title=job.title,
                error_message=job.error_message,
                input_url=job.input_url,
                file_ids=job.file_ids
            ))

        return ContentJobsListResponse(
            total=total_count,
            jobs=job_responses
        )

    except Exception as e:
        logger.error("Failed to get jobs list", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve jobs list")


@router.delete("/{job_id}")
async def delete_job(
    job_id: int,
    repo = Depends(get_content_job_repository)
):
    try:
        success = repo.delete_job(job_id)
        if not success:
            raise HTTPException(status_code=404, detail="Job not found")

        logger.info("Job deleted successfully", job_id=job_id)
        return {"message": "Job deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete job", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete job")


@router.get("/supported-types")
async def get_supported_types():
    return {
        "supported_types": ["youtube", "pdf", "docx", "web_url"],
        "file_limits": {
            "pdf": "10MB",
            "docx": "5MB",
            "doc": "5MB"
        },
        "supported_extensions": [".pdf", ".docx", ".doc"],
        "url_support": ["YouTube videos", "Web pages (HTML content)"]
    }