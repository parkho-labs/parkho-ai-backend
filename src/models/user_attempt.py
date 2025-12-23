from datetime import datetime
from typing import Optional, Dict, Any, List
import json
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from ..core.database import Base


class UserAttempt(Base):
    """
    Model for tracking user attempts at PYQ exam papers
    """
    __tablename__ = "user_attempts"

    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("exam_papers.id"), nullable=True, index=True)  # Nullable for GCS papers
    user_identifier = Column(String(100), nullable=True, index=True)  # Optional user identification

    # Attempt results
    score = Column(Float, nullable=True)  # Actual score obtained
    total_marks = Column(Float, nullable=False)  # Total marks possible
    percentage = Column(Float, nullable=True)  # Percentage score
    time_taken_seconds = Column(Integer, nullable=True)  # Time taken to complete

    # Answer data stored as JSON
    answers = Column(Text, nullable=True)  # User's submitted answers

    # Attempt status
    is_completed = Column(Boolean, default=False, nullable=False)
    is_submitted = Column(Boolean, default=False, nullable=False)

    # Timestamps
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationship to exam paper
    exam_paper = relationship("ExamPaper", lazy="select")

    @property
    def answers_dict(self) -> Optional[Dict[str, Any]]:
        """Parse answers JSON and return as dict"""
        if self.answers:
            try:
                return json.loads(self.answers)
            except json.JSONDecodeError:
                return None
        return None

    @answers_dict.setter
    def answers_dict(self, value: Optional[Dict[str, Any]]):
        """Set answers as JSON"""
        if value is not None:
            self.answers = json.dumps(value)
        else:
            self.answers = None

    def set_user_answers(self, answers: Dict[int, str]):
        """
        Set user answers for the attempt

        Args:
            answers: Dict mapping question_id -> selected_answer
        """
        self.answers_dict = {
            "submitted_answers": answers,
            "total_attempted": len(answers)
        }

    def get_user_answers(self) -> Dict[int, str]:
        """Get user's submitted answers"""
        answers_data = self.answers_dict
        if answers_data and "submitted_answers" in answers_data:
            return answers_data["submitted_answers"]
        return {}

    def calculate_score(self, correct_answers: Dict[int, str]) -> Dict[str, Any]:
        """
        Calculate score based on correct answers

        Args:
            correct_answers: Dict mapping question_id -> correct_answer

        Returns:
            Dict with score details
        """
        user_answers = self.get_user_answers()

        correct_count = 0
        incorrect_count = 0
        unattempted_count = 0
        total_questions = len(correct_answers)

        # Calculate correct/incorrect answers
        for question_id, correct_answer in correct_answers.items():
            user_answer = user_answers.get(question_id)

            if user_answer is None:
                unattempted_count += 1
            elif user_answer.strip() == correct_answer.strip():
                correct_count += 1
            else:
                incorrect_count += 1

        # Calculate score (assuming 1 mark per question for now)
        # This can be enhanced to read marks from question data
        score = correct_count
        percentage = (score / self.total_marks * 100) if self.total_marks > 0 else 0

        return {
            "score": score,
            "percentage": round(percentage, 2),
            "correct_count": correct_count,
            "incorrect_count": incorrect_count,
            "unattempted_count": unattempted_count,
            "total_questions": total_questions
        }

    def submit_attempt(self, answers: Dict[int, str], correct_answers: Dict[int, str]):
        """
        Submit the attempt with answers and calculate score

        Args:
            answers: User's submitted answers
            correct_answers: Correct answers for scoring
        """
        # Set user answers
        self.set_user_answers(answers)

        # Calculate score
        score_data = self.calculate_score(correct_answers)

        # Update attempt with scores
        self.score = score_data["score"]
        self.percentage = score_data["percentage"]
        self.is_completed = True
        self.is_submitted = True
        self.submitted_at = datetime.utcnow()

        # Calculate time taken if started_at is available
        if self.started_at:
            time_diff = datetime.utcnow() - self.started_at
            self.time_taken_seconds = int(time_diff.total_seconds())

    def get_detailed_results(self, exam_questions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get detailed results including question-wise analysis

        Args:
            exam_questions: List of questions from exam paper

        Returns:
            Detailed results with question-wise breakdown
        """
        user_answers = self.get_user_answers()

        question_results = []
        for question in exam_questions:
            question_id = question.get("id")
            correct_answer = question.get("correct_answer")
            user_answer = user_answers.get(question_id)

            is_correct = user_answer == correct_answer if user_answer else False
            is_attempted = user_answer is not None

            question_results.append({
                "question_id": question_id,
                "question_text": question.get("question_text", ""),
                "correct_answer": correct_answer,
                "user_answer": user_answer,
                "is_correct": is_correct,
                "is_attempted": is_attempted,
                "marks": question.get("marks", 1)
            })

        return {
            "attempt_id": self.id,
            "paper_id": self.paper_id,
            "score": self.score,
            "percentage": self.percentage,
            "total_marks": self.total_marks,
            "time_taken_seconds": self.time_taken_seconds,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "question_results": question_results
        }

    @property
    def display_time_taken(self) -> str:
        """Format time taken for display"""
        if not self.time_taken_seconds:
            return "N/A"

        hours = self.time_taken_seconds // 3600
        minutes = (self.time_taken_seconds % 3600) // 60
        seconds = self.time_taken_seconds % 60

        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"

    def __repr__(self):
        return f"<UserAttempt(id={self.id}, paper_id={self.paper_id}, score={self.score}, completed={self.is_completed})>"