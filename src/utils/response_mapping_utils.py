"""Response mapping utilities for clean API response creation."""

from typing import List
from ..api.v1.schemas import ContentJobResponse, FileProcessingResult, JobStatus
from ..models.content_job import ContentJob


def map_job_to_response(job: ContentJob) -> ContentJobResponse:
    """Map ContentJob model to ContentJobResponse schema."""
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


def map_jobs_to_responses(jobs: List[ContentJob]) -> List[ContentJobResponse]:
    """Map list of ContentJob models to list of ContentJobResponse schemas."""
    return [map_job_to_response(job) for job in jobs]


def create_file_processing_results(input_config_data: List[dict], job_id: int) -> List[FileProcessingResult]:
    """Create FileProcessingResult objects for each input source."""
    return [
        FileProcessingResult(
            file_id=data["id"],
            job_id=job_id,
            status=JobStatus.PENDING,
            message="File processing started successfully"
        )
        for data in input_config_data
    ]