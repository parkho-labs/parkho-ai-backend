import json
import time
from typing import Dict, Any, List
import structlog

from .base import ContentTutorAgent
from .physics_tutor_agent import PhysicsTutorAgent
from ..repositories.quiz_repository import QuizRepository
from ..core.database import SessionLocal
from ..api.v1.schemas import QuestionType, QuestionTypeCount, QuestionCountsResponse, ContentSubject

logger = structlog.get_logger(__name__)


class QuestionGeneratorAgent(ContentTutorAgent):
    def __init__(self):
        super().__init__("question_generator")
        self.physics_tutor = PhysicsTutorAgent()

    def determine_subject_type(self, content: str) -> ContentSubject:
        content_lower = content.lower()

        physics_keywords = ["force", "energy", "momentum", "velocity", "acceleration", "gravity", "wave", "frequency", "quantum", "thermodynamics", "mechanics", "optics", "electromagnetic", "nuclear", "atom", "particle", "newton", "einstein", "physics", "kinematics", "dynamics"]
        math_keywords = ["equation", "algebra", "calculus", "geometry", "theorem", "function", "derivative", "integral", "matrix", "polynomial", "trigonometry", "statistics", "probability", "mathematics", "math"]
        chemistry_keywords = ["molecule", "reaction", "element", "compound", "bond", "atom", "periodic", "chemical", "solution", "acid", "base", "organic", "inorganic", "chemistry"]
        biology_keywords = ["cell", "organism", "DNA", "protein", "evolution", "species", "gene", "ecosystem", "bacteria", "virus", "tissue", "organ", "biology", "life"]

        if sum(1 for k in physics_keywords if k in content_lower) >= 3:
            return ContentSubject.PHYSICS
        if sum(1 for k in math_keywords if k in content_lower) >= 3:
            return ContentSubject.MATHEMATICS
        if sum(1 for k in chemistry_keywords if k in content_lower) >= 3:
            return ContentSubject.CHEMISTRY
        if sum(1 for k in biology_keywords if k in content_lower) >= 3:
            return ContentSubject.BIOLOGY

        return ContentSubject.GENERAL

    async def run(self, job_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"=== QUESTION GENERATOR START ===")
        logger.info(f"Job ID: {job_id}")
        logger.info(f"Data keys: {list(data.keys())}")

        transcript = data.get("transcript")
        title = data.get("title", "")
        rag_context = data.get("rag_context", "")
        num_questions = data.get("num_questions", 5)
        question_types = data.get("question_types", ["multiple_choice"])

        logger.info(f"Transcript length: {len(transcript) if transcript else 0}")
        logger.info(f"Title: {title}")
        logger.info(f"RAG context length: {len(rag_context) if rag_context else 0}")
        logger.info(f"Number of questions requested: {num_questions}")
        logger.info(f"Question types requested: {question_types}")

        if not transcript:
            logger.error("No transcript available for question generation")
            raise ValueError("No transcript available for question generation")

        try:
            await self.update_job_progress(job_id, 80.0, "Detecting subject and generating questions")

            start_time = time.time()
            print(f"[TIMER] Starting Subject Detection...")
            subject = self.determine_subject_type(f"{title} {transcript}")
            logger.info(f"Detected subject: {subject}")

            logger.info(f"=== CALLING PHYSICS TUTOR FOR {subject} ===")

            # Create context for LLM
            full_context = f"{rag_context}\n\n{transcript}" if rag_context else transcript
            logger.info(f"Full context length: {len(full_context)}")

            query = f"Generate {num_questions} {'/'.join(question_types)} quiz questions for: {title}"
            logger.info(f"Query: {query}")
            detection_time = time.time() - start_time
            print(f"[TIMER] Subject Detection: {detection_time:.3f}s")

            llm_start = time.time()
            print(f"[TIMER] Starting LLM Question Generation...")
            match subject:
                case ContentSubject.PHYSICS:
                    questions_data = await self.physics_tutor.generate_educational_questions(
                        query=query,
                        context=full_context,
                        job_id=job_id,
                        difficulty_level=data.get("difficulty_level", "intermediate"),
                        content_type=ContentSubject.PHYSICS
                    )
                    raw_questions = questions_data.get("questions", [])
                    logger.info(f"Physics LLM returned {len(raw_questions)} questions")
                    questions = self.convert_physics_format_to_standard(raw_questions)
                    logger.info(f"After conversion: {len(questions)} questions")
                case ContentSubject.MATHEMATICS:
                    questions_data = await self.physics_tutor.generate_educational_questions(
                        query=query,
                        context=full_context,
                        job_id=job_id,
                        difficulty_level=data.get("difficulty_level", "intermediate"),
                        content_type=ContentSubject.MATHEMATICS
                    )
                    questions = self.convert_physics_format_to_standard(questions_data.get("questions", []))
                case ContentSubject.CHEMISTRY:
                    questions_data = await self.physics_tutor.generate_educational_questions(
                        query=query,
                        context=full_context,
                        job_id=job_id,
                        difficulty_level=data.get("difficulty_level", "intermediate"),
                        content_type=ContentSubject.CHEMISTRY
                    )
                    questions = self.convert_physics_format_to_standard(questions_data.get("questions", []))
                case ContentSubject.BIOLOGY:
                    questions_data = await self.physics_tutor.generate_educational_questions(
                        query=query,
                        context=full_context,
                        job_id=job_id,
                        difficulty_level=data.get("difficulty_level", "intermediate"),
                        content_type=ContentSubject.BIOLOGY
                    )
                    questions = self.convert_physics_format_to_standard(questions_data.get("questions", []))
                case _:
                    questions_data = await self.physics_tutor.generate_educational_questions(
                        query=query,
                        context=full_context,
                        job_id=job_id,
                        difficulty_level=data.get("difficulty_level", "intermediate"),
                        content_type=ContentSubject.GENERAL
                    )
                    questions = self.convert_physics_format_to_standard(questions_data.get("questions", []))

            llm_time = time.time() - llm_start
            print(f"[TIMER] LLM Question Generation: {llm_time:.3f}s")

            await self.update_job_progress(job_id, 90.0, "Question generation completed")

            db_start = time.time()
            print(f"[TIMER] Starting Database Question Save...")
            logger.info(f"=== FINAL RESULTS ===")
            logger.info(f"Total questions generated: {len(questions)}")
            logger.info("Questions being saved", question_count=len(questions))

            await self.save_quiz_questions(job_id, questions)
            data["questions"] = questions
            data["num_questions"] = num_questions
            data["question_types"] = question_types

            db_time = time.time() - db_start
            print(f"[TIMER] Database Question Save: {db_time:.3f}s")

            logger.info(f"=== QUESTION GENERATOR END - SUCCESS ===")
            return data

        except Exception as e:
            await self.mark_job_failed(job_id, f"Question generation failed: {str(e)}")
            raise


    def convert_physics_format_to_standard(self, physics_questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        standard_questions = []

        for i, pq in enumerate(physics_questions):
            if not isinstance(pq, dict):
                continue

            if "question_config" in pq:
                question_config = pq.get("question_config", {})
                answer_config = pq.get("answer_config", {})
                question_text = question_config.get("question_text", "")
                options = answer_config.get("options", [])
                correct_answer = answer_config.get("correct_answer", "")
                explanation = answer_config.get("reason", "") or question_config.get("explanation", "")
                question_type = question_config.get("type", "")
            else:
                question_text = pq.get("question_text", "")
                options = pq.get("options", [])
                correct_answer = pq.get("correct_answer", "")
                explanation = pq.get("explanation", "")
                question_type = pq.get("type", "")

            if not question_text:
                continue

            if len(options) >= 4:
                options_dict = {
                    "A": options[0] if len(options) > 0 else "",
                    "B": options[1] if len(options) > 1 else "",
                    "C": options[2] if len(options) > 2 else "",
                    "D": options[3] if len(options) > 3 else ""
                }

                correct_letter = "A"
                if correct_answer in options:
                    answer_index = options.index(correct_answer)
                    correct_letter = ["A", "B", "C", "D"][answer_index]

                final_answer_config = {
                    "options": options_dict,
                    "correct_answer": correct_letter
                }
                question_type = question_type or "multiple_choice"
            else:
                final_answer_config = {
                    "correct_answer": correct_answer
                }
                question_type = question_type or "short_answer"

            standard_question = {
                "question_id": f"q{i+1}",
                "question": question_text,
                "type": question_type,
                "answer_config": final_answer_config,
                "context": explanation,
                "max_score": 1
            }

            standard_questions.append(standard_question)

        return standard_questions

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

            logger.info(
                "Saving quiz questions",
                job_id=job_id,
                question_count=len(questions_data)
            )
            if not questions_data:
                logger.warning("No questions to save", job_id=job_id)
                return

            quiz_repo.create_questions_batch(questions_data)
            logger.info("Quiz questions saved", job_id=job_id, question_ids=[q["question_id"] for q in questions_data])

        except Exception:
            db.rollback()
            logger.error("Failed to save quiz questions", job_id=job_id, exc_info=True)
            raise
        finally:
            db.close()