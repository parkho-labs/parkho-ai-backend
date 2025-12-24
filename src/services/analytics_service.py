from typing import Dict, Any, List, Optional
from datetime import datetime

from ..models.user_event import UserEvent
from ..repositories.analytics_repository import AnalyticsRepository


class AnalyticsService:

    def __init__(self, repo: AnalyticsRepository):
        self.repo = repo

    def track_quiz_start(self, user_id: int, quiz_id: int, session_id: Optional[str] = None) -> UserEvent:
        return self.repo.create_event(user_id, "quiz_started", {
            "quiz_id": quiz_id,
            "session_id": session_id,
            "started_at": datetime.utcnow().isoformat()
        })

    def track_quiz_completion(self, user_id: int, quiz_id: int, score: int, duration: int) -> UserEvent:
        return self.repo.create_event(user_id, "quiz_completed", {
            "quiz_id": quiz_id,
            "score": score,
            "duration_seconds": duration,
            "completed_at": datetime.utcnow().isoformat()
        })

    def get_user_quiz_history(self, user_id: int, limit: int = 10) -> List[UserEvent]:
        return self.repo.get_user_events(user_id, "quiz_completed", limit)

    def get_quiz_analytics(self, quiz_id: int) -> Dict[str, Any]:
        stats = self.repo.get_quiz_performance(quiz_id)
        return {
            "quiz_id": quiz_id,
            "total_attempts": stats.attempts or 0,
            "average_score": float(stats.avg_score or 0)
        }

    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        quiz_count = self.repo.get_user_quiz_count(user_id)
        return {
            "user_id": user_id,
            "total_quizzes_completed": quiz_count
        }

    def get_law_stats(self, user_id: str) -> Dict[str, Any]:
        return self.repo.get_law_quiz_stats(user_id)

    def get_user_activity_metrics(self, user_id: str) -> Dict[str, Any]:
        return self.repo.get_user_activity_metrics(user_id)

    def get_mastery_stats(self, user_id: str) -> Dict[str, Any]:
        mastery = self.repo.get_concept_mastery_stats(user_id)
        
        # Identify weak and strong subjects (top 3 and bottom 3)
        strong = [m["concept_name"] for m in mastery[:3] if m["mastery_percentage"] >= 70]
        weak = [m["concept_name"] for m in mastery[-3:] if m["mastery_percentage"] < 50]
        
        return {
            "concepts": mastery,
            "weak_subjects": weak,
            "strong_subjects": strong
        }