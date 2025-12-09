import structlog
from typing import Optional
from datetime import datetime

from ..models.content_job import ContentJob
from ..core.database import SessionLocal
from ..api.v1.schemas import JobStatus

logger = structlog.get_logger(__name__)

class ContentTutorAgent:
    def __init__(self, name: str):
        self.name = name

    async def run(self, job_id: int, data: dict) -> dict:
        raise NotImplementedError("Subclasses must implement run method")

    def _get_job(self, db, job_id: int) -> Optional[ContentJob]:
        return db.query(ContentJob).filter(ContentJob.id == job_id).first()

    async def update_job_progress(self, job_id: int, progress: float, message: Optional[str] = None):
        db = SessionLocal()
        try:
            job = self._get_job(db, job_id)
            if job:
                job.progress = progress
                job.status = JobStatus.RUNNING
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    async def mark_job_failed(self, job_id: int, error_message: str):
        db = SessionLocal()
        try:
            job = self._get_job(db, job_id)
            if job:
                job.status = JobStatus.FAILED
                job.error_message = error_message
                job.completed_at = datetime.now()
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    async def _push_progress_update(self, job_id: int, progress: float, message: str):
        # No-op: websocket push removed (polling used)
        return