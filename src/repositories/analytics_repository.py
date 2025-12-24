from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from ..models.user_event import UserEvent
from ..models.collection import Collection
from ..models.uploaded_file import UploadedFile


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

    def get_library_stats(self, user_id: str) -> Dict[str, Any]:
        """Get stats for user's library usage"""
        # Count collections
        total_collections = self.session.query(Collection).filter(Collection.user_id == user_id).count()
        
        # Get collections to count files
        collections = self.session.query(Collection).filter(Collection.user_id == user_id).all()
        
        total_files = 0
        total_size_bytes = 0
        
        for col in collections:
            total_files += len(col.files)
            for f in col.files:
                total_size_bytes += (f.file_size or 0)
                
        return {
            "total_collections": total_collections,
            "total_documents": total_files,
            "total_storage_mb": round(total_size_bytes / (1024 * 1024), 2),
            "avg_docs_per_collection": round(total_files / total_collections, 1) if total_collections > 0 else 0
        }

    def get_detailed_law_stats(self, user_id: str) -> Dict[str, Any]:
        """Get law stats broken down by subject/act"""
        from ..models.user_attempt import UserAttempt
        import json
        
        attempts = (
            self.session.query(UserAttempt)
            .filter(
                UserAttempt.user_identifier == user_id,
                UserAttempt.paper_id == None,
                UserAttempt.answers.contains('subject')
            ).all()
        )
        
        subject_stats = {}
        
        for a in attempts:
            try:
                data = json.loads(a.answers) if a.answers else {}
                subject = data.get("subject", "Uncategorized")
                
                if subject not in subject_stats:
                    subject_stats[subject] = {
                        "attempts": 0, 
                        "completed": 0,
                        "total_questions": 0,
                        "correct": 0,
                        "total_score": 0
                    }
                
                stats = subject_stats[subject]
                stats["attempts"] += 1
                
                if a.is_submitted:
                    stats["completed"] += 1
                    stats["total_questions"] += int(a.total_marks or 0)
                    stats["correct"] += int(a.score or 0)
                    stats["total_score"] += (a.percentage or 0)
            except:
                continue
                
        # Finalize stats
        results = []
        for subject, stats in subject_stats.items():
            completed = stats["completed"]
            avg_score = round(stats["total_score"] / completed, 1) if completed > 0 else 0
            accuracy = round((stats["correct"] / stats["total_questions"] * 100), 1) if stats["total_questions"] > 0 else 0
            
            results.append({
                "subject": subject,
                "total_attempts": stats["attempts"],
                "completed_attempts": completed,
                "questions_solved": stats["total_questions"],
                "accuracy": accuracy,
                "average_score": avg_score
            })
            
        return {
            "breakdown": sorted(results, key=lambda x: x["completed_attempts"], reverse=True),
            "total_subjects_practiced": len(results)
        }

    def get_comprehensive_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get high-level stats aggregating everything"""
        from ..models.user_attempt import UserAttempt
        
        # All attempts (PYQ + Law)
        all_attempts = self.session.query(UserAttempt).filter(UserAttempt.user_identifier == user_id).all()
        
        submitted = [a for a in all_attempts if a.is_submitted]
        
        total_quizzes = len(submitted)
        total_questions = sum(int(a.total_marks or 0) for a in submitted)
        total_time_seconds = sum(int(a.time_taken_seconds or 0) for a in submitted)
        
        avg_score = sum(a.percentage or 0 for a in submitted) / total_quizzes if total_quizzes > 0 else 0
        
        return {
            "total_quizzes_completed": total_quizzes,
            "total_questions_answered": total_questions,
            "total_study_time_minutes": int(total_time_seconds / 60),
            "average_accuracy": round(avg_score, 1),
            "total_attempts_started": len(all_attempts)
        }