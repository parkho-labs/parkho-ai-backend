from typing import Optional
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from fastapi import Depends

from ..core.database import get_db
from ..repositories.content_job_repository import ContentJobRepository
from ..repositories.file_repository import FileRepository
from ..repositories.quiz_repository import QuizRepository
from ..repositories.analytics_repository import AnalyticsRepository
from ..services.file_storage import FileStorageService
from ..services.analytics_service import AnalyticsService
from ..services.analytics_dashboard_service import get_analytics_dashboard_service, AnalyticsDashboardService
from ..models.user import User

security = HTTPBearer(auto_error=False)


def get_content_job_repository(db: Session = Depends(get_db)) -> ContentJobRepository:
    return ContentJobRepository(db)


def get_file_repository(db: Session = Depends(get_db)) -> FileRepository:
    return FileRepository(db)


def get_quiz_repository(db: Session = Depends(get_db)) -> QuizRepository:
    return QuizRepository(db)


def get_file_storage(db: Session = Depends(get_db)) -> FileStorageService:
    file_repo = FileRepository(db)
    return FileStorageService(file_repo)


def get_analytics_repository(db: Session = Depends(get_db)) -> AnalyticsRepository:
    return AnalyticsRepository(db)


def get_analytics_service(repo: AnalyticsRepository = Depends(get_analytics_repository)) -> AnalyticsService:
    return AnalyticsService(repo)


def get_analytics_dashboard_service_dep() -> AnalyticsDashboardService:
    return get_analytics_dashboard_service()


def get_current_user_optional() -> Optional[User]:
    # TODO: Implement actual user authentication
    return None


# Legacy dependencies for backward compatibility during transition
def get_video_job_repository(db: Session = Depends(get_db)):
    # Temporary redirect to content job repository
    return ContentJobRepository(db)