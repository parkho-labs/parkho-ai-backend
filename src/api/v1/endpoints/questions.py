"""
Legal Question Generation Endpoint

Provides /legal/generate-quiz endpoint for creating exam-style legal questions.
Business-focused frontend API that uses RagQuestionGeneratorService internally.
"""

import structlog
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Query, Path as PathParam
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
import json

from src.api.v1.schemas import (
    LegalQuestionRequest,
    LegalQuestionResponse,
    LegalQuestion,
    LegalQuestionMetadata,
    LegalQuestionStats,
    CustomQuizRequest,
    MockQuizRequest,
    QuizGenerationResponse,
    CustomQuestionSpec,
    ExamAnswers,
    SubmitAttemptResponse
)
from src.core.database import get_db
from src.api.dependencies import get_llm_service
from src.services.llm_service import LLMService
import asyncio

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/generate-quiz", response_model=LegalQuestionResponse)
async def generate_legal_questions(
    request: LegalQuestionRequest,
    user_id: str = Query("anonymous", description="User identifier"),
    db: Session = Depends(get_db)
) -> LegalQuestionResponse:
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

            # Pass question type directly to RAG (no mapping needed)
            # RAG will handle whatever question type is sent
            rag_question = {
                "type": question_spec.type,  # Pass through as-is
                "difficulty": question_spec.difficulty,
                "count": question_spec.count,
                "filters": question_spec.filters or {"collection_ids": ["constitution-golden-source"]}
            }
            rag_questions.append(rag_question)

        # Use legal-specific RAG client method to call /law/questions
        from src.api.dependencies import get_law_rag_client
        rag_client = get_law_rag_client()
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

        # Record attempt in database
        try:
            from src.models.user_attempt import UserAttempt
            attempt = UserAttempt(
                user_identifier=user_id,
                total_marks=len(legal_questions),
                started_at=datetime.now()
            )
            # Store questions in meta for scoring later
            attempt.answers = json.dumps({
                "quiz_type": "legal",
                "subject": request.context.subject if request.context else "Constitutional Law",
                "questions": [q.dict() for q in legal_questions]
            })
            db.add(attempt)
            db.commit()
            db.refresh(attempt)
            response.attempt_id = attempt.id
        except Exception as e:
            logger.error("Failed to record legal quiz attempt", error=str(e))

        logger.info(
            "Legal question generation completed",
            total_requested=total_requested,
            total_generated=response.total_generated,
            generation_time=generation_time,
            attempt_id=response.attempt_id
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
async def generate_custom_quiz(
    request: CustomQuizRequest,
    user_id: str = Query("anonymous"),
    db: Session = Depends(get_db)
) -> QuizGenerationResponse:
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

            # Pass question type directly to RAG (no mapping needed)
            # RAG will handle whatever question type is sent
            rag_question = {
                "type": question_spec.type,  # Pass through as-is
                "difficulty": request.difficulty,  # Same difficulty for all questions
                "count": question_spec.count,
                "filters": request.filters or {"collection_ids": ["constitution-golden-source"]}
            }
            rag_questions.append(rag_question)

        # Use legal-specific RAG client method to call /law/questions
        from src.api.dependencies import get_law_rag_client
        rag_client = get_law_rag_client()
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
                    "requested_difficulty": request.difficulty,
                    "subject": request.subject,
                    "scope": request.scope
                },
                errors=[f"Question generation failed: {rag_response_data.get('error', 'Unknown error')}"],
                warnings=rag_response_data.get("warnings", [])
            )

        # Transform RAG response to legal format
        legal_questions = []
        legal_questions_with_answers = []  # Store full questions with answers for DB
        type_counts = {}
        difficulty_counts = {}

        questions_data = rag_response_data.get("questions", [])
        for question_data in questions_data:
            # Generate legal question metadata
            metadata = LegalQuestionMetadata(
                question_id=str(uuid.uuid4()),
                type=question_data.get("metadata", {}).get("type", "unknown"),
                difficulty=question_data.get("metadata", {}).get("difficulty", request.difficulty),
                estimated_time=question_data.get("metadata", {}).get("estimated_time", 3),
                source_files=question_data.get("metadata", {}).get("source_files", []),
                generated_at=datetime.now().isoformat()
            )

            # Count by type and difficulty
            type_counts[metadata.type] = type_counts.get(metadata.type, 0) + 1
            difficulty_counts[metadata.difficulty] = difficulty_counts.get(metadata.difficulty, 0) + 1

            # Full question with answers (for DB storage)
            full_question = LegalQuestion(
                metadata=metadata,
                content=question_data.get("content", {})
            )
            legal_questions_with_answers.append(full_question)
            
            # Conditionally strip answers for frontend response
            if request.include_answers:
                # Include everything
                legal_questions.append(full_question)
            else:
                # Remove answer fields from content
                content_without_answers = question_data.get("content", {}).copy()
                # Remove answer-related fields based on question type
                content_without_answers.pop("correct_option", None)
                content_without_answers.pop("correct_matches", None)
                content_without_answers.pop("explanation", None)
                
                question_for_frontend = LegalQuestion(
                    metadata=metadata,
                    content=content_without_answers
                )
                legal_questions.append(question_for_frontend)

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
                "requested_difficulty": request.difficulty,
                "subject": request.subject,
                "scope": request.scope,
                "user_specified_types": [q.type for q in request.questions],
                "user_specified_counts": [q.count for q in request.questions]
            },
            errors=[],
            warnings=rag_response_data.get("warnings", [])
        )

        # Record attempt in database
        try:
            from src.models.user_attempt import UserAttempt
            attempt = UserAttempt(
                user_identifier=user_id,
                total_marks=len(legal_questions),
                started_at=datetime.now()
            )
            # Store FULL questions with answers for scoring later
            attempt.answers = json.dumps({
                "quiz_type": "custom",
                "subject": request.subject,
                "scope": request.scope,
                "questions": [q.dict() for q in legal_questions_with_answers]
            })
            db.add(attempt)
            db.commit()
            db.refresh(attempt)
            response.attempt_id = attempt.id
        except Exception as e:
            logger.error("Failed to record custom quiz attempt", error=str(e))

        logger.info(
            "Custom quiz generation completed",
            total_requested=total_requested,
            total_generated=response.total_generated,
            generation_time=generation_time,
            quiz_type="custom",
            attempt_id=response.attempt_id
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
async def generate_mock_quiz(
    request: MockQuizRequest,
    user_id: str = Query("anonymous"),
    db: Session = Depends(get_db)
) -> QuizGenerationResponse:
    """
    Generate mock quiz with automatic equal distribution of question types and mixed difficulties.
    """
    try:
        logger.info("Processing mock quiz generation request", total_questions=request.total_questions)

        # Calculate automatic distribution
        questions_per_type = request.total_questions // 3
        question_types = ["assertion_reasoning", "match_following", "comprehension"]
        default_difficulty = "moderate"

        rag_questions = []
        total_requested = request.total_questions

        type_distribution = {}
        difficulty_distribution = {}

        for question_type in question_types:
            rag_question = {
                "type": question_type,
                "difficulty": default_difficulty,
                "count": questions_per_type,
                "filters": request.filters or {"collection_ids": ["constitution-golden-source"]}
            }
            rag_questions.append(rag_question)
            type_distribution[question_type] = questions_per_type
            difficulty_distribution[default_difficulty] = difficulty_distribution.get(default_difficulty, 0) + questions_per_type

        from src.api.dependencies import get_law_rag_client
        rag_client = get_law_rag_client()
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

        legal_questions = []
        legal_questions_with_answers = []  # Store full questions with answers for DB
        actual_type_counts = {}
        actual_difficulty_counts = {}

        questions_data = rag_response_data.get("questions", [])
        for question_data in questions_data:
            metadata = LegalQuestionMetadata(
                question_id=str(uuid.uuid4()),
                type=question_data.get("metadata", {}).get("type", "unknown"),
                difficulty=question_data.get("metadata", {}).get("difficulty", "moderate"),
                estimated_time=question_data.get("metadata", {}).get("estimated_time", 3),
                source_files=question_data.get("metadata", {}).get("source_files", []),
                generated_at=datetime.now().isoformat()
            )
            actual_type_counts[metadata.type] = actual_type_counts.get(metadata.type, 0) + 1
            actual_difficulty_counts[metadata.difficulty] = actual_difficulty_counts.get(metadata.difficulty, 0) + 1
            
            # Full question with answers (for DB storage)
            full_question = LegalQuestion(
                metadata=metadata,
                content=question_data.get("content", {})
            )
            legal_questions_with_answers.append(full_question)
            
            # Conditionally strip answers for frontend response
            if request.include_answers:
                # Include everything
                legal_questions.append(full_question)
            else:
                # Remove answer fields from content
                content_without_answers = question_data.get("content", {}).copy()
                # Remove answer-related fields based on question type
                content_without_answers.pop("correct_option", None)
                content_without_answers.pop("correct_matches", None)
                content_without_answers.pop("explanation", None)
                
                question_for_frontend = LegalQuestion(
                    metadata=metadata,
                    content=content_without_answers
                )
                legal_questions.append(question_for_frontend)

        generation_stats = LegalQuestionStats(
            total_requested=total_requested,
            by_type=actual_type_counts,
            by_difficulty=actual_difficulty_counts,
            content_selection_time=rag_response_data.get("generation_stats", {}).get("content_selection_time", 0.0),
            generation_time=generation_time
        )

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

        try:
            from src.models.user_attempt import UserAttempt
            attempt = UserAttempt(
                user_identifier=user_id,
                total_marks=len(legal_questions),
                started_at=datetime.now()
            )
            attempt.answers = json.dumps({
                "quiz_type": "mock",
                "subject": request.subject,
                "scope": request.scope,
                "questions": [q.dict() for q in legal_questions_with_answers]
            })
            db.add(attempt)
            db.commit()
            db.refresh(attempt)
            response.attempt_id = attempt.id
        except Exception as e:
            logger.error("Failed to record mock quiz attempt", error=str(e))

        logger.info(
            "Mock quiz generation completed",
            total_requested=total_requested,
            total_generated=response.total_generated,
            generation_time=generation_time,
            quiz_type="mock",
            attempt_id=response.attempt_id,
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


@router.post("/attempts/{attempt_id}/submit", response_model=SubmitAttemptResponse)
async def submit_legal_quiz(
    attempt_id: int = PathParam(..., description="Quiz attempt ID"),
    answers: ExamAnswers = None,
    db: Session = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service)
) -> SubmitAttemptResponse:
    """
    Submit answers for a generated legal quiz and get score.
    Includes automatic explanation generation if missing.
    """
    try:
        from src.models.user_attempt import UserAttempt
        
        attempt = db.query(UserAttempt).filter(UserAttempt.id == attempt_id).first()
        if not attempt:
            raise HTTPException(status_code=404, detail="Attempt not found")
        
        if attempt.is_submitted:
            raise HTTPException(status_code=400, detail="Already submitted")
            
        data = json.loads(attempt.answers) if attempt.answers else {}
        questions = data.get("questions", [])
        
        correct_count = 0
        question_results = []
        submitted_answers = answers.answers if answers else {}

        # Prepare tasks for missing explanations
        explanation_tasks = []
        task_indices = []

        for i, q in enumerate(questions):
            q_metadata = q.get("metadata", {})
            q_id = q_metadata.get("question_id")
            q_content = q.get("content", {})
            correct_ans = q_content.get("correct_option") or q_content.get("correct_matches")
            
            user_ans = submitted_answers.get(q_id)
            is_correct = False
            if isinstance(correct_ans, dict):
                 is_correct = str(user_ans) == str(correct_ans)
            else:
                 is_correct = str(user_ans).strip().upper() == str(correct_ans).strip().upper() if user_ans else False
            
            if is_correct:
                correct_count += 1

            # Get or generate explanation
            explanation = q_content.get("explanation", "").strip()
            
            if not explanation:
                # Prepare LLM task to generate explanation
                q_text = q_content.get("question_text", "")
                q_options = q_content.get("options", [])
                
                system_prompt = "You are an expert Indian Legal Assistant. Provide a concise, accurate explanation for the correct answer to the given legal question."
                user_prompt = f"""
                Question: {q_text}
                Options: {q_options}
                Correct Answer: {correct_ans}
                
                Provide a 2-3 sentence explanation explaining why this answer is correct according to the Indian Constitution or relevant laws.
                """
                
                explanation_tasks.append(llm_service.generate_with_fallback(system_prompt, user_prompt))
                task_indices.append(i)
                explanation = "Generating explanation..." # Placeholder
            
            question_results.append({
                "question_id": str(q_id),
                "question_text": q_content.get("question_text", ""),
                "correct_answer": str(correct_ans),
                "user_answer": str(user_ans) if user_ans else None,
                "is_correct": is_correct,
                "is_attempted": user_ans is not None,
                "explanation": explanation,
                "marks": 1.0
            })

        # Resolve LLM tasks if any
        if explanation_tasks:
            generated_explanations = await asyncio.gather(*explanation_tasks, return_exceptions=True)
            for idx, generated_exp in zip(task_indices, generated_explanations):
                if isinstance(generated_exp, str):
                    question_results[idx]["explanation"] = generated_exp
                else:
                    question_results[idx]["explanation"] = "Explanation could not be generated at this time."
            
        attempt.score = float(correct_count)
        attempt.total_marks = float(len(questions))
        attempt.percentage = (attempt.score / attempt.total_marks * 100) if attempt.total_marks > 0 else 0
        attempt.is_submitted = True
        attempt.is_completed = True
        attempt.submitted_at = datetime.now(timezone.utc)
        
        if attempt.started_at:
            # Ensure started_at is offset-aware for subtraction
            started_at_aware = attempt.started_at
            if started_at_aware.tzinfo is None:
                started_at_aware = started_at_aware.replace(tzinfo=timezone.utc)
            
            attempt.time_taken_seconds = int((attempt.submitted_at - started_at_aware).total_seconds())
            
        data["submitted_answers"] = submitted_answers
        data["detailed_results"] = {"question_results": question_results}
        attempt.answers = json.dumps(data)
        
        db.commit()
        db.refresh(attempt)
        
        return SubmitAttemptResponse(
            attempt_id=attempt.id,
            submitted=True,
            score=attempt.score,
            total_marks=attempt.total_marks,
            percentage=attempt.percentage,
            time_taken_seconds=attempt.time_taken_seconds,
            display_time=attempt.display_time_taken,
            submitted_at=attempt.submitted_at.isoformat(),
            paper_info={
                "id": 0,
                "title": f"Quiz: {data.get('subject', 'Legal')}",
                "exam_name": "Legal Education",
                "year": datetime.now().year
            },
            detailed_results={
                "attempt_id": attempt.id,
                "paper_id": 0,
                "score": attempt.score,
                "total_marks": attempt.total_marks,
                "percentage": attempt.percentage,
                "question_results": question_results
            }
        )
    except Exception as e:
        logger.error("Submit legal quiz failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))