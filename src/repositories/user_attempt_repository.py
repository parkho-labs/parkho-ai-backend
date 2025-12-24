from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, and_, or_, func
from datetime import datetime, timedelta

from ..models.user_attempt import UserAttempt
from ..models.exam_paper import ExamPaper


class UserAttemptRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, user_attempt: UserAttempt) -> UserAttempt:
        """Create a new user attempt"""
        self.session.add(user_attempt)
        self.session.commit()
        self.session.refresh(user_attempt)
        return user_attempt

    def get_by_id(self, attempt_id: int) -> Optional[UserAttempt]:
        """Get user attempt by ID with exam paper details"""
        return (
            self.session.query(UserAttempt)
            .options(joinedload(UserAttempt.exam_paper))
            .filter(UserAttempt.id == attempt_id)
            .first()
        )

    def get_by_paper_and_user(
        self,
        paper_id: int,
        user_identifier: Optional[str] = None
    ) -> List[UserAttempt]:
        """Get all attempts for a specific paper and user"""
        query = (
            self.session.query(UserAttempt)
            .options(joinedload(UserAttempt.exam_paper))
            .filter(UserAttempt.paper_id == paper_id)
        )

        if user_identifier:
            query = query.filter(UserAttempt.user_identifier == user_identifier)

        return query.order_by(desc(UserAttempt.started_at)).all()

    def get_user_attempts(
        self,
        user_identifier: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[UserAttempt]:
        """Get all attempts by a specific user"""
        return (
            self.session.query(UserAttempt)
            .options(joinedload(UserAttempt.exam_paper))
            .filter(UserAttempt.user_identifier == user_identifier)
            .order_by(desc(UserAttempt.started_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_completed_attempts(
        self,
        user_identifier: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[UserAttempt]:
        """Get completed attempts, optionally filtered by user"""
        query = (
            self.session.query(UserAttempt)
            .options(joinedload(UserAttempt.exam_paper))
            .filter(UserAttempt.is_completed == True)
        )

        if user_identifier:
            query = query.filter(UserAttempt.user_identifier == user_identifier)

        return (
            query.order_by(desc(UserAttempt.submitted_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_incomplete_attempts(
        self,
        user_identifier: Optional[str] = None,
        older_than_hours: int = 24
    ) -> List[UserAttempt]:
        """Get incomplete attempts, optionally filter by user and age"""
        cutoff_time = datetime.utcnow() - timedelta(hours=older_than_hours)

        query = (
            self.session.query(UserAttempt)
            .options(joinedload(UserAttempt.exam_paper))
            .filter(
                and_(
                    UserAttempt.is_completed == False,
                    UserAttempt.started_at < cutoff_time
                )
            )
        )

        if user_identifier:
            query = query.filter(UserAttempt.user_identifier == user_identifier)

        return query.order_by(desc(UserAttempt.started_at)).all()

    def get_user_best_score(self, user_identifier: str, paper_id: int) -> Optional[UserAttempt]:
        """Get user's best scoring attempt for a specific paper"""
        return (
            self.session.query(UserAttempt)
            .options(joinedload(UserAttempt.exam_paper))
            .filter(
                and_(
                    UserAttempt.user_identifier == user_identifier,
                    UserAttempt.paper_id == paper_id,
                    UserAttempt.is_completed == True
                )
            )
            .order_by(desc(UserAttempt.score))
            .first()
        )

    def get_user_latest_attempt(self, user_identifier: str, paper_id: int) -> Optional[UserAttempt]:
        """Get user's most recent attempt for a specific paper"""
        return (
            self.session.query(UserAttempt)
            .options(joinedload(UserAttempt.exam_paper))
            .filter(
                and_(
                    UserAttempt.user_identifier == user_identifier,
                    UserAttempt.paper_id == paper_id
                )
            )
            .order_by(desc(UserAttempt.started_at))
            .first()
        )

    def get_user_performance_stats(self, user_identifier: str) -> dict:
        """Get user's overall performance statistics"""
        # Total attempts
        total_attempts = (
            self.session.query(UserAttempt)
            .filter(UserAttempt.user_identifier == user_identifier)
            .count()
        )

        # Completed attempts
        completed_attempts = (
            self.session.query(UserAttempt)
            .filter(
                and_(
                    UserAttempt.user_identifier == user_identifier,
                    UserAttempt.is_completed == True
                )
            )
            .count()
        )

        # Average score and percentage
        score_stats = (
            self.session.query(
                func.avg(UserAttempt.score).label('avg_score'),
                func.avg(UserAttempt.percentage).label('avg_percentage'),
                func.max(UserAttempt.score).label('best_score'),
                func.max(UserAttempt.percentage).label('best_percentage')
            )
            .filter(
                and_(
                    UserAttempt.user_identifier == user_identifier,
                    UserAttempt.is_completed == True
                )
            )
            .first()
        )

        # Average time taken
        avg_time = (
            self.session.query(func.avg(UserAttempt.time_taken_seconds))
            .filter(
                and_(
                    UserAttempt.user_identifier == user_identifier,
                    UserAttempt.is_completed == True
                )
            )
            .scalar()
        )

        return {
            "total_attempts": total_attempts,
            "completed_attempts": completed_attempts,
            "completion_rate": (completed_attempts / total_attempts * 100) if total_attempts > 0 else 0,
            "average_score": float(score_stats.avg_score) if score_stats.avg_score else 0,
            "average_percentage": float(score_stats.avg_percentage) if score_stats.avg_percentage else 0,
            "best_score": float(score_stats.best_score) if score_stats.best_score else 0,
            "best_percentage": float(score_stats.best_percentage) if score_stats.best_percentage else 0,
            "average_time_seconds": int(avg_time) if avg_time else 0
        }

    def get_paper_performance_stats(self, paper_id: int) -> dict:
        """Get performance statistics for a specific paper"""
        # Total attempts for this paper
        total_attempts = (
            self.session.query(UserAttempt)
            .filter(UserAttempt.paper_id == paper_id)
            .count()
        )

        # Completed attempts
        completed_attempts = (
            self.session.query(UserAttempt)
            .filter(
                and_(
                    UserAttempt.paper_id == paper_id,
                    UserAttempt.is_completed == True
                )
            )
            .count()
        )

        # Score statistics
        score_stats = (
            self.session.query(
                func.avg(UserAttempt.score).label('avg_score'),
                func.avg(UserAttempt.percentage).label('avg_percentage'),
                func.max(UserAttempt.score).label('highest_score'),
                func.min(UserAttempt.score).label('lowest_score'),
                func.stddev(UserAttempt.score).label('score_stddev')
            )
            .filter(
                and_(
                    UserAttempt.paper_id == paper_id,
                    UserAttempt.is_completed == True
                )
            )
            .first()
        )

        return {
            "paper_id": paper_id,
            "total_attempts": total_attempts,
            "completed_attempts": completed_attempts,
            "completion_rate": (completed_attempts / total_attempts * 100) if total_attempts > 0 else 0,
            "average_score": float(score_stats.avg_score) if score_stats.avg_score else 0,
            "average_percentage": float(score_stats.avg_percentage) if score_stats.avg_percentage else 0,
            "highest_score": float(score_stats.highest_score) if score_stats.highest_score else 0,
            "lowest_score": float(score_stats.lowest_score) if score_stats.lowest_score else 0,
            "score_std_deviation": float(score_stats.score_stddev) if score_stats.score_stddev else 0
        }

    def update(self, user_attempt: UserAttempt) -> UserAttempt:
        """Update an existing user attempt"""
        self.session.commit()
        self.session.refresh(user_attempt)
        return user_attempt

    def delete(self, attempt_id: int) -> bool:
        """Delete a user attempt"""
        attempt = self.get_by_id(attempt_id)
        if attempt:
            self.session.delete(attempt)
            self.session.commit()
            return True
        return False

    def cleanup_old_incomplete_attempts(self, older_than_hours: int = 24) -> int:
        """Remove old incomplete attempts and return count of deleted attempts"""
        cutoff_time = datetime.utcnow() - timedelta(hours=older_than_hours)

        deleted_count = (
            self.session.query(UserAttempt)
            .filter(
                and_(
                    UserAttempt.is_completed == False,
                    UserAttempt.started_at < cutoff_time
                )
            )
            .delete()
        )

        self.session.commit()
        return deleted_count

    def start_new_attempt(self, paper_id: int, user_identifier: Optional[str] = None) -> UserAttempt:
        """Start a new attempt for a user on a specific paper"""
        # Get the exam paper to set total_marks
        paper = self.session.query(ExamPaper).filter(ExamPaper.id == paper_id).first()
        if not paper:
            raise ValueError(f"Exam paper with ID {paper_id} not found")

        attempt = UserAttempt(
            paper_id=paper_id,
            user_identifier=user_identifier,
            total_marks=paper.total_marks,
            is_completed=False,
            is_submitted=False
        )

        return self.create(attempt)