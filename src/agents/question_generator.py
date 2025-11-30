import json
import time
from typing import Dict, Any, List
import structlog

from .base import ContentTutorAgent
from ..services.question_generation_service import question_generation_service
from ..repositories.quiz_repository import QuizRepository
from ..core.database import SessionLocal

logger = structlog.get_logger(__name__)


class QuestionGeneratorAgent(ContentTutorAgent):
    def __init__(self):
        super().__init__("question_generator")

    async def run(self, job_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("=== QUESTION GENERATOR START ===")
        logger.info(f"AGENT ROUTING: Job {job_id} using QuestionGeneratorAgent", job_id=job_id, agent_type="QuestionGeneratorAgent")
        logger.info(f"Job ID: {job_id}")
        logger.info(f"Data keys: {list(data.keys())}")

        transcript = data.get("transcript")
        title = data.get("title", "")
        rag_context = data.get("rag_context", "")
        subject_type = data.get("subject_type", "general")

        question_config = self._parse_question_config(data)
        logger.info(f"Question config: {question_config}")
        logger.info(f"Subject type: {subject_type}")

        if not transcript:
            logger.error("No transcript available for question generation")
            raise ValueError("No transcript available for question generation")

        try:
            await self.update_job_progress(job_id, 80.0, "Generating questions")

            content = f"{rag_context}\n\n{transcript}" if rag_context else transcript
            difficulty_level = data.get("difficulty_level", "intermediate")

            agent_result = await question_generation_service.generate_questions(
                subject=subject_type,
                content=content,
                question_config=question_config,
                difficulty_level=difficulty_level
            )

            all_questions = agent_result.get("questions", [])
            await self.update_job_progress(job_id, 90.0, "Saving questions")
            await self.save_quiz_questions(job_id, all_questions)

            data["questions"] = all_questions
            data["total_questions"] = len(all_questions)
            data["total_score"] = len(all_questions)

            return data

        except Exception as e:
            error_msg = f"Question generation failed: {str(e)}"
            logger.error(error_msg, job_id=job_id, exc_info=True)
            await self.mark_job_failed(job_id, error_msg)
            raise

    def _parse_question_config(self, data: Dict[str, Any]) -> Dict[str, int]:
        question_types = data.get("question_types", {})

        if isinstance(question_types, dict) and question_types:
            return question_types
        else:
            raise ValueError("question_types must be a dictionary with counts: {'multiple_choice': 5, 'true_false': 3}")


    async def save_quiz_questions(self, job_id: int, questions: List[Dict[str, Any]]):
        db = SessionLocal()
        try:
            quiz_repo = QuizRepository(db)

            questions_data = []
            for i, q in enumerate(questions):
                # Store options in answer_config for storage
                answer_config = q["answer_config"].copy()
                if "question_config" in q and "options" in q["question_config"]:
                    answer_config["options"] = q["question_config"]["options"]

                # Store metadata separately in question_metadata field
                question_metadata = None
                if "metadata" in q and q["metadata"]:
                    question_metadata = q["metadata"].copy()

                question_data = {
                    "job_id": job_id,
                    "question_id": q.get("question_id", f"q{i+1}"),
                    "question": q["question"],
                    "type": q["question_config"]["type"],
                    "answer_config": answer_config,
                    "question_metadata": question_metadata,
                    "context": q.get("context", ""),
                    "max_score": q.get("max_score", 1)
                }
                questions_data.append(question_data)

            if questions_data:
                quiz_repo.create_questions_batch(questions_data)

        except Exception:
            db.rollback()
            logger.error("Failed to save quiz questions", job_id=job_id, exc_info=True)
            raise
        finally:
            db.close()

