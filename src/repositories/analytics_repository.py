from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from ..models.user_event import UserEvent


class AnalyticsRepository:

    def __init__(self, session: Session):
        self.session = session

    def create_event(self, user_id: int, event_name: str, properties: Dict[str, Any]) -> UserEvent:
        event = UserEvent(
            user_id=user_id,
            event_name=event_name,
            properties=properties
        )
        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)
        return event

    def get_user_events(self, user_id: int, event_name: str, limit: int) -> List[UserEvent]:
        return (
            self.session.query(UserEvent)
            .filter(UserEvent.user_id == user_id, UserEvent.event_name == event_name)
            .order_by(desc(UserEvent.timestamp))
            .limit(limit)
            .all()
        )

    def get_quiz_performance(self, quiz_id: int):
        return (
            self.session.query(
                func.count(UserEvent.id).label('attempts'),
                func.avg(func.json_extract(UserEvent.properties, '$.score')).label('avg_score')
            )
            .filter(
                UserEvent.event_name == 'quiz_completed',
                func.json_extract(UserEvent.properties, '$.quiz_id') == str(quiz_id)
            )
            .first()
        )

    def get_user_quiz_count(self, user_id: int) -> int:
        return (
            self.session.query(UserEvent)
            .filter(UserEvent.user_id == user_id, UserEvent.event_name == 'quiz_completed')
            .count()
        )

    def get_law_quiz_stats(self, user_id: str) -> Dict[str, Any]:
        from ..models.user_attempt import UserAttempt
        import json

        # Only attempts that are NOT linked to a paper_id and have 'legal' or 'law' in metadata
        attempts = (
            self.session.query(UserAttempt)
            .filter(
                UserAttempt.user_identifier == user_id,
                UserAttempt.paper_id == None,
                UserAttempt.answers.contains('subject')
            ).all()
        )

        total_generated = len(attempts)
        completed = sum(1 for a in attempts if a.is_submitted)
        
        submitted_attempts = [a for a in attempts if a.is_submitted and a.percentage is not None]
        avg_score = sum(a.percentage for a in submitted_attempts) / len(submitted_attempts) if submitted_attempts else 0
        best_score = max((a.percentage for a in submitted_attempts), default=0)

        # Count total questions and correct ones
        total_q = 0
        total_correct = 0
        for a in submitted_attempts:
            if a.score is not None:
                total_correct += int(a.score)
            if a.total_marks is not None:
                total_q += int(a.total_marks)

        return {
            "quizzes_generated": total_generated,
            "quizzes_completed": completed,
            "total_questions": total_q,
            "correct_answers": total_correct,
            "average_score": round(avg_score, 2),
            "best_score": round(best_score, 2)
        }

    def get_user_activity_metrics(self, user_id: str) -> Dict[str, Any]:
        from ..models.user_attempt import UserAttempt
        from ..models.user_event import UserEvent
        from datetime import datetime
        from sqlalchemy import distinct, cast, Date

        # Get unique active days from both attempts and events
        attempt_days = self.session.query(cast(UserAttempt.started_at, Date)).filter(UserAttempt.user_identifier == user_id).distinct()
        event_days = self.session.query(cast(UserEvent.timestamp, Date)).filter(UserEvent.user_id == user_id).distinct()
        
        all_days = sorted(set([d[0] for d in attempt_days.all() if d[0]] + [d[0] for d in event_days.all() if d[0]]), reverse=True)
        
        total_active_days = len(all_days)
        last_active = all_days[0] if all_days else None
        
        # Streak calculation
        day_streak = 0
        if all_days:
            from datetime import timedelta
            current_date = datetime.now().date()
            expected_date = current_date
            
            for adate in all_days:
                if adate == expected_date or adate == expected_date - timedelta(days=1):
                    day_streak += 1
                    expected_date = adate - timedelta(days=1)
                else:
                    break

        login_count = self.session.query(UserEvent).filter(
            UserEvent.user_id == user_id,
            UserEvent.event_name.in_(['login', 'session_started'])
        ).count()

        return {
            "streak_days": day_streak,
            "total_active_days": total_active_days,
            "last_active": last_active.isoformat() if last_active else None,
            "daily_login_count": login_count
        }

    def get_concept_mastery_stats(self, user_id: str) -> List[Dict[str, Any]]:
        from ..models.user_attempt import UserAttempt
        import json

        attempts = (
            self.session.query(UserAttempt)
            .filter(
                UserAttempt.user_identifier == user_id,
                UserAttempt.is_submitted == True
            ).all()
        )

        concept_stats = {}

        for a in attempts:
            try:
                data = json.loads(a.answers)
                # This assumes detailed_results or started_questions has concept info
                # If using RAG questions, they might have concepts in metadata
                results = data.get("detailed_results", {}).get("question_results", [])
                if not results and "started_questions" in data:
                    # If results not in metadata, check if we have submitted_answers
                    # This is complex, but let's try to find concepts
                    pass
                
                for r in results:
                    concepts = r.get("concepts", ["General"])
                    is_correct = r.get("is_correct", False)
                    
                    for c in concepts:
                        if c not in concept_stats:
                            concept_stats[c] = {"total": 0, "correct": 0}
                        concept_stats[c]["total"] += 1
                        if is_correct:
                            concept_stats[c]["correct"] += 1
            except:
                continue

        mastery = []
        for concept, stats in concept_stats.items():
            mastery.append({
                "concept_name": concept,
                "total_questions": stats["total"],
                "correct_questions": stats["correct"],
                "mastery_percentage": round((stats["correct"] / stats["total"] * 100), 2) if stats["total"] > 0 else 0
            })
        
        return sorted(mastery, key=lambda x: x["mastery_percentage"], reverse=True)