from typing import Optional
import logging
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends, Request, HTTPException
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
from ..services.llm_service import LLMService
from ..models.user import User
from ..config import get_settings

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


def get_llm_service() -> LLMService:
    settings = get_settings()
    return LLMService(
        openai_api_key=settings.openai_api_key,
        anthropic_api_key=settings.anthropic_api_key,
        google_api_key=settings.google_api_key,
        openai_model_name=settings.openai_model_name,
        anthropic_model_name=settings.anthropic_model_name,
        google_model_name=settings.google_model_name
    )


async def get_current_user_required(
    request: Request,
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> User:
    settings = get_settings()

    user = await get_current_user_optional(request, db, credentials)

    if not user and settings.demo_mode:
        demo_user = await get_or_create_demo_user(db, settings.demo_user_id)
        return demo_user

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please provide a valid Firebase token."
        )
    return user


async def get_or_create_demo_user(db: Session, demo_user_id: str) -> User:
    from ..models.user import User

    existing_user = db.query(User).filter(User.user_id == demo_user_id).first()
    if existing_user:
        return existing_user

    demo_user = User(
        user_id=demo_user_id,
        firebase_uid=f"demo-{demo_user_id}",
        email="demo@example.com",
        full_name="Demo User"
    )
    db.add(demo_user)
    db.commit()
    db.refresh(demo_user)
    return demo_user


async def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[User]:
    try:
        if not credentials or not credentials.credentials:
            return None

        firebase_data = verify_firebase_token(credentials.credentials)
        if not firebase_data:
            return None

        firebase_uid = firebase_data.get("uid")
        email = firebase_data.get("email")
        name = firebase_data.get("name", firebase_data.get("email", "Unknown User"))

        if not firebase_uid or not email:
            return None

        try:
            return await get_or_create_user(
                db=db,
                firebase_uid=firebase_uid,
                email=email,
                full_name=name,
                date_of_birth=None
            )
        except Exception:
            existing_user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
            return existing_user

    except Exception:
        return None


async def get_or_create_anonymous_user(db: Session) -> User:
    """Create or return an anonymous user for when authentication is disabled"""
    anonymous_user_id = "anonymous-user"

    existing_user = db.query(User).filter(User.user_id == anonymous_user_id).first()
    if existing_user:
        return existing_user

    anonymous_user = User(
        user_id=anonymous_user_id,
        firebase_uid="anonymous",
        email="anonymous@example.com",
        full_name="Anonymous User"
    )
    db.add(anonymous_user)
    db.commit()
    db.refresh(anonymous_user)
    return anonymous_user


async def get_current_user_conditional(
    request: Request,
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> User:
    """
    Conditional authentication dependency that enforces auth based on settings.
    - If authentication_enabled=True: requires valid auth (like get_current_user_required)
    - If authentication_enabled=False: returns anonymous user without requiring auth
    """
    settings = get_settings()

    if not settings.authentication_enabled:
        # Auth disabled - return anonymous user
        return await get_or_create_anonymous_user(db)

    # Auth enabled - use existing required auth logic
    return await get_current_user_required(request, db, credentials)


async def get_current_user_optional_conditional(
    request: Request,
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[User]:
    """
    Conditional optional authentication dependency.
    - If authentication_enabled=True: behaves like get_current_user_optional
    - If authentication_enabled=False: returns anonymous user (never None)
    """
    settings = get_settings()

    if not settings.authentication_enabled:
        # Auth disabled - return anonymous user
        return await get_or_create_anonymous_user(db)

    # Auth enabled - use existing optional auth logic
    return await get_current_user_optional(request, db, credentials)


# Legacy dependencies for backward compatibility during transition
def get_video_job_repository(db: Session = Depends(get_db)):
    # Temporary redirect to content job repository
    return ContentJobRepository(db)