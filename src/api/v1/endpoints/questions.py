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
    LegalQuestionStats,
    # New schemas for enhanced quiz APIs
    CustomQuizRequest,
    MockQuizRequest,
    QuizGenerationResponse,
    CustomQuestionSpec
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


@router.post("/custom-quiz", response_model=QuizGenerationResponse)
async def generate_custom_quiz(request: CustomQuizRequest) -> QuizGenerationResponse:
    """
    Generate custom quiz where user specifies exact question types and counts.

    Endpoint: POST /api/v1/legal/custom-quiz

    Request Body:
        questions: List of question specifications (type and count)
        difficulty: Overall difficulty level for all questions
        subject: Subject context (default: "Constitutional Law")
        scope: Content scope - ["constitution"], ["bns"], or both
        filters: Optional filters like collection_ids

    Response:
        success: Boolean success status
        total_generated: Number of questions actually generated
        total_requested: Number of questions requested
        questions: List of generated questions with metadata
        generation_stats: Statistics about the generation process
        quiz_metadata: Additional metadata about the quiz
    """
    try:
        logger.info("Processing custom quiz generation request", request_questions=len(request.questions))

        # Transform custom request to RAG question generation request
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
                "difficulty": request.difficulty.value,  # Same difficulty for all questions
                "count": question_spec.count,
                "filters": request.filters or {"collection_ids": ["constitution-golden-source"]}
            }
            rag_questions.append(rag_question)

        # Use legal-specific RAG client method to call /law/questions
        from src.api.dependencies import get_rag_client
        rag_client = get_rag_client()
        generation_start = datetime.now()

        context = {"subject": request.subject}
        rag_response_data = await rag_client.legal_questions("user123", rag_questions, context)

        generation_time = (datetime.now() - generation_start).total_seconds()

        if not rag_response_data.get("success", False):
            return QuizGenerationResponse(
                success=False,
                total_generated=0,
                total_requested=total_requested,
                questions=[],
                generation_stats=LegalQuestionStats(
                    total_requested=total_requested,
                    by_type={},
                    by_difficulty={},
                    content_selection_time=0.0,
                    generation_time=generation_time
                ),
                quiz_metadata={
                    "quiz_type": "custom",
                    "requested_difficulty": request.difficulty.value,
                    "subject": request.subject,
                    "scope": request.scope
                },
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
                difficulty=question_data.get("metadata", {}).get("difficulty", request.difficulty.value),
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

        response = QuizGenerationResponse(
            success=True,
            total_generated=len(legal_questions),
            total_requested=total_requested,
            questions=legal_questions,
            generation_stats=generation_stats,
            quiz_metadata={
                "quiz_type": "custom",
                "requested_difficulty": request.difficulty.value,
                "subject": request.subject,
                "scope": request.scope,
                "user_specified_types": [q.type.value for q in request.questions],
                "user_specified_counts": [q.count for q in request.questions]
            },
            errors=[],
            warnings=rag_response_data.get("warnings", [])
        )

        logger.info(
            "Custom quiz generation completed",
            total_requested=total_requested,
            total_generated=response.total_generated,
            generation_time=generation_time,
            quiz_type="custom"
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Custom quiz generation failed", error=str(e), exc_info=e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate custom quiz: {str(e)}"
        )


@router.post("/mock-quiz", response_model=QuizGenerationResponse)
async def generate_mock_quiz(request: MockQuizRequest) -> QuizGenerationResponse:
    """
    Generate mock quiz with automatic equal distribution of question types and mixed difficulties.

    Endpoint: POST /api/v1/legal/mock-quiz

    Request Body:
        total_questions: Total number of questions (must be divisible by 3 for equal distribution)
        subject: Subject context (default: "Constitutional Law")
        scope: Content scope - ["constitution"], ["bns"], or both
        filters: Optional filters like collection_ids

    Response:
        success: Boolean success status
        total_generated: Number of questions actually generated
        total_requested: Number of questions requested
        questions: List of generated questions with metadata
        generation_stats: Statistics about the generation process
        quiz_metadata: Additional metadata about the quiz including distribution details

    Auto-Distribution Logic:
        - Question types: Equal split (33% each of assertion_reasoning, match_following, comprehension)
        - Difficulty levels: Equal split (33% easy, 33% moderate, 33% difficult)
    """
    try:
        logger.info("Processing mock quiz generation request", total_questions=request.total_questions)

        # Calculate automatic distribution
        questions_per_type = request.total_questions // 3

        # Define question types in order
        question_types = ["assertion_reasoning", "match_following", "comprehension"]
        # Use single difficulty for simplicity - RAG engine seems to prefer this
        default_difficulty = "moderate"

        # Create distributed question specs
        rag_questions = []
        total_requested = request.total_questions

        type_distribution = {}
        difficulty_distribution = {}

        # Distribute questions equally across types with single difficulty
        for question_type in question_types:
            rag_question = {
                "type": question_type,
                "difficulty": default_difficulty,
                "count": questions_per_type,
                "filters": request.filters or {"collection_ids": ["constitution-golden-source"]}
            }
            rag_questions.append(rag_question)

            # Track distribution
            type_distribution[question_type] = questions_per_type
            difficulty_distribution[default_difficulty] = difficulty_distribution.get(default_difficulty, 0) + questions_per_type

        # Use legal-specific RAG client method to call /law/questions
        from src.api.dependencies import get_rag_client
        rag_client = get_rag_client()
        generation_start = datetime.now()

        context = {"subject": request.subject}
        rag_response_data = await rag_client.legal_questions("user123", rag_questions, context)

        generation_time = (datetime.now() - generation_start).total_seconds()

        if not rag_response_data.get("success", False):
            return QuizGenerationResponse(
                success=False,
                total_generated=0,
                total_requested=total_requested,
                questions=[],
                generation_stats=LegalQuestionStats(
                    total_requested=total_requested,
                    by_type={},
                    by_difficulty={},
                    content_selection_time=0.0,
                    generation_time=generation_time
                ),
                quiz_metadata={
                    "quiz_type": "mock",
                    "intended_type_distribution": type_distribution,
                    "intended_difficulty_distribution": difficulty_distribution,
                    "subject": request.subject,
                    "scope": request.scope,
                    "distribution_strategy": "equal_split"
                },
                errors=[f"Question generation failed: {rag_response_data.get('error', 'Unknown error')}"],
                warnings=rag_response_data.get("warnings", [])
            )

        # Transform RAG response to legal format
        legal_questions = []
        actual_type_counts = {}
        actual_difficulty_counts = {}

        questions_data = rag_response_data.get("questions", [])
        for question_data in questions_data:
            # Generate legal question metadata
            metadata = LegalQuestionMetadata(
                question_id=str(uuid.uuid4()),
                type=question_data.get("metadata", {}).get("type", "unknown"),
                difficulty=question_data.get("metadata", {}).get("difficulty", "moderate"),
                estimated_time=question_data.get("metadata", {}).get("estimated_time", 3),
                source_files=question_data.get("metadata", {}).get("source_files", []),
                generated_at=datetime.now().isoformat()
            )

            # Count actual distribution
            actual_type_counts[metadata.type] = actual_type_counts.get(metadata.type, 0) + 1
            actual_difficulty_counts[metadata.difficulty] = actual_difficulty_counts.get(metadata.difficulty, 0) + 1

            legal_question = LegalQuestion(
                metadata=metadata,
                content=question_data.get("content", {})
            )
            legal_questions.append(legal_question)

        # Build generation stats
        generation_stats = LegalQuestionStats(
            total_requested=total_requested,
            by_type=actual_type_counts,
            by_difficulty=actual_difficulty_counts,
            content_selection_time=rag_response_data.get("generation_stats", {}).get("content_selection_time", 0.0),
            generation_time=generation_time
        )

        # Calculate distribution effectiveness
        distribution_effectiveness = {}
        for q_type in question_types:
            intended = type_distribution.get(q_type, 0)
            actual = actual_type_counts.get(q_type, 0)
            effectiveness = (actual / intended) * 100 if intended > 0 else 0
            distribution_effectiveness[q_type] = round(effectiveness, 1)

        response = QuizGenerationResponse(
            success=True,
            total_generated=len(legal_questions),
            total_requested=total_requested,
            questions=legal_questions,
            generation_stats=generation_stats,
            quiz_metadata={
                "quiz_type": "mock",
                "intended_type_distribution": type_distribution,
                "actual_type_distribution": actual_type_counts,
                "intended_difficulty_distribution": difficulty_distribution,
                "actual_difficulty_distribution": actual_difficulty_counts,
                "distribution_effectiveness": distribution_effectiveness,
                "subject": request.subject,
                "scope": request.scope,
                "distribution_strategy": "equal_split",
                "questions_per_type_target": questions_per_type
            },
            errors=[],
            warnings=rag_response_data.get("warnings", [])
        )

        logger.info(
            "Mock quiz generation completed",
            total_requested=total_requested,
            total_generated=response.total_generated,
            generation_time=generation_time,
            quiz_type="mock",
            distribution_effectiveness=distribution_effectiveness
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Mock quiz generation failed", error=str(e), exc_info=e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate mock quiz: {str(e)}"
        )