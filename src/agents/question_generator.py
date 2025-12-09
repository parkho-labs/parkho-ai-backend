import json
import time
from typing import Dict, Any, List, Optional
import structlog

from .base import ContentTutorAgent
from ..services.question_generation_service import question_generation_service
from ..repositories.quiz_repository import QuizRepository
from ..repositories.quiz_repository import QuizRepository
from ..core.database import SessionLocal
from ..services.memory_service import memory_service

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
            user_id = data.get("user_id")
            
            user_profile = ""
            if user_id:
                try:
                    user_profile = memory_service.get_user_profile(user_id)
                    logger.info("injected_user_profile", user_id=user_id, profile_length=len(user_profile))
                except Exception as e:
                    logger.warning("failed_to_inject_profile", error=str(e))

            agent_result = await question_generation_service.generate_questions(
                subject=subject_type,
                content=content,
                question_config=question_config,
                difficulty_level=difficulty_level,
                user_profile=user_profile
            )

            all_questions = agent_result.get("questions", [])
            
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
        """Backwards-compatible batch save for generated questions."""
        await self.save_questions_bulk(job_id, questions)

    async def save_questions_bulk(self, job_id: int, questions: List[Dict[str, Any]]):
        """Insert all questions for a job in a single transaction."""
        if not questions:
            return

        db = SessionLocal()
        try:
            quiz_repo = QuizRepository(db)
            questions_data = [self._build_question_payload(job_id, q, idx) for idx, q in enumerate(questions)]
            quiz_repo.create_questions_batch(questions_data)
        except Exception:
            db.rollback()
            logger.error("Failed to save quiz questions in bulk", job_id=job_id, exc_info=True)
            raise
        finally:
            db.close()

    async def save_question(self, job_id: int, question: Dict[str, Any], index: int = 0):
        """Single-question save (used for compatibility/fallback)."""
        db = SessionLocal()
        try:
            quiz_repo = QuizRepository(db)
            payload = self._build_question_payload(job_id, question, index)
            quiz_repo.create_questions_batch([payload])
        except Exception:
            db.rollback()
            logger.error("Failed to save single quiz question", job_id=job_id, exc_info=True)
            raise
        finally:
            db.close()

    def _build_question_payload(self, job_id: int, question: Dict[str, Any], index: int) -> Dict[str, Any]:
        # Handle answer_config - prefer top-level, then merge/fallback to question_config
        answer_config = question.get("answer_config", {}).copy() if question.get("answer_config") else {}
        
        q_config = question.get("question_config", {})
        if q_config and isinstance(q_config, dict):
            # If options are in question_config but not answer_config, copy them
            if "options" in q_config and "options" not in answer_config:
                answer_config["options"] = q_config["options"]
            # If correct_answer is in question_config but not answer_config
            if "correct_answer" in q_config and "correct_answer" not in answer_config:
                answer_config["correct_answer"] = q_config["correct_answer"]

        # Extract type - separate logic to try top-level first (common in direct strategies), then question_config
        question_type = question.get("type")
        if not question_type:
            question_type = q_config.get("type") if q_config else None

        question_metadata: Optional[Dict[str, Any]] = None
        if "metadata" in question and question["metadata"]:
            question_metadata = question["metadata"].copy()

        return {
            "job_id": job_id,
            "question_id": question.get("question_id", f"q{index+1}"),
            "question": question.get("question", ""),
            "type": question_type,
            "answer_config": answer_config,
            "question_metadata": question_metadata,
            "context": question.get("context", ""),
            "max_score": question.get("max_score", 1),
        }

