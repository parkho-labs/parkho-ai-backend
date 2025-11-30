import json
from typing import Dict, Any

import structlog

from ..config import get_settings
from ..services.llm_service import LLMService
from ..utils.prompt_strings import PromptStrings

logger = structlog.get_logger(__name__)


class QuestionGenerationService:
    def __init__(self):
        settings = get_settings()
        self.llm_service = LLMService(
            openai_api_key=settings.openai_api_key,
            anthropic_api_key=settings.anthropic_api_key,
            google_api_key=settings.google_api_key
        )

    async def generate_questions(self, subject: str = None, content: str = "",
                               question_config: Dict[str, int] = {},
                               difficulty_level: str = "intermediate") -> Dict[str, Any]:
        try:
            prompt = self._get_prompt(subject, content, question_config, difficulty_level)

            response = await self.llm_service.generate_with_fallback(
                system_prompt="You are an expert educator. Generate educational questions based on the provided content.",
                user_prompt=prompt,
                temperature=0.7,
                max_tokens=4000
            )

            cleaned_response = self._clean_json_response(response)
            questions_data = json.loads(cleaned_response)
            questions = questions_data.get("questions", [])

            formatted_questions = self._format_questions(questions)

            return {
                "questions": formatted_questions,
                "total_questions": len(formatted_questions),
                "total_score": len(formatted_questions)
            }

        except Exception as e:
            logger.error(f"Question generation failed: {str(e)}", exc_info=True)
            return {"questions": [], "total_questions": 0, "total_score": 0}

    def _get_prompt(self, subject: str, content: str, question_config: Dict[str, int], difficulty_level: str) -> str:
        prompt_template = self._get_prompt_template(subject)

        question_breakdown = []
        total_questions = sum(question_config.values())

        for qtype, count in question_config.items():
            if count > 0:
                question_breakdown.append(f"- {count} {qtype} questions")

        return prompt_template.format(
            total_questions=total_questions,
            difficulty=difficulty_level,
            question_breakdown="\n".join(question_breakdown),
            content=content
        )

    def _get_prompt_template(self, subject: str) -> str:
        match subject:
            case "physics":
                return PromptStrings.PHYSICS_QUESTIONS
            case "chemistry":
                return PromptStrings.CHEMISTRY_QUESTIONS
            case _:
                return PromptStrings.GENERIC_QUESTIONS

    def _format_questions(self, questions: list) -> list:
        formatted = []

        for i, q in enumerate(questions):
            formatted_question = {
                "question_id": f"q{i+1}",
                "question": q.get("question", ""),
                "question_config": {
                    "type": q.get("question_type", "multiple_choice"),
                    "requires_diagram": q.get("requires_diagram", False)
                },
                "answer_config": q.get("answer_config", {}),
                "reason": q.get("reason", ""),
                "max_score": 1
            }

            if q.get("options"):
                formatted_question["question_config"]["options"] = q["options"]

            if q.get("requires_diagram"):
                formatted_question["question_config"]["diagram_type"] = q.get("diagram_type")
                formatted_question["question_config"]["diagram_elements"] = q.get("diagram_elements", {})

            if q.get("source_timestamp"):
                formatted_question["metadata"] = {
                    "video_timestamp": q["source_timestamp"],
                    "sources": {}
                }

            formatted.append(formatted_question)

        return formatted

    def _clean_json_response(self, response: str) -> str:
        response = response.strip()

        if response.startswith("```json"):
            response = response[7:]
        elif response.startswith("```"):
            response = response[3:]

        if response.endswith("```"):
            response = response[:-3]

        return response.strip()


question_generation_service = QuestionGenerationService()