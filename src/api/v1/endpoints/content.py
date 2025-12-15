import structlog
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Response

from src.utils import job_utils
from ..mappers.quiz_response_mapper import QuizResponseMapper

from ...dependencies import get_content_job_repository, get_file_storage, get_current_user_optional, get_current_user_conditional, get_current_user_conditional, get_db, get_quiz_repository
from ..schemas import (
    ContentProcessingRequest,
    FileProcessingResult,
    ContentJobResponse,
    ContentResults,
    ContentJobsListResponse,
    ContentTextResponse,
    FileUploadResponse,
    JobStatus,
    QuizResponse,
    QuizQuestion,
    QuizSubmission,
    QuizEvaluationResult,
    QuizResult,
    QuestionType,
)
from ....config import get_settings
from ....services.content_processor import content_processor
from ....core.exceptions import JobNotFoundError, ValidationError
from ....models.user import User
from ....models.content_job import ContentJob

logger = structlog.get_logger(__name__)
settings = get_settings()

router = APIRouter()





@router.post("/process", response_model=List[FileProcessingResult])
async def process_content(
    request: ContentProcessingRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    repo = Depends(get_content_job_repository), #REVISIT - What does this do??
    current_user: User = Depends(get_current_user_conditional)
) -> List[FileProcessingResult]:
   
    try:
        results = []

        user_id = current_user.user_id
        job = repo.create_job(user_id=user_id)

        input_config_data = []
        for input_item in request.input_config:
            input_config_data.append({
                "content_type": input_item.content_type.value,
                "id": input_item.id
            })

        # Calculate total number of questions from question_types dictionary
        total_questions = sum(request.question_types.values()) if request.question_types else 5

        job.set_input_config(
            input_config=input_config_data,
            question_types=request.question_types,
            difficulty_level=request.difficulty_level.value,
            num_questions=total_questions,
            generate_summary=request.generate_summary,
            llm_provider=request.llm_provider.value
        )
        job.collection_name = request.collection_name
        job.should_add_to_collection = request.should_add_to_collection

        # Add structured_response to input_config for processing logic
        job_input_config = job.input_config_dict or {}
        job_input_config["structured_response"] = request.structured_response
        job.input_config_dict = job_input_config

        repo.update_job(job)

        background_tasks.add_task(
            content_processor.process_content_background_sync,
            job.id
        )


        #REVISIT - response should be list of indivual files. 
        for data in input_config_data:
            results.append(FileProcessingResult(
                file_id=data["id"],
                job_id=job.id,
                status=JobStatus.PENDING,
                message="File processing started successfully"
            ))

        logger.info(
            "Multimodal content processing job created",
            job_id=job.id,
            input_config=input_config_data,
            question_types=request.question_types
        )

        if any(result.status == JobStatus.FAILED for result in results):
            response.status_code = 207
        elif any(result.status in [JobStatus.RUNNING, JobStatus.SUCCESS] and result.job_id for result in results):
            response.status_code = 207
        else:
            response.status_code = 207

        return results

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to process content request", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process content request")


@router.get("/{job_id}/status", response_model=ContentJobResponse)
async def get_job_status(
    job_id: int,
    repo = Depends(get_content_job_repository),
    current_user: User = Depends(get_current_user_conditional)
) -> ContentJobResponse:
    try:
        job = repo.get(job_id)
        if not job or job.user_id != current_user.user_id:
            raise HTTPException(status_code=404, detail="Job not found")

        return ContentJobResponse(
            id=job.id,
            status=job.status,
            progress=job.progress,
            created_at=job.created_at,
            completed_at=job.completed_at,
            title=job.title,
            error_message=job.error_message,
            input_url=job.input_url,
            file_ids=job.file_ids
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get job status", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve job status")


@router.get("/{job_id}/results", response_model=ContentResults)
async def get_job_results(
    job_id: int,
    repo = Depends(get_content_job_repository),
    current_user: User = Depends(get_current_user_conditional)
) -> ContentResults:
    try:
        job = job_utils.check_job_exists(job_id, repo)
        if job.user_id != current_user.user_id:
            raise HTTPException(status_code=404, detail="Job not found")

        processing_duration = None
        if job.completed_at and job.created_at:
            processing_duration = int((job.completed_at - job.created_at).total_seconds())

        return ContentResults(
            job_id=job.id,
            status=job.status,
            title=job.title,
            processing_duration_seconds=processing_duration,
            created_at=job.created_at,
            completed_at=job.completed_at
        )

    except JobNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get job results", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve job results")



@router.get("/{job_id}/content", response_model=ContentTextResponse)
async def get_job_content(
    job_id: int,
    repo = Depends(get_content_job_repository),
    current_user: User = Depends(get_current_user_conditional)
) -> ContentTextResponse:
    try:
        job = job_utils.check_job_exists(job_id, repo)
        if job.user_id != current_user.user_id:
            raise HTTPException(status_code=404, detail="Job not found")
        return ContentTextResponse(content_text=job.content_text)

    except JobNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get content", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve content")


@router.get("/jobs", response_model=ContentJobsListResponse)
async def get_jobs_list(
    limit: int = 50,
    offset: int = 0,
    repo = Depends(get_content_job_repository),
    current_user: User = Depends(get_current_user_conditional)
) -> ContentJobsListResponse:
    try:
        jobs = repo.get_jobs_by_user(current_user.user_id, limit=limit, offset=offset)
        total_count = repo.session.query(ContentJob).filter(ContentJob.user_id == current_user.user_id).count()

        #REVISIT - Can we apply DRY principle here?
        job_responses = []
        for job in jobs:
            job_responses.append(ContentJobResponse(
                id=job.id,
                status=job.status,
                progress=job.progress,
                created_at=job.created_at,
                completed_at=job.completed_at,
                title=job.title,
                error_message=job.error_message,
                input_url=job.input_url,
                file_ids=job.file_ids
            ))

        return ContentJobsListResponse(
            total=total_count,
            jobs=job_responses
        )

    except Exception as e:
        logger.error("Failed to get jobs list", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve jobs list")


@router.delete("/{job_id}")
async def delete_job(
    job_id: int,
    repo = Depends(get_content_job_repository),
    current_user: User = Depends(get_current_user_conditional)
):
    try:
        job = repo.get(job_id)
        if not job or job.user_id != current_user.user_id:
            raise HTTPException(status_code=404, detail="Job not found")

        success = repo.delete_job(job_id)
        if not success:
            raise HTTPException(status_code=404, detail="Job not found")

        logger.info("Job deleted successfully", job_id=job_id)
        return {"message": "Job deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete job", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete job")


@router.delete("/")
async def delete_all_jobs(
    repo = Depends(get_content_job_repository)
):
    """Delete all jobs from the database and reset auto-increment."""
    try:
        from sqlalchemy import delete, text
        from ....models.content_job import ContentJob
        from ....models.quiz_question import QuizQuestion

        # Delete all quiz questions first (dependent on jobs)
        repo.session.execute(delete(QuizQuestion))
        
        # Delete all jobs
        result = repo.session.execute(delete(ContentJob))
        deleted_count = result.rowcount

        # Reset auto-increment to start from 1 (SQLite specific)
        if repo.session.bind.dialect.name == "sqlite":
            repo.session.execute(text("DELETE FROM sqlite_sequence WHERE name='content_jobs'"))

        repo.session.commit()

        logger.info("All jobs deleted and ID reset", deleted_count=deleted_count)
        return {
            "message": "All jobs deleted successfully and ID counter reset",
            "deleted_count": deleted_count
        }
    except Exception as e:
        logger.error("Failed to delete all jobs", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete all jobs")



@router.get("/supported-types")
async def get_supported_types():
    return {
        "supported_types": ["youtube", "web_url", "collection", "files"],
        "file_limits": {
            "pdf": "10MB",
            "docx": "5MB",
            "doc": "5MB"
        },
        "supported_extensions": [".pdf", ".docx", ".doc"],
        "url_support": ["YouTube videos", "Web pages (HTML content)"]
    }


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




router.get("/{job_id}/quiz/results", response_model=QuizEvaluationResult)
async def get_job_quiz_results(
    job_id: int,
    repo = Depends(get_content_job_repository),
    quiz_repo = Depends(get_quiz_repository)
) -> QuizEvaluationResult:
    try:
        job = job_utils.check_job_exists(job_id, repo)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        quiz_questions_db = quiz_repo.get_questions_by_job_id(job_id)
        if not quiz_questions_db:
            raise HTTPException(status_code=500, detail="Content not found - quiz questions were not generated during processing")

        return QuizEvaluationResult(
            total_score=job.total_score,
            max_possible_score=job.max_possible_score,
            percentage=job.percentage,
            results=job.results
        )
    except JobNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get quiz results", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve quiz results")