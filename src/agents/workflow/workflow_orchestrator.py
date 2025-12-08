from typing import Dict, Any
from datetime import datetime
import structlog
from sqlalchemy.orm import Session

from .job_status_manager import JobStatusManager
from .content_parsing_coordinator import ContentParsingCoordinator
from ..question_generator import QuestionGeneratorAgent
from ...strategies.strategy_factory import ContentProcessingStrategyFactory
from ...strategies.base_strategy import ProcessingStatus
from ...utils.database_utils import DatabaseService
from ...utils.validation_utils import validate_job_exists
from ...exceptions import WorkflowError
from ...services.rag_integration_service import get_rag_service

logger = structlog.get_logger(__name__)


class WorkflowOrchestrator:
    def __init__(self, db_session: Session):
        self.db_service = DatabaseService(db_session)
        self.job_manager = JobStatusManager(self.db_service)
        self.parsing_coordinator = ContentParsingCoordinator(db_session)
        try:
            self.rag_service = get_rag_service()
            self.rag_enabled = True
        except Exception as e:
            logger.warning("rag_service_initialization_failed", error=str(e))
            self.rag_service = None
            self.rag_enabled = False
        self.question_generator = QuestionGeneratorAgent()
        self.strategy_factory = ContentProcessingStrategyFactory()

    async def process_content(self, job_id: int) -> None:
        logger.info("workflow_started", job_id=job_id)

        try:
            job = await self._validate_and_get_job(job_id)
            await self.job_manager.mark_job_started(job_id)

            await self._execute_strategy_with_fallback(job_id, job)

        except Exception as e:
            logger.error("workflow_failed", job_id=job_id, error=str(e))
            await self.job_manager.mark_job_failed(job_id, str(e))
            raise WorkflowError(f"Content processing failed: {str(e)}")

    async def _validate_and_get_job(self, job_id: int):
        job = self.job_manager.get_job(job_id)
        validate_job_exists(job, job_id)
        return job

    async def _execute_strategy_with_fallback(self, job_id: int, job):
        input_config=job.input_config_dict or {}
        selection_result = self.strategy_factory.select_strategy(
            input_config=input_config.get("input_config", []),
            job_config=job.output_config_dict or {}
        )
        
        strategy = selection_result.strategy
        strategy_name = selection_result.strategy_name

        try:
            result = await strategy.process_content(job_id)

            if result.status == ProcessingStatus.SUCCESS:
                await self._handle_successful_completion(job_id, job, result)
            else:
                await self._handle_processing_failure(job_id, result)

        except Exception as e:
            logger.warning("primary_strategy_failed", job_id=job_id, error=str(e), strategy=strategy_name)
            await self._try_fallback_strategy(job_id, job, failed_strategy_name=strategy_name)

    async def _handle_successful_completion(self, job_id: int, job, result):
        await self.job_manager.update_job_progress(job_id, 90.0, "Finalizing job")

        # Create data dict for finalize_job (which expects a dict)
        result_data = {
            "summary": result.summary,
            "content": result.content_text,
            "questions": result.questions,
            "title": result.metadata.get("title") if result.metadata else None,
            "metadata": result.metadata
        }
        
        await self._finalize_job(job_id, job, result_data)

        await self.job_manager.mark_job_completed(job_id)

        logger.info("workflow_completed_successfully", job_id=job_id)

    async def _handle_processing_failure(self, job_id: int, result):
        error_message = result.error or "Processing failed with unknown error"
        await self.job_manager.mark_job_failed(job_id, error_message)
        raise WorkflowError(error_message)

    async def _try_fallback_strategy(self, job_id: int, job, failed_strategy_name: str):
        try:
            await self.job_manager.update_job_progress(job_id, 10.0, "Trying fallback processing method")

            input_config=job.input_config_dict or {}
            fallback_strategy = self.strategy_factory.get_fallback_strategy(
                failed_strategy=failed_strategy_name,
                input_config=input_config.get("input_config", []),
                config=job.output_config_dict or {}
            )
            
            if not fallback_strategy:
                raise WorkflowError("No fallback strategy available")

            result = await fallback_strategy.process_content(job_id)

            if result.status == ProcessingStatus.SUCCESS:
                await self._handle_successful_completion(job_id, job, result)
            else:
                await self._handle_processing_failure(job_id, result)

        except Exception as fallback_error:
            logger.error("fallback_strategy_failed", job_id=job_id, error=str(fallback_error))
            await self.job_manager.mark_job_failed(job_id, f"Both primary and fallback strategies failed: {str(fallback_error)}")
            raise WorkflowError(f"All processing strategies failed: {str(fallback_error)}")

    async def _finalize_job(self, job_id: int, job, result_data: Dict[str, Any]):
        try:
            if self.rag_enabled and hasattr(job, 'should_add_to_collection') and job.should_add_to_collection:
                content = result_data.get("content", "")
                title = result_data.get("title", "")
                summary = result_data.get("summary", "")
                await self._add_content_to_collection(job, content, title, summary)

            job.completed_at = datetime.utcnow()
            
            job.update_output_config(
                summary=result_data.get("summary"),
                content_text=result_data.get("content"),
                questions=result_data.get("questions")
            )

            if "questions" in result_data:
                await self._save_questions(job_id, result_data["questions"])

            self.job_manager.update_job_in_db(job)

            logger.info("job_finalized", job_id=job_id)

        except Exception as e:
            logger.error("job_finalization_failed", job_id=job_id, error=str(e))
            raise WorkflowError(f"Failed to finalize job: {str(e)}")

    async def _save_questions(self, job_id: int, questions_data):
        try:
            questions_list = []
            if isinstance(questions_data, list):
                questions_list = questions_data
            elif isinstance(questions_data, dict) and "questions" in questions_data:
                questions_list = questions_data["questions"]

            if questions_list:
                await self.question_generator.save_questions_bulk(job_id, questions_list)
                logger.info("questions_saved", job_id=job_id, count=len(questions_list))

        except Exception as e:
            logger.warning("question_saving_failed", job_id=job_id, error=str(e))

    async def _add_content_to_collection(self, job, content: str, title: str, summary: str = ""):
        if not self.rag_service or not getattr(job, "collection_name", None):
            return

        try:
            # Format content with metadata for better context
            full_content = f"Title: {title}\n"
            if summary:
                full_content += f"\nSummary: {summary}\n"
            full_content += f"\nContent:\n{content or ''}"

            filename = f"job_{job.id}_{(title or 'content')[:50].replace(' ', '_')}.txt"
            
            success = await self.rag_service.upload_and_link_content(
                collection_name=job.collection_name,
                content_data={
                    "content": full_content,
                    "filename": filename,
                    "content_type": "text"
                }
            )
            if success:
                logger.info(
                    "content_added_to_collection",
                    job_id=job.id,
                    collection=job.collection_name,
                    filename=filename
                )
        except Exception as e:
            logger.warning("rag_linking_failed", job_id=job.id, error=str(e))