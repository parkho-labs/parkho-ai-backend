from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any

from ...dependencies import get_analytics_service, get_current_user_conditional, get_current_user_conditional, get_content_job_repository
from ....services.analytics_service import AnalyticsService
from ....models.user import User

router = APIRouter()


#TODO Chnange the respone type to a model
@router.get("/user/quiz-history")
async def get_user_quiz_history(
    limit: int = 10,
    current_user: User = Depends(get_current_user_conditional),
    analytics: AnalyticsService = Depends(get_analytics_service)
) -> List[Dict[str, Any]]:
    events = analytics.get_user_quiz_history(current_user.user_id, limit)
    return [
        {
            "quiz_id": event.properties["quiz_id"],
            "score": event.properties["score"],
            "duration_seconds": event.properties.get("duration_seconds", 0),
            "completed_at": event.timestamp.isoformat()
        }
        for event in events
    ]


@router.get("/user/stats")
async def get_user_stats(
    current_user: User = Depends(get_current_user_conditional),
    analytics: AnalyticsService = Depends(get_analytics_service)
) -> Dict[str, Any]:
    return analytics.get_user_stats(current_user.user_id)


@router.get("/law/stats")
async def get_law_stats(
    user_id: str,
    analytics: AnalyticsService = Depends(get_analytics_service)
) -> Dict[str, Any]:
    """Get statistics for law/legal quizzes (generated, correct answers, etc.)"""
    return analytics.get_law_stats(user_id)


@router.get("/user/metrics")
async def get_user_activity_metrics(
    user_id: str,
    analytics: AnalyticsService = Depends(get_analytics_service)
) -> Dict[str, Any]:
    """Get user activity metrics (streak, daily login count, etc.)"""
    return analytics.get_user_activity_metrics(user_id)


@router.get("/user/mastery")
async def get_user_mastery_stats(
    user_id: str,
    analytics: AnalyticsService = Depends(get_analytics_service)
) -> Dict[str, Any]:
    """Get concept mastery and weak/strong subjects"""
    return analytics.get_mastery_stats(user_id)


@router.get("/quiz/{quiz_id}/performance")
async def get_quiz_performance(
    quiz_id: int,
    current_user: User = Depends(get_current_user_conditional),
    job_repo = Depends(get_content_job_repository),
    analytics: AnalyticsService = Depends(get_analytics_service)
) -> Dict[str, Any]:
    job = job_repo.get(quiz_id)
    if not job or job.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Quiz not found")

    return analytics.get_quiz_analytics(quiz_id)