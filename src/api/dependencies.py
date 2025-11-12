from typing import Optional
import logging
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.firebase import verify_firebase_token, get_or_create_user
from ..repositories.content_job_repository import ContentJobRepository
from ..repositories.file_repository import FileRepository
from ..repositories.quiz_repository import QuizRepository
from ..repositories.analytics_repository import AnalyticsRepository
from ..services.file_storage import FileStorageService
from ..services.analytics_service import AnalyticsService
from ..services.analytics_dashboard_service import get_analytics_dashboard_service, AnalyticsDashboardService
from ..models.user import User

logger = logging.getLogger(__name__)

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


async def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[User]:
    """
    Get current authenticated user from Firebase token.

    This function:
    1. Extracts Firebase token from Authorization header
    2. Verifies token with Firebase
    3. Auto-creates user if valid token but user doesn't exist (with RAG registration)
    4. Returns User object or None

    Args:
        request: FastAPI request object
        db: Database session
        credentials: HTTP Bearer credentials (optional)

    Returns:
        User object if authenticated, None otherwise
    """
    try:
        # Check for Authorization header
        if not credentials or not credentials.credentials:
            return None

        token = credentials.credentials

        # Verify Firebase token
        firebase_data = verify_firebase_token(token)
        if not firebase_data:
            logger.debug("Invalid Firebase token provided")
            return None

        # Extract user data from Firebase token
        firebase_uid = firebase_data.get("uid")
        email = firebase_data.get("email")
        name = firebase_data.get("name", firebase_data.get("email", "Unknown User"))

        if not firebase_uid or not email:
            logger.warning(f"Firebase token missing required fields: uid={firebase_uid}, email={email}")
            return None

        # Auto-create user if they don't exist (includes RAG registration)
        try:
            user = await get_or_create_user(
                db=db,
                firebase_uid=firebase_uid,
                email=email,
                full_name=name,
                date_of_birth=None  # Optional field, can be updated later
            )

            logger.debug(f"Successfully authenticated user: {user.email}")
            return user

        except Exception as e:
            # Log RAG/creation errors but don't break authentication flow
            logger.error(f"Failed to create/retrieve user {firebase_uid}: {e}")

            # Try to fetch existing user without creation (fallback)
            existing_user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
            if existing_user:
                logger.info(f"Returning existing user {existing_user.email} despite creation error")
                return existing_user

            logger.error(f"Cannot authenticate user {firebase_uid} - creation failed and user doesn't exist")
            return None

    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return None


# Legacy dependencies for backward compatibility during transition
def get_video_job_repository(db: Session = Depends(get_db)):
    # Temporary redirect to content job repository
    return ContentJobRepository(db)