from typing import List, Dict, Any, Optional
import uuid
from ....models.quiz_question import QuizQuestion
from ....models.content_job import ContentJob


class QuizResponseMapper:
    """Maps database quiz questions to proper API response format"""

    @staticmethod
    def map_to_quiz_response(
        quiz_questions_db: List[QuizQuestion],
        job: ContentJob
    ) -> Dict[str, Any]:
        """
        Maps database quiz questions to the expected API response format
        """
        questions = []
        total_score = 0

        for q in quiz_questions_db:
            question_data = QuizResponseMapper._map_question(q)
            questions.append(question_data)
            total_score += q.max_score

        return {
            "quiz_id": str(uuid.uuid4()),
            "quiz_title": job.title or "Generated Quiz",
            "questions": questions,
            "total_questions": len(quiz_questions_db),
            "total_score": total_score,
            "summary": job.summary
        }

    @staticmethod
    def _map_question(q: QuizQuestion) -> Dict[str, Any]:
        """Maps a single quiz question to proper format"""

        # Build question_config structure
        question_config = {
            "type": q.type,
            "requires_diagram": QuizResponseMapper._extract_requires_diagram(q.answer_config)
        }

        # Add options for multiple choice questions only
        if q.type in ["multiple_choice", "multiple_correct"]:
            options = QuizResponseMapper._extract_options(q.answer_config)
            question_config["options"] = options

        # Add diagram info if available
        diagram_type = QuizResponseMapper._extract_diagram_type(q.answer_config)
        if diagram_type:
            question_config["diagram_type"] = diagram_type

        diagram_elements = QuizResponseMapper._extract_diagram_elements(q.answer_config)
        if diagram_elements:
            question_config["diagram_elements"] = diagram_elements

        # Build metadata structure from question_metadata field
        metadata = QuizResponseMapper._extract_metadata_from_question(q)

        return {
            "question_id": q.question_id,
            "question": q.question,
            "question_config": question_config,
            "metadata": metadata,
            "max_score": q.max_score
        }

    @staticmethod
    def _extract_options(answer_config: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Extract options from answer_config"""
        if answer_config and "options" in answer_config:
            return answer_config["options"]
        return None

    @staticmethod
    def _extract_requires_diagram(answer_config: Dict[str, Any]) -> bool:
        """Extract requires_diagram flag from answer_config"""
        if answer_config and "requires_diagram" in answer_config:
            return answer_config["requires_diagram"]
        return False

    @staticmethod
    def _extract_diagram_type(answer_config: Dict[str, Any]) -> Optional[str]:
        """Extract diagram_type from answer_config"""
        if answer_config and "diagram_type" in answer_config:
            return answer_config["diagram_type"]
        return None

    @staticmethod
    def _extract_diagram_elements(answer_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract diagram_elements from answer_config"""
        if answer_config and "diagram_elements" in answer_config:
            return answer_config["diagram_elements"]
        return None

    @staticmethod
    def _extract_metadata_from_question(q: QuizQuestion) -> Dict[str, Any]:
        """Extract metadata from question_metadata field"""
        metadata = {}

        # Read from the new question_metadata field
        if q.question_metadata:
            metadata = q.question_metadata.copy()

        return metadata