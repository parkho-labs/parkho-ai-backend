from sqlalchemy.orm import Session
from typing import Optional

from ..exceptions import DatabaseError
from ..models.content_job import ContentJob
from ..repositories.content_job_repository import ContentJobRepository


class DatabaseService:
    def __init__(self, session: Session):
        self.session = session
        self.job_repo = ContentJobRepository(session)

    def get_job(self, job_id: int) -> Optional[ContentJob]:
        try:
            return self.job_repo.get(job_id)
        except Exception as e:
            raise DatabaseError(f"Failed to retrieve job {job_id}: {str(e)}")

    def update_job(self, job: ContentJob) -> None:
        try:
            self.job_repo.update(job)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise DatabaseError(f"Failed to update job {job.id}: {str(e)}")

    def save_job(self, job: ContentJob) -> ContentJob:
        try:
            saved_job = self.job_repo.create(job)
            self.session.commit()
            return saved_job
        except Exception as e:
            self.session.rollback()
            raise DatabaseError(f"Failed to save job: {str(e)}")

    def commit(self) -> None:
        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise DatabaseError(f"Failed to commit transaction: {str(e)}")

    def rollback(self) -> None:
        self.session.rollback()