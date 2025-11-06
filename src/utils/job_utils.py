

from fastapi import Depends, HTTPException
from src.api.dependencies import get_content_job_repository
from src.api.v1.schemas import JobStatus
from src.core.exceptions import JobNotFoundError


def check_job_exists(job_id: int, repo = Depends(get_content_job_repository)) -> bool:

    job = repo.get(job_id)
    if not job:
        raise JobNotFoundError(job.id)
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail=f"Job not complete. Current status: {job.status}"
        )
    return job