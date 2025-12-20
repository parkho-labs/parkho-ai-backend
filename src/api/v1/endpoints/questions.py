"""
Legal Question Generation Endpoint

Provides /questions/generate endpoint for creating exam-style legal questions.
Matches the specification in BACKEND_API_INTEGRATION.md.
"""

import structlog
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from src.services.rag_question_generator_service import RagQuestionGeneratorService
from src.api.v1.schemas import (
    LegalQuestionRequest,
    LegalQuestionResponse,
    LegalQuestion,
    LegalQuestionMetadata,
    LegalQuestionStats
)

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/generate", response_model=LegalQuestionResponse)
async def generate_legal_questions(request: LegalQuestionRequest) -> LegalQuestionResponse:
    """
    Generate exam-style questions for legal education.

    Endpoint: POST /api/v1/questions/generate

    Request Body:
        questions: List of question specifications (type, difficulty, count, filters)
        context: Optional context (subject, etc.)

    Response:
        success: Boolean success status
        total_generated: Number of questions generated
        questions: List of generated questions with metadata
        generation_stats: Statistics about the generation process
        errors: List of any errors that occurred
        warnings: List of any warnings
    """
    try:
        logger.info("Processing legal question generation request", request_questions=len(request.questions))

        # Transform legal request to RAG question generation request
        rag_questions = []
        total_requested = 0

        for question_spec in request.questions:
            total_requested += question_spec.count

            # Map legal question types to RAG service types
            rag_type_mapping = {
                "assertion_reasoning": "assertion_reasoning",
                "match_following": "match_following",
                "comprehension": "comprehension"
            }

            rag_type = rag_type_mapping.get(question_spec.type.value)
            if not rag_type:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported question type: {question_spec.type.value}"
                )

            rag_question = {
                "type": rag_type,
                "difficulty": question_spec.difficulty.value,
                "count": question_spec.count,
                "filters": question_spec.filters or {"collection_ids": ["constitution-golden-source"]}
            }
            rag_questions.append(rag_question)

        # Build RAG request
        from src.api.v1.schemas import RagQuestionGenerationRequest
        rag_request = RagQuestionGenerationRequest(
            questions=rag_questions,
            context={"subject": request.context.subject if request.context else "Constitutional Law"}
        )

        # Call RAG question generation service
        rag_service = RagQuestionGeneratorService.get_instance()
        generation_start = datetime.now()

        rag_response = await rag_service.generate_questions(rag_request)

        generation_time = (datetime.now() - generation_start).total_seconds()

        if not rag_response.success:
            return LegalQuestionResponse(
                success=False,
                total_generated=0,
                questions=[],
                generation_stats=LegalQuestionStats(
                    total_requested=total_requested,
                    by_type={},
                    by_difficulty={},
                    content_selection_time=0.0,
                    generation_time=generation_time
                ),
                errors=[f"Question generation failed: {', '.join(rag_response.errors)}"],
                warnings=rag_response.warnings
            )

        # Transform RAG response to legal format
        legal_questions = []
        type_counts = {}
        difficulty_counts = {}

        for rag_question in rag_response.questions:
            # Generate legal question metadata
            metadata = LegalQuestionMetadata(
                question_id=str(uuid.uuid4()),
                type=rag_question.metadata.type,
                difficulty=rag_question.metadata.difficulty,
                estimated_time=rag_question.metadata.estimated_time,
                source_files=rag_question.metadata.source_files,
                generated_at=datetime.now().isoformat()
            )

            # Count by type and difficulty
            type_counts[metadata.type] = type_counts.get(metadata.type, 0) + 1
            difficulty_counts[metadata.difficulty] = difficulty_counts.get(metadata.difficulty, 0) + 1

            legal_question = LegalQuestion(
                metadata=metadata,
                content=rag_question.content
            )
            legal_questions.append(legal_question)

        # Build generation stats
        generation_stats = LegalQuestionStats(
            total_requested=total_requested,
            by_type=type_counts,
            by_difficulty=difficulty_counts,
            content_selection_time=rag_response.generation_stats.content_selection_time,
            generation_time=generation_time
        )

        response = LegalQuestionResponse(
            success=True,
            total_generated=len(legal_questions),
            questions=legal_questions,
            generation_stats=generation_stats,
            errors=[],
            warnings=rag_response.warnings
        )

        logger.info(
            "Legal question generation completed",
            total_requested=total_requested,
            total_generated=response.total_generated,
            generation_time=generation_time
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Legal question generation failed", error=str(e), exc_info=e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate legal questions: {str(e)}"
        )