"""
Legal Question Generation Endpoint

Provides /legal/generate-quiz endpoint for creating exam-style legal questions.
Business-focused frontend API that uses RagQuestionGeneratorService internally.
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


@router.post("/generate-quiz", response_model=LegalQuestionResponse)
async def generate_legal_questions(request: LegalQuestionRequest) -> LegalQuestionResponse:
    """
    Generate exam-style questions for legal education.

    Endpoint: POST /api/v1/legal/generate-quiz

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

        # Use legal-specific RAG client method to call /law/questions
        from src.api.dependencies import get_rag_client
        rag_client = get_rag_client()
        generation_start = datetime.now()

        context = {"subject": request.context.subject if request.context else "Constitutional Law"}
        rag_response_data = await rag_client.legal_questions("user123", rag_questions, context)

        generation_time = (datetime.now() - generation_start).total_seconds()

        if not rag_response_data.get("success", False):
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
                errors=[f"Question generation failed: {rag_response_data.get('error', 'Unknown error')}"],
                warnings=rag_response_data.get("warnings", [])
            )

        # Transform RAG response to legal format
        legal_questions = []
        type_counts = {}
        difficulty_counts = {}

        questions_data = rag_response_data.get("questions", [])
        for question_data in questions_data:
            # Generate legal question metadata
            metadata = LegalQuestionMetadata(
                question_id=str(uuid.uuid4()),
                type=question_data.get("metadata", {}).get("type", "unknown"),
                difficulty=question_data.get("metadata", {}).get("difficulty", "easy"),
                estimated_time=question_data.get("metadata", {}).get("estimated_time", 3),
                source_files=question_data.get("metadata", {}).get("source_files", []),
                generated_at=datetime.now().isoformat()
            )

            # Count by type and difficulty
            type_counts[metadata.type] = type_counts.get(metadata.type, 0) + 1
            difficulty_counts[metadata.difficulty] = difficulty_counts.get(metadata.difficulty, 0) + 1

            legal_question = LegalQuestion(
                metadata=metadata,
                content=question_data.get("content", {})
            )
            legal_questions.append(legal_question)

        # Build generation stats
        generation_stats = LegalQuestionStats(
            total_requested=total_requested,
            by_type=type_counts,
            by_difficulty=difficulty_counts,
            content_selection_time=rag_response_data.get("generation_stats", {}).get("content_selection_time", 0.0),
            generation_time=generation_time
        )

        response = LegalQuestionResponse(
            success=True,
            total_generated=len(legal_questions),
            questions=legal_questions,
            generation_stats=generation_stats,
            errors=[],
            warnings=rag_response_data.get("warnings", [])
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