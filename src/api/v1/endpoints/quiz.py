import structlog
from fastapi import APIRouter, Depends, HTTPException

from src.utils import job_utils
from ..mappers.quiz_response_mapper import QuizResponseMapper
from ...dependencies import get_content_job_repository, get_quiz_repository
from ..schemas import QuizResponse, QuizSubmission, QuizEvaluationResult, QuizResult
from ....exceptions import JobNotFoundError

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/{job_id}/quiz", response_model=QuizResponse)
async def get_job_quiz(
    job_id: int,
    repo = Depends(get_content_job_repository),
    quiz_repo = Depends(get_quiz_repository)
) -> QuizResponse:
    try:
        job = job_utils.check_job_exists(job_id, repo)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        quiz_questions_db = quiz_repo.get_questions_by_job_id(job_id)
        if not quiz_questions_db:
            logger.error(
                "Quiz retrieval failed - no questions",
                job_id=job_id,
                job_status=job.status,
                has_output_questions=bool(job.questions)
            )
            raise HTTPException(
                status_code=500,
                detail="Content not found - quiz questions were not generated during processing"
            )

        return QuizResponseMapper.map_to_quiz_response(quiz_questions_db, job)

    except JobNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get quiz questions", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve quiz questions")


@router.post("/{job_id}/quiz", response_model=QuizEvaluationResult)
async def submit_job_quiz(
    job_id: int,
    submission: QuizSubmission,
    repo = Depends(get_content_job_repository),
    quiz_repo = Depends(get_quiz_repository)
) -> QuizEvaluationResult:
    try:
        job = job_utils.check_job_exists(job_id, repo)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        quiz_questions_db = quiz_repo.get_questions_by_job_id(job_id)
        if not quiz_questions_db:
            raise HTTPException(
                status_code=500,
                detail="Content not found - quiz questions were not generated during processing"
            )

        results = []
        total_score = 0
        max_possible_score = 0

        for q in quiz_questions_db:
            question_id = q.question_id
            question_type = q.type
            answer_config = q.answer_config
            max_score = q.max_score
            max_possible_score += max_score

            user_answer = submission.answers.get(question_id, "")
            correct_answer = answer_config.get("correct_answer", "")

            is_correct = False
            score = 0

            if question_type == "multiple_choice":
                is_correct = user_answer.upper() == correct_answer.upper()
            elif question_type == "true_false":
                is_correct = user_answer.lower() == correct_answer.lower()
            elif question_type == "short_answer":
                is_correct = user_answer.lower().strip() == correct_answer.lower().strip()

            if is_correct:
                score = max_score
                total_score += score

            results.append(QuizResult(
                question_id=question_id,
                user_answer=user_answer,
                correct_answer=correct_answer,
                is_correct=is_correct,
                score=score
            ))

        percentage = 0.0
        if max_possible_score > 0:
            percentage = round((total_score / max_possible_score) * 100, 2)

        return QuizEvaluationResult(
            total_score=total_score,
            max_possible_score=max_possible_score,
            percentage=percentage,
            results=results
        )

    except JobNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to submit quiz", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to evaluate quiz submission")