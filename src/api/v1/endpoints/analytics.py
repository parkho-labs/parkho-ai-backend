from fastapi import APIRouter, Depends
from typing import List, Dict, Any

from ...dependencies import get_analytics_service, get_current_user_optional
from ....services.analytics_service import AnalyticsService
from ....models.user import User

router = APIRouter()


#TODO Chnange the respone type to a model
@router.get("/user/quiz-history")
async def get_user_quiz_history(
    limit: int = 10,
    user_id: int = 1,  # Temporary hardcoded until auth is implemented
    analytics: AnalyticsService = Depends(get_analytics_service)
) -> List[Dict[str, Any]]:
    events = analytics.get_user_quiz_history(user_id, limit)
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
    user_id: int = 1,  # Temporary hardcoded until auth is implemented
    analytics: AnalyticsService = Depends(get_analytics_service)
) -> Dict[str, Any]:
    return analytics.get_user_stats(user_id)


@router.get("/quiz/{quiz_id}/performance")
async def get_quiz_performance(
    quiz_id: int,
    analytics: AnalyticsService = Depends(get_analytics_service)
) -> Dict[str, Any]:
    return analytics.get_quiz_analytics(quiz_id)