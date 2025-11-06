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