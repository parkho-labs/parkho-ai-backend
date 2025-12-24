from datetime import datetime
from typing import Optional, Dict, Any, List
import json
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Boolean
from sqlalchemy.sql import func

from ..core.database import Base


class ExamPaper(Base):
    """
    Model for storing Previous Year Question (PYQ) papers
    """
    __tablename__ = "exam_papers"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    exam_name = Column(String(100), nullable=False, index=True)

    # Exam configuration
    total_questions = Column(Integer, nullable=False)
    total_marks = Column(Float, nullable=False)
    time_limit_minutes = Column(Integer, nullable=False, default=180)

    # Question data stored as JSON
    question_data = Column(Text, nullable=False)

    # Metadata
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    @property
    def questions(self) -> Optional[List[Dict[str, Any]]]:
        """Parse question_data JSON and return questions list"""
        if self.question_data:
            try:
                data = json.loads(self.question_data)
                return data.get("questions", [])
            except json.JSONDecodeError:
                return None
        return None

    @questions.setter
    def questions(self, value: Optional[List[Dict[str, Any]]]):
        """Set questions data as JSON"""
        if value is not None:
            # Ensure we maintain the full structure
            current_data = self.question_data_dict or {}
            current_data["questions"] = value
            self.question_data = json.dumps(current_data)
        else:
            self.question_data = json.dumps({"questions": []})

    @property
    def question_data_dict(self) -> Optional[Dict[str, Any]]:
        """Parse question_data JSON and return full structure"""
        if self.question_data:
            try:
                return json.loads(self.question_data)
            except json.JSONDecodeError:
                return None
        return None

    @question_data_dict.setter
    def question_data_dict(self, value: Optional[Dict[str, Any]]):
        """Set complete question data as JSON"""
        if value is not None:
            self.question_data = json.dumps(value)
        else:
            self.question_data = json.dumps({"questions": []})

    def set_question_data(
        self,
        questions: List[Dict[str, Any]],
        instructions: Optional[str] = None,
        marking_scheme: Optional[Dict[str, Any]] = None
    ):
        """Set complete question paper data"""
        data = {
            "questions": questions,
            "total_questions": len(questions),
            "total_marks": sum(q.get("marks", 1) for q in questions)
        }

        if instructions:
            data["instructions"] = instructions

        if marking_scheme:
            data["marking_scheme"] = marking_scheme

        self.question_data_dict = data
        self.total_questions = len(questions)
        self.total_marks = sum(q.get("marks", 1) for q in questions)

    def get_question_by_id(self, question_id: int) -> Optional[Dict[str, Any]]:
        """Get specific question by its ID"""
        questions = self.questions
        if questions:
            for question in questions:
                if question.get("id") == question_id:
                    return question
        return None

    def get_correct_answers(self) -> Dict[int, str]:
        """Get all correct answers mapping question_id -> correct_answer"""
        answers = {}
        questions = self.questions
        if questions:
            for question in questions:
                question_id = question.get("id")
                correct_answer = question.get("correct_answer")
                if question_id is not None and correct_answer is not None:
                    answers[question_id] = correct_answer
        return answers

    @property
    def display_name(self) -> str:
        """Generate display name for the exam paper"""
        return f"{self.exam_name} {self.year} - {self.title}"

    def __repr__(self):
        return f"<ExamPaper(id={self.id}, title='{self.title}', year={self.year}, exam='{self.exam_name}')>"