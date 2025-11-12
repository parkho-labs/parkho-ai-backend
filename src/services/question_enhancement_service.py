import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..agents.physics_tutor_agent import PhysicsTutorAgent
from ..services.rag_integration_service import get_rag_service
from ..utils.query_analyzer import QueryAnalyzer
from ..config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class QuestionEnhancementService:
    def __init__(self):
        self.physics_tutor = PhysicsTutorAgent()
        try:
            self.rag_service = get_rag_service()
        except Exception as e:
            logger.warning(f"RAG service initialization failed: {e}")
            self.rag_service = None

    async def process_question_request(
        self,
        query: str,
        input_config: List[Dict[str, Any]],
        options: Dict[str, Any],
        job_id: Optional[int] = None
    ) -> Dict[str, Any]:
        try:
            query_analysis = QueryAnalyzer.analyze_query_comprehensive(query)
            context_text = await self._retrieve_rag_context(
                query=query,
                collection_name=options.get("collection_name"),
                job_id=job_id
            )

            generation_options = self._prepare_generation_options(options, query_analysis)

            llm_response = await self._generate_questions_with_agent(
                query=query,
                context=context_text,
                generation_options=generation_options,
                job_id=job_id
            )

            enhanced_response = await self._enhance_for_frontend(
                llm_response=llm_response,
                query=query,
                query_analysis=query_analysis,
                generation_options=generation_options
            )

            return enhanced_response

        except Exception as e:
            logger.error("Question enhancement failed", error=str(e), job_id=job_id)
            return self._create_error_response(str(e), query)

    async def _retrieve_rag_context(
        self,
        query: str,
        collection_name: Optional[str] = None,
        job_id: Optional[int] = None
    ) -> str:
        if not self.rag_service or not collection_name:
            return ""

        try:
            context = await self.rag_service.get_collection_context(
                collection_name=collection_name,
                query=query
            )
            return context or ""
        except Exception as e:
            logger.warning("Failed to retrieve RAG context", error=str(e))
            return ""

    def _prepare_generation_options(
        self,
        options: Dict[str, Any],
        query_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        generation_options = {
            "structured_response": True,
            "difficulty_level": options.get("difficulty_level", query_analysis["complexity_level"]),
            "num_questions": options.get("num_questions", query_analysis["question_count"]) or 5,
            "question_types": options.get("question_types", query_analysis["question_types"]),
            "use_jee_template": query_analysis["is_jee_focused"] or query_analysis["complexity_level"] == "jee_advanced",
            "subject_area": query_analysis["subject_area"],
            "llm_provider": options.get("llm_provider", "openai")
        }

        generation_options["num_questions"] = min(max(1, generation_options["num_questions"]), 20)
        return generation_options

    async def _generate_questions_with_agent(
        self,
        query: str,
        context: str,
        generation_options: Dict[str, Any],
        job_id: Optional[int] = None
    ) -> Dict[str, Any]:
        try:
            agent_data = {
                "query": query,
                "context": context,
                "structured_response": True,
                "difficulty_level": generation_options["difficulty_level"],
                "use_jee_template": generation_options["use_jee_template"]
            }

            if job_id:
                result = await self.physics_tutor.run(job_id, agent_data)
                return result.get("content", {})
            else:
                return await self.physics_tutor.generate_educational_questions(
                    query=query,
                    context=context,
                    difficulty_level=generation_options["difficulty_level"],
                    use_jee_template=generation_options["use_jee_template"]
                )

        except Exception as e:
            logger.error("Agent question generation failed", error=str(e))
            raise

    async def _enhance_for_frontend(
        self,
        llm_response: Dict[str, Any],
        query: str,
        query_analysis: Dict[str, Any],
        generation_options: Dict[str, Any]
    ) -> Dict[str, Any]:
        try:
            raw_questions = llm_response.get("questions", [])

            if not raw_questions:
                return self._create_empty_response(query)

            enhanced_questions = []
            for i, raw_question in enumerate(raw_questions):
                enhanced_question = self._enhance_single_question(
                    raw_question=raw_question,
                    question_number=i + 1,
                    generation_options=generation_options
                )
                enhanced_questions.append(enhanced_question)

            summary = self._create_content_summary(
                questions_count=len(enhanced_questions),
                difficulty_level=generation_options["difficulty_level"],
                subject_area=generation_options["subject_area"]
            )

            total_score = sum(q["answer_config"]["max_score"] for q in enhanced_questions)
            total_time = sum(q["metadata"]["estimated_time"] for q in enhanced_questions)

            enhanced_response = {
                "content_text": f"Educational questions generated for: {query}",
                "summary": summary,
                "questions": enhanced_questions,
                "metadata": {
                    "analysis": {
                        "main_topics": QueryAnalyzer.extract_physics_topics(query),
                        "content_type": "educational_questions",
                        "complexity_level": generation_options["difficulty_level"],
                        "estimated_reading_time": max(1, total_time // 60),
                        "target_audience": self._get_target_audience(generation_options["difficulty_level"]),
                        "subject_area": generation_options["subject_area"]
                    },
                    "question_generation": {
                        "total_questions": len(enhanced_questions),
                        "question_types": self._count_question_types(enhanced_questions),
                        "user_request": query,
                        "difficulty_level": generation_options["difficulty_level"],
                        "generated_from": "rag_context" if "rag_context_used" in llm_response else "input_content",
                        "llm_provider": generation_options["llm_provider"],
                        "total_score": total_score,
                        "estimated_time": total_time,
                        "generation_timestamp": datetime.now().isoformat()
                    }
                }
            }

            return enhanced_response

        except Exception as e:
            logger.error("Failed to enhance response for frontend", error=str(e))
            return self._create_error_response(str(e), query)

    def _enhance_single_question(
        self,
        raw_question: Dict[str, Any],
        question_number: int,
        generation_options: Dict[str, Any]
    ) -> Dict[str, Any]:
        question_id = f"q{question_number}"
        question_type = QueryAnalyzer.classify_question_type_from_options(
            raw_question.get("options", [])
        )

        question_config = {
            "question_text": raw_question.get("question_text", ""),
            "type": question_type,
            "requires_diagram": bool(raw_question.get("requires_diagram", False)),
            "contains_math": bool(raw_question.get("contains_math", False)),
            "diagram_type": raw_question.get("diagram_type"),
            "complexity_level": generation_options["difficulty_level"],
            "source_reference": raw_question.get("source_reference", "Generated content")
        }

        if generation_options.get("use_jee_template"):
            question_config["jee_topic"] = raw_question.get("jee_topic", generation_options["subject_area"])

        answer_config = {
            "options": raw_question.get("options", []),
            "correct_answer": raw_question.get("correct_answer", ""),
            "reason": raw_question.get("explanation", ""),
            "max_score": self._calculate_question_score(question_type, generation_options["difficulty_level"])
        }

        metadata = {
            "auto_generated_id": True,
            "question_number": question_number,
            "estimated_time": self._estimate_question_time(
                question_type, generation_options["difficulty_level"]
            ),
            "physics_topics": QueryAnalyzer.extract_physics_topics(
                raw_question.get("question_text", "") + " " + raw_question.get("explanation", "")
            )
        }

        return {
            "question_id": question_id,
            "question_config": question_config,
            "answer_config": answer_config,
            "context": raw_question.get("source_reference", "Generated from physics content"),
            "metadata": metadata
        }

    def _calculate_question_score(self, question_type: str, difficulty_level: str) -> int:
        base_scores = {"multiple_choice": 1, "true_false": 1, "short_answer": 2}
        difficulty_multipliers = {"basic": 1, "intermediate": 1, "advanced": 2, "jee_advanced": 3}

        base_score = base_scores.get(question_type, 1)
        multiplier = difficulty_multipliers.get(difficulty_level, 1)
        return base_score * multiplier

    def _estimate_question_time(self, question_type: str, difficulty_level: str) -> int:
        base_times = {"multiple_choice": 60, "true_false": 30, "short_answer": 120}
        difficulty_multipliers = {"basic": 0.8, "intermediate": 1.0, "advanced": 1.5, "jee_advanced": 2.0}

        base_time = base_times.get(question_type, 60)
        multiplier = difficulty_multipliers.get(difficulty_level, 1.0)
        return int(base_time * multiplier)

    def _count_question_types(self, questions: List[Dict[str, Any]]) -> Dict[str, int]:
        type_counts = {}
        for question in questions:
            q_type = question["question_config"]["type"]
            type_counts[q_type] = type_counts.get(q_type, 0) + 1
        return type_counts

    def _get_target_audience(self, difficulty_level: str) -> str:
        audiences = {
            "basic": "High school physics students",
            "intermediate": "Undergraduate physics students",
            "advanced": "Advanced physics students and professionals",
            "jee_advanced": "Students preparing for JEE Advanced and competitive exams"
        }
        return audiences.get(difficulty_level, "Physics students")

    def _create_content_summary(self, questions_count: int, difficulty_level: str, subject_area: str) -> str:
        return f"This content provides {questions_count} educational questions in {subject_area} at {difficulty_level} level, designed to test understanding and application skills in physics concepts."

    def _create_empty_response(self, query: str) -> Dict[str, Any]:
        return {
            "content_text": f"No questions could be generated for: {query}",
            "summary": "No educational content was generated due to processing issues.",
            "questions": [],
            "metadata": {
                "analysis": {
                    "content_type": "educational_questions",
                    "complexity_level": "unknown",
                    "estimated_reading_time": 0,
                    "target_audience": "Physics students"
                },
                "question_generation": {
                    "total_questions": 0,
                    "question_types": {},
                    "user_request": query,
                    "generated_from": "none",
                    "generation_timestamp": datetime.now().isoformat()
                }
            }
        }

    def _create_error_response(self, error_message: str, query: str) -> Dict[str, Any]:
        return {
            "content_text": f"Error processing request: {query}",
            "summary": f"An error occurred during question generation: {error_message}",
            "questions": [],
            "error": error_message,
            "metadata": {
                "analysis": {"content_type": "error", "complexity_level": "unknown"},
                "question_generation": {
                    "total_questions": 0,
                    "user_request": query,
                    "error": error_message,
                    "generation_timestamp": datetime.now().isoformat()
                }
            }
        }