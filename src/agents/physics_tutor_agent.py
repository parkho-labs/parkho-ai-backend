import structlog
from typing import Dict, Any, Optional, List

from .base import ContentTutorAgent
from .prompts import PhysicsTeacherPrompts
from ..services.llm_service import LLMService, LLMProvider
from ..config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class PhysicsTutorAgent(ContentTutorAgent):
    def __init__(self):
        super().__init__(name="PhysicsTutorAgent")
        self.llm_service = LLMService(
            openai_api_key=settings.openai_api_key,
            anthropic_api_key=settings.anthropic_api_key,
            google_api_key=settings.google_api_key
        )

    async def run(self, job_id: int, data: dict) -> dict:
        try:
            query = data.get("query", "")
            context = data.get("context", "")
            structured_response = data.get("structured_response", True)

            await self.update_job_progress(job_id, 10.0, "Starting physics content generation")

            if structured_response:
                result = await self.generate_educational_questions(
                    query=query,
                    context=context,
                    job_id=job_id
                )
            else:
                result = await self.generate_text_response(
                    query=query,
                    context=context,
                    job_id=job_id
                )

            await self.update_job_progress(job_id, 100.0, "Physics content generation completed")

            return {
                "success": True,
                "content": result,
                "agent": self.name,
                "response_type": "structured" if structured_response else "text"
            }

        except Exception as e:
            error_msg = f"PhysicsTutorAgent failed: {str(e)}"
            logger.error(error_msg, job_id=job_id)
            await self.mark_job_failed(job_id, error_msg)
            raise

    async def generate_educational_questions(
        self,
        query: str,
        context: str,
        job_id: Optional[int] = None,
        difficulty_level: str = "intermediate",
        use_jee_template: bool = False
    ) -> Dict[str, Any]:
        try:
            if job_id:
                await self.update_job_progress(job_id, 30.0, "Generating educational questions")

            if use_jee_template or "jee" in query.lower() or "advanced" in difficulty_level.lower():
                prompt = PhysicsTeacherPrompts.get_jee_advanced_template(
                    context=context,
                    query=query,
                    difficulty_level=difficulty_level
                )
            else:
                prompt = PhysicsTeacherPrompts.get_educational_json_template(
                    context=context,
                    query=query
                )

            if job_id:
                await self.update_job_progress(job_id, 50.0, "Processing with LLM")

            system_message = PhysicsTeacherPrompts.get_system_message()
            llm_response = await self.llm_service.generate_with_fallback(
                system_prompt=system_message,
                user_prompt=prompt,
                temperature=0.7,
                max_tokens=10000,
                preferred_provider=LLMProvider.OPENAI
            )

            if job_id:
                await self.update_job_progress(job_id, 80.0, "Parsing LLM response")

            questions_data = await self.llm_service.parse_json_response(llm_response)
            validated_data = self._validate_questions_response(questions_data)

            return validated_data

        except Exception as e:
            logger.error("Failed to generate educational questions", error=str(e), job_id=job_id)
            return {
                "questions": [],
                "error": f"Question generation failed: {str(e)}",
                "fallback": True
            }

    async def generate_text_response(
        self,
        query: str,
        context: str,
        job_id: Optional[int] = None
    ) -> str:
        try:
            if job_id:
                await self.update_job_progress(job_id, 30.0, "Generating text response")

            prompt = PhysicsTeacherPrompts.get_text_response_template(
                context=context,
                query=query
            )

            if job_id:
                await self.update_job_progress(job_id, 60.0, "Processing with LLM")

            system_message = PhysicsTeacherPrompts.get_system_message()
            response = await self.llm_service.generate_with_fallback(
                system_prompt=system_message,
                user_prompt=prompt,
                temperature=0.7,
                max_tokens=8000,
                preferred_provider=LLMProvider.OPENAI
            )

            return response

        except Exception as e:
            logger.error("Failed to generate text response", error=str(e), job_id=job_id)
            return f"I apologize, but I encountered an error while processing your request: {str(e)}"

    def _validate_questions_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(response_data, dict):
            return {"questions": []}

        questions = response_data.get("questions", [])
        if not isinstance(questions, list):
            questions = []

        validated_questions = []
        for i, question in enumerate(questions):
            if not isinstance(question, dict):
                continue

            validated_question = {
                "question_text": question.get("question_text", ""),
                "options": question.get("options", []),
                "correct_answer": question.get("correct_answer", ""),
                "explanation": question.get("explanation", ""),
                "requires_diagram": bool(question.get("requires_diagram", False)),
                "contains_math": bool(question.get("contains_math", False)),
                "diagram_type": question.get("diagram_type"),
                "source_reference": question.get("source_reference", "Generated content")
            }

            if "jee_topic" in question:
                validated_question["jee_topic"] = question["jee_topic"]
            if "complexity_level" in question:
                validated_question["complexity_level"] = question["complexity_level"]

            if validated_question["question_text"] and validated_question["correct_answer"]:
                validated_questions.append(validated_question)

        return {
            "questions": validated_questions,
            "total_questions": len(validated_questions),
            "generated_by": self.name
        }

    async def extract_direct_questions(
        self,
        context_chunks: List[str],
        query: str,
        job_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        try:
            if job_id:
                await self.update_job_progress(job_id, 20.0, "Searching for existing questions")

            direct_questions = []
            question_indicators = [
                r'Q\d+[\.\):]', r'Question \d+', r'\d+\.',
                r'Find the', r'Calculate', r'What is', r'Which of'
            ]

            for chunk_idx, chunk in enumerate(context_chunks):
                lines = chunk.split('\n')

                for line_idx, line in enumerate(lines):
                    line = line.strip()
                    if not line:
                        continue

                    for pattern in question_indicators:
                        import re
                        if re.search(pattern, line, re.IGNORECASE):
                            context_lines = lines[max(0, line_idx-1):min(len(lines), line_idx+5)]

                            question_data = {
                                "question_text": line,
                                "context": '\n'.join(context_lines),
                                "source_reference": f"Chunk {chunk_idx+1}, Line {line_idx+1}",
                                "extraction_method": "pattern_matching",
                                "confidence": 0.7
                            }

                            direct_questions.append(question_data)
                            break

            return direct_questions

        except Exception as e:
            logger.error("Failed to extract direct questions", error=str(e), job_id=job_id)
            return []