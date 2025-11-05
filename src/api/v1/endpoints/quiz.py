import structlog
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
import openai

from ...dependencies import get_quiz_repository, get_content_job_repository
from ..schemas import QuizResponse, QuizSubmission
from ....core.exceptions import JobNotFoundError
from ....services.quiz_evaluator import QuizEvaluator
from ....config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

router = APIRouter()

@router.get("", response_model=Dict[str, Any])
async def get_content_quiz(
    content_id: int,
    quiz_repo = Depends(get_quiz_repository),
    content_repo = Depends(get_content_job_repository)
) -> Dict[str, Any]:
    try:
        job = content_repo.get(content_id)
        if not job:
            raise JobNotFoundError(content_id)

        if job.status != "completed":
            raise HTTPException(
                status_code=409,
                detail=f"Quiz not available. Job status: {job.status}"
            )

        questions = quiz_repo.get_questions_by_job_id(content_id)
        if not questions:
            raise HTTPException(
                status_code=404,
                detail="No quiz questions found for this video"
            )

        # Hide correct answers - only return question data needed for taking quiz
        quiz_questions = []
        for q in questions:
            question_data = {
                "question_id": q.question_id,
                "question": q.question,
                "type": q.type,
                "max_score": q.max_score
            }

            # Add options for MCQ questions only
            if q.type == "multiple_choice" and "options" in q.answer_config:
                question_data["options"] = q.answer_config["options"]

            # Add context if available
            if q.context:
                question_data["context"] = q.context

            quiz_questions.append(question_data)

        total_score = quiz_repo.get_total_score_by_job_id(content_id)

        return {
            "questions": quiz_questions,
            "total_questions": len(questions),
            "max_score": total_score
        }

    except JobNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get quiz questions", content_id=content_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve quiz questions")


@router.post("", response_model=Dict[str, Any])
async def submit_content_quiz(
    content_id: int,
    submission: QuizSubmission,
    quiz_repo = Depends(get_quiz_repository),
    content_repo = Depends(get_content_job_repository)
) -> Dict[str, Any]:
    try:
        job = content_repo.get(content_id)
        if not job:
            raise JobNotFoundError(content_id)

        questions = quiz_repo.get_questions_by_job_id(content_id)
        if not questions:
            raise HTTPException(
                status_code=404,
                detail="No quiz questions found for this video"
            )

        questions_data = [
            {
                "question_id": q.question_id,
                "question": q.question,
                "type": q.type,
                "answer_config": q.answer_config,
                "context": q.context,
                "max_score": q.max_score
            }
            for q in questions
        ]

        user_answers = [
            {
                "question_id": question_id,
                "user_answer": user_answer
            }
            for question_id, user_answer in submission.answers.items()
        ]

        class OpenAIWrapper:
            def __init__(self, api_key):
                self.client = openai.OpenAI(api_key=api_key)

            async def generate_async(self, prompt):
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )
                return response.choices[0].message.content

        llm_provider = OpenAIWrapper(settings.openai_api_key)
        evaluator = QuizEvaluator(llm_provider)
        evaluation_result = await evaluator.evaluate_quiz_submission(questions_data, user_answers)

        # Calculate percentage
        percentage = 0.0
        if evaluation_result["max_possible_score"] > 0:
            percentage = (evaluation_result["total_score"] / evaluation_result["max_possible_score"]) * 100

        return {
            "total_score": evaluation_result["total_score"],
            "max_possible_score": evaluation_result["max_possible_score"],
            "percentage": round(percentage, 2),
            "evaluated_at": evaluation_result["evaluated_at"],
            "results": evaluation_result["question_results"]
        }

    except JobNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to submit quiz", content_id=content_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to evaluate quiz submission")


