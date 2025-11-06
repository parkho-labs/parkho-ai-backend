import json
from typing import Dict, Any, List
import structlog

import openai

from .base import ContentTutorAgent
from ..config import get_settings
from ..models.content_job import ContentJob
from ..repositories.quiz_repository import QuizRepository
from ..core.database import SessionLocal
from ..services.llm_service import LLMService

settings = get_settings()
logger = structlog.get_logger(__name__)


class QuestionGeneratorAgent(ContentTutorAgent):
    def __init__(self):
        super().__init__("question_generator")

        # Initialize multi-provider LLM service
        self.llm_service = LLMService(
            openai_api_key=settings.openai_api_key,
            anthropic_api_key=settings.anthropic_api_key,
            google_api_key=settings.google_api_key
        )


    def get_model_client(self):
        return openai.OpenAI(api_key=settings.openai_api_key)


    async def run(self, job_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        transcript = data.get("transcript")
        content_analysis = data.get("content_analysis", {})
        key_concepts = data.get("key_concepts", [])

        question_types = data.get("question_types", ["multiple_choice", "true_false"])
        difficulty_level = data.get("difficulty_level", "intermediate")
        num_questions = data.get("num_questions", 10)

        if not transcript:
            raise ValueError("No transcript available for question generation")

        logger.info(f"QuestionGenerator received data keys: {list(data.keys())}")
        logger.info(f"Transcript length: {len(transcript) if transcript else 0}")
        logger.info(f"Question types: {question_types}, Num questions: {num_questions}")

        try:
            await self.update_job_progress(job_id, 80.0, "Generating questions")

            questions = await self.generate_questions(
                transcript, content_analysis, key_concepts,
                question_types, difficulty_level, num_questions
            )

            await self.update_job_progress(job_id, 90.0, "Question generation completed")
            await self.save_quiz_questions(job_id, questions)
            data["questions"] = questions
            return data

        except Exception as e:
            await self.mark_job_failed(job_id, f"Question generation failed: {str(e)}")
            raise

    async def generate_questions(self, transcript: str, content_analysis: Dict[str, Any],
                                key_concepts: List[Dict[str, Any]], question_types: List[str],
                                difficulty_level: str, num_questions: int) -> List[Dict[str, Any]]:

        question_counts = {
            "multiple_choice": 5,
            "true_false": 3,
            "short_answer": 2
        }

        if "short_answer" in question_types:
            question_counts["multiple_choice"] = 5
            question_counts["true_false"] = 3
        else:
            question_counts["multiple_choice"] = 6
            question_counts["true_false"] = 4

        all_questions = []
        question_id_counter = 1

        for question_type in question_types:
            count = question_counts.get(question_type, 1)
            questions = await self.generate_questions_by_type(
                transcript, content_analysis, key_concepts,
                question_type, difficulty_level, count
            )

            for q in questions:
                q["question_id"] = f"q{question_id_counter}"
                question_id_counter += 1

            all_questions.extend(questions)

        return all_questions

    async def generate_questions_by_type(self, transcript: str, content_analysis: Dict[str, Any],
                                        key_concepts: List[Dict[str, Any]], question_type: str,
                                        difficulty_level: str, num_questions: int) -> List[Dict[str, Any]]:

        if question_type == "multiple_choice":
            return await self.generate_mcq(transcript, content_analysis, difficulty_level, num_questions)
        elif question_type == "true_false":
            return await self.generate_true_false(transcript, content_analysis, difficulty_level, num_questions)
        elif question_type == "short_answer":
            return await self.generate_short_answer(transcript, key_concepts, difficulty_level, num_questions)
        elif question_type == "long_form":
            return await self.generate_long_form(transcript, content_analysis, difficulty_level, num_questions)
        else:
            return []

    async def generate_mcq(self, transcript: str, content_analysis: Dict[str, Any],
                          difficulty_level: str, num_questions: int) -> List[Dict[str, Any]]:

        system_prompt = f"""Generate {num_questions} multiple-choice questions based on the content. Each question should be {difficulty_level} level and have:
- question: the question text
- answer_config: object with options array, correct_answer, and reason
- context: relevant excerpt from content
- max_score: 1

Return as JSON array in this exact format:
[{{"question": "...", "answer_config": {{"options": ["A", "B", "C", "D"], "correct_answer": "A", "reason": "..."}}, "context": "...", "max_score": 1}}]"""

        content_summary = f"Main topics: {', '.join(content_analysis.get('main_topics', []))}"
        user_content = f"{content_summary}\n\nContent: {transcript[:3000]}"

        try:
            questions = await self.call_model(system_prompt, user_content)

            for q in questions:
                q["type"] = "multiple_choice"

            return questions if isinstance(questions, list) else []
        except Exception:
            return []

    async def generate_true_false(self, transcript: str, content_analysis: Dict[str, Any],
                                 difficulty_level: str, num_questions: int) -> List[Dict[str, Any]]:

        system_prompt = f"""Generate {num_questions} true/false questions based on the content. Each question should be {difficulty_level} level and have:
- question: the true/false statement
- answer_config: object with correct_answer ("true" or "false" as STRING) and reason
- context: relevant excerpt from content
- max_score: 1

IMPORTANT: correct_answer must be a string "true" or "false", NOT a boolean.

Return as JSON array in this exact format:
[{{"question": "...", "answer_config": {{"correct_answer": "true", "reason": "..."}}, "context": "...", "max_score": 1}}]"""

        content_summary = f"Main topics: {', '.join(content_analysis.get('main_topics', []))}"
        user_content = f"{content_summary}\n\nContent: {transcript[:3000]}"

        try:
            questions = await self.call_model(system_prompt, user_content)

            for q in questions:
                q["type"] = "true_false"
                # Normalize correct_answer to string if LLM returned boolean
                if "answer_config" in q and "correct_answer" in q["answer_config"]:
                    answer = q["answer_config"]["correct_answer"]
                    if isinstance(answer, bool):
                        q["answer_config"]["correct_answer"] = "true" if answer else "false"

            return questions if isinstance(questions, list) else []
        except Exception:
            return []

    async def generate_short_answer(self, transcript: str, key_concepts: List[Dict[str, Any]],
                                   difficulty_level: str, num_questions: int) -> List[Dict[str, Any]]:

        system_prompt = f"""Generate {num_questions} short-answer questions based on the content. Each question should be {difficulty_level} level and have:
- question: the question text
- answer_config: object with correct_answer and reason
- context: relevant excerpt from content
- max_score: 1

Return as JSON array in this exact format:
[{{"question": "...", "answer_config": {{"correct_answer": "...", "reason": "..."}}, "context": "...", "max_score": 1}}]"""

        concepts_summary = "\n".join([f"- {c.get('concept', '')}: {c.get('definition', '')}"
                                     for c in key_concepts[:5]])
        user_content = f"Key concepts:\n{concepts_summary}\n\nContent: {transcript[:3000]}"

        try:
            questions = await self.call_model(system_prompt, user_content)

            for q in questions:
                q["type"] = "short_answer"

            return questions if isinstance(questions, list) else []
        except Exception:
            return []

    async def generate_long_form(self, transcript: str, content_analysis: Dict[str, Any],
                                difficulty_level: str, num_questions: int) -> List[Dict[str, Any]]:

        system_prompt = f"""Generate {num_questions} long-form essay questions based on the content. Each question should be {difficulty_level} level and have:
- question: the question text
- correct_answer: key points that should be covered
- explanation: what makes a good answer
- topic: main topic this question covers

Return as JSON array."""

        learning_objectives = content_analysis.get('learning_objectives', [])
        objectives_text = "\n".join([f"- {obj}" for obj in learning_objectives])
        user_content = f"Learning objectives:\n{objectives_text}\n\nContent: {transcript[:3000]}"

        try:
            questions = await self.call_model(system_prompt, user_content)

            for q in questions:
                q["question_type"] = "long_form"
                q["difficulty"] = difficulty_level
                q["options"] = None

            return questions if isinstance(questions, list) else []
        except Exception:
            return []

    async def call_model(self, system_prompt: str, user_content: str) -> List[Dict[str, Any]]:
        client = self.get_model_client()

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ]
        )
        content = response.choices[0].message.content

        return json.loads(content)

    async def save_quiz_questions(self, job_id: int, questions: List[Dict[str, Any]]):
        db = SessionLocal()
        try:
            quiz_repo = QuizRepository(db)

            questions_data = []
            for i, q in enumerate(questions):
                question_data = {
                    "job_id": job_id,
                    "question_id": q.get("question_id", f"q{i+1}"),
                    "question": q["question"],
                    "type": q["type"],
                    "answer_config": q["answer_config"],
                    "context": q.get("context", ""),
                    "max_score": q.get("max_score", 1)
                }
                questions_data.append(question_data)

            quiz_repo.create_questions_batch(questions_data)

        except Exception:
            db.rollback()
            raise
        finally:
            db.close()