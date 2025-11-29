from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_
from datetime import datetime

from ..models.content_job import ContentJob
from ..api.v1.schemas import JobStatus


class ContentJobRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_job(self, user_id: Optional[int] = None) -> ContentJob:
        job = ContentJob(user_id=user_id)
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def get(self, job_id: int) -> Optional[ContentJob]:
        return self.session.query(ContentJob).filter(ContentJob.id == job_id).first()

    def get_all_jobs(self, limit: int = 50, offset: int = 0) -> List[ContentJob]:
        return (
            self.session.query(ContentJob)
            .order_by(desc(ContentJob.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_jobs_by_user(self, user_id: int, limit: int = 50, offset: int = 0) -> List[ContentJob]:
        return (
            self.session.query(ContentJob)
            .filter(ContentJob.user_id == user_id)
            .order_by(desc(ContentJob.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_total_jobs_count(self) -> int:
        return self.session.query(ContentJob).count()

    def update_job(self, job: ContentJob) -> ContentJob:
        self.session.commit()
        self.session.refresh(job)
        return job

    def delete_job(self, job_id: int) -> bool:
        job = self.get(job_id)
        if job:
            self.session.delete(job)
            self.session.commit()
            return True
        return False

    def reset_job_for_retry(self, job_id: int) -> bool:
        job = self.get(job_id)
        if job and job.status == JobStatus.FAILED:
            job.status = JobStatus.PENDING
            job.progress = 0.0
            job.completed_at = None
            job.error_message = None
            self.session.commit()
            return True
        return False

    def find_existing_job_by_file_id(self, file_id: str) -> Optional[ContentJob]:
        """
        Find an existing job that is processing or has completed this file_id.
        This is used for duplicate detection.
        """
        # Query for jobs that contain this file_id in their input_config JSON
        # We need to use JSON functions to search within the JSON field
        jobs = (
            self.session.query(ContentJob)
            .filter(ContentJob.input_config.contains(f'"{file_id}"'))
            .filter(ContentJob.status.in_([JobStatus.PENDING, JobStatus.RUNNING, JobStatus.SUCCESS]))
            .order_by(desc(ContentJob.created_at))
            .all()
        )

        # Filter results to ensure the file_id is actually in file_ids array
        for job in jobs:
            if file_id in job.file_ids:
                return job

        return None

    def get_job_status_for_file_id(self, file_id: str) -> Optional[str]:
        """
        Get the current status of a job processing this file_id.
        Returns None if no job exists for this file_id.
        """
        job = self.find_existing_job_by_file_id(file_id)
        return job.status if job else None

    def get_by_id(self, job_id: int) -> Optional[ContentJob]:
        """Alias for get() method for compatibility"""
        return self.get(job_id)

    def mark_failed(self, job_id: int, error_message: str) -> bool:
        """Mark a job as failed with error message"""
        job = self.get(job_id)
        if job:
            job.status = JobStatus.FAILED
            job.error_message = error_message
            job.completed_at = datetime.now()
            self.session.commit()
            return True
        return False

    def mark_running(self, job_id: int) -> bool:
        """Mark a job as running"""
        job = self.get(job_id)
        if job:
            job.status = JobStatus.RUNNING
            self.session.commit()
            return True
        return False

    def mark_success(self, job_id: int) -> bool:
        """Mark a job as successfully completed"""
        job = self.get(job_id)
        if job:
            job.status = JobStatus.SUCCESS
            job.completed_at = datetime.now()
            self.session.commit()
            return True
        return False

    def update_progress(self, job_id: int, progress: float, message: str = None) -> bool:
        """Update job progress and optional status message"""
        job = self.get(job_id)
        if job:
            job.progress = progress
            if message:
                job.status_message = message
            self.session.commit()
            return True
        return False

    def create(self, job: ContentJob) -> ContentJob:
        """Create a new job"""
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def delete(self, job_id: int) -> bool:
        """Delete a job by ID"""
        return self.delete_job(job_id)