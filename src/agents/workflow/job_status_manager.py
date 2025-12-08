from datetime import datetime
from typing import Optional
import structlog

from ...api.v1.schemas import JobStatus
from ...utils.database_utils import DatabaseService
from ...exceptions import JobError

logger = structlog.get_logger(__name__)


class JobStatusManager:
    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service

    async def update_job_status(self, job_id: int, status: JobStatus, progress: float = None, message: str = None, **kwargs) -> None:
        try:
            job = self.db_service.get_job(job_id)
            if not job:
                raise JobError(f"Job {job_id} not found")

            job.status = status
            job.updated_at = datetime.utcnow()

            if progress is not None:
                job.progress = min(100.0, max(0.0, progress))

            if message:
                job.status_message = message

            for key, value in kwargs.items():
                if hasattr(job, key):
                    setattr(job, key, value)

            self.db_service.update_job(job)

            logger.info("job_status_updated",
                       job_id=job_id,
                       status=status.value,
                       progress=job.progress,
                       message=message)

        except Exception as e:
            logger.error("job_status_update_failed",
                        job_id=job_id,
                        status=status.value,
                        error=str(e))
            raise JobError(f"Failed to update job status: {str(e)}")

    async def mark_job_started(self, job_id: int) -> None:
        await self.update_job_status(job_id, JobStatus.RUNNING, progress=0.0, message="Job started")

    async def mark_job_completed(self, job_id: int, **kwargs) -> None:
        await self.update_job_status(job_id, JobStatus.SUCCESS, progress=100.0, message="Job completed successfully", **kwargs)

    async def mark_job_failed(self, job_id: int, error_message: str) -> None:
        await self.update_job_status(job_id, JobStatus.FAILED, message=f"Job failed: {error_message}")

    async def update_job_progress(self, job_id: int, progress: float, message: str = None) -> None:
        await self.update_job_status(job_id, JobStatus.RUNNING, progress=progress, message=message)

    def get_job(self, job_id: int):
        return self.db_service.get_job(job_id)

    def update_job_in_db(self, job):
        self.db_service.update_job(job)