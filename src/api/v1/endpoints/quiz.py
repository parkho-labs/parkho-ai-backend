import structlog
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
import openai

from src.utils import job_utils

from ...dependencies import get_quiz_repository, get_content_job_repository, get_analytics_service
from ..schemas import JobStatus, QuestionType, QuizSubmission
from ....core.exceptions import JobNotFoundError
from ....services.quiz_evaluator import QuizEvaluator
from ....config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

router = APIRouter()

#REVISIT - Why this router is empty?
@router.get("", response_model=Dict[str, Any])
async def get_content_quiz(
    content_id: int,
    quiz_repo = Depends(get_quiz_repository),
    analytics = Depends(get_analytics_service)
) -> Dict[str, Any]:
    try:
        
        questions = quiz_repo.get_questions_by_job_id(content_id)
        if not questions:
            raise HTTPException(
                status_code=404,
                detail="No quiz questions found for this video"
            )

        #TODO add video time here to track video analytics
        quiz_questions = []
        for q in questions:
            question_data = {
                "question_id": q.question_id,
                "question": q.question,
                "type": q.type,
                "max_score": q.max_score
            }

            if q.type == QuestionType.MULTIPLE_CHOICE and "options" in q.answer_config:
                question_data["options"] = q.answer_config["options"]

            if q.context:
                question_data["context"] = q.context

            quiz_questions.append(question_data)

        total_score = quiz_repo.get_total_score_by_job_id(content_id)
        analytics.track_quiz_start(user_id=1, quiz_id=content_id) 

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


#TODO Change return type to a proper response model and not dictionary
#REVISIT This is a very big and messy function need to break it
@router.post("", response_model=Dict[str, Any])
async def submit_content_quiz(
    content_id: int,
    submission: QuizSubmission,
    quiz_repo = Depends(get_quiz_repository),
    analytics = Depends(get_analytics_service)
) -> Dict[str, Any]:
    try:
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

        # Track quiz completion event
        analytics.track_quiz_completion(
            user_id=1,  # Temporary user_id=1
            quiz_id=content_id,
            score=evaluation_result["total_score"],
            duration=300  # Temporary duration, will calculate properly later
        )

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


