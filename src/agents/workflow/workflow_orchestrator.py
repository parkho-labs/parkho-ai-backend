from typing import Dict, Any
from datetime import datetime
import structlog
from sqlalchemy.orm import Session

from .job_status_manager import JobStatusManager

from ..question_generator import QuestionGeneratorAgent
from ...services.llm_service import LLMService
# from ...strategies.strategy_factory import ContentProcessingStrategyFactory # REMOVED
# from ...strategies.base_strategy import ProcessingStatus # REMOVED
from ...utils.database_utils import DatabaseService
from ...utils.validation_utils import validate_job_exists
from ...exceptions import WorkflowError
from ...services.rag_client import rag_client, RagQueryRequest
from ...config import get_settings
import time

logger = structlog.get_logger(__name__)


class WorkflowOrchestrator:
    def __init__(self, db_session: Session):
        self.db_service = DatabaseService(db_session)
        self.job_manager = JobStatusManager(self.db_service)
        self.llm_service = None

        try:
            self.rag_client = rag_client
            self.rag_enabled = True
        except Exception as e:
            logger.warning("rag_client_initialization_failed", error=str(e))
            self.rag_client = None
            self.rag_enabled = False
        self.question_generator = QuestionGeneratorAgent()
        
        # Initialize LLM Service
        try:
            settings = get_settings()
            self.llm_service = LLMService(
                openai_api_key=settings.openai_api_key,
                anthropic_api_key=settings.anthropic_api_key,
                google_api_key=settings.google_api_key
            )
        except Exception as e:
            logger.error("llm_service_initialization_failed", error=str(e))
            # workflow will likely fail later if this didn't work

    async def process_content(self, job_id: int) -> None:
        logger.info("workflow_started", job_id=job_id)
        start_time = time.time()

        try:
            job = await self._validate_and_get_job(job_id)
            await self.job_manager.mark_job_started(job_id)

            # --- 1. Validate Input & RAG ---
            collection_name = job.collection_name
            if not collection_name:
                input_config = job.input_config_dict or {}
                for source in input_config.get("input_config", []):
                    if source.get("content_type") == "collection":
                        collection_name = source.get("id")
                        break
            
            if not collection_name:
                raise ValueError("No collection name provided. RAG-based processing requires a collection.")

            if not self.rag_client:
                raise WorkflowError("RAG Client is not available but is required for processing.")

            # --- 2. Retrieve Context ---
            await self.job_manager.update_job_progress(job_id, 20.0, "Retrieving content from RAG...")
            try:
                # Use collection name as topic query to retrieve relevant context
                request = RagQueryRequest(
                    query=collection_name,
                    top_k=50
                )
                retrieve_response = await self.rag_client.retrieve_content(
                    user_id=job.user_id,
                    request=request
                )
                if retrieve_response and retrieve_response.success:
                     content_text = "\n\n".join([c.chunk_text for c in retrieve_response.results])
                else:
                     content_text = ""
            except Exception as e:
                logger.error("rag_retrieval_failed", job_id=job_id, error=str(e))
                raise WorkflowError(f"Failed to retrieve context from RAG: {str(e)}")

            if not content_text:
                raise ValueError(f"No content found in collection '{collection_name}' (or RAG service returned empty).")

            title = job.title or collection_name

            # --- 3. Generate Summary ---
            summary = ""
            if job.input_config_dict.get("generate_summary", True):
                await self.job_manager.update_job_progress(job_id, 40.0, "Generating summary...")
                try:
                    summary = await self._generate_summary(content_text)
                except Exception as e:
                    logger.warning("summary_generation_failed", job_id=job_id, error=str(e))
                    summary = "Summary generation failed."

            # --- 4. Generate Questions ---
            await self.job_manager.update_job_progress(job_id, 70.0, "Generating quiz questions...")
            rag_context = content_text
            
            agent_data = {
                "transcript": content_text,
                "title": title,
                "rag_context": rag_context,
                "subject_type": "general", 
                "question_types": job.input_config_dict.get("question_types", {"multiple_choice": 5}),
                "difficulty_level": job.input_config_dict.get("difficulty_level", "intermediate")
            }
            
            try:
                agent_result = await self.question_generator.run(job_id, agent_data)
                questions = agent_result.get("questions", [])
            except Exception as e:
                logger.error("question_generation_failed", job_id=job_id, error=str(e))
                raise WorkflowError(f"Question generation failed: {str(e)}")

            # --- 5. Finalize ---
            await self.job_manager.update_job_progress(job_id, 90.0, "Finalizing job")
            
            result_data = {
                "summary": summary,
                "content": content_text,
                "questions": questions,
                "title": title,
                "metadata": {
                    "collection_name": collection_name,
                    "content_length": len(content_text),
                    "processing_method": "rag_only",
                    "processing_time": time.time() - start_time
                }
            }
            
            await self._finalize_job(job_id, job, result_data)
            await self.job_manager.mark_job_completed(job_id)
            logger.info("workflow_completed_successfully", job_id=job_id)

        except Exception as e:
            logger.error("workflow_failed", job_id=job_id, error=str(e), exc_info=True)
            await self.job_manager.mark_job_failed(job_id, str(e))
            # Re-raise if needed or suppress
            raise WorkflowError(f"Content processing failed: {str(e)}")

    async def _validate_and_get_job(self, job_id: int):
        job = self.job_manager.get_job(job_id)
        validate_job_exists(job, job_id)
        return job

    async def _generate_summary(self, content: str) -> str:
        if not self.llm_service:
            return "Summary unavailable (LLM service not initialized)."
            
        max_chars = 100000
        truncated_content = content[:max_chars]
        
        system_prompt = "You are an expert educational summarizer. Create a concise, structured summary of the provided content."
        user_prompt = f"Please summarize the following content, highlighting key concepts and main points:\\n\\n{truncated_content}"
        
        return await self.llm_service.generate_with_fallback(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
            max_tokens=1000
        )

    async def _finalize_job(self, job_id: int, job, result_data: Dict[str, Any]):
        try:
            # We skip 'add_content_to_collection' because in this RAG-only flow, 
            # the content typically CAME from the collection. 
            # If we wanted to add generated summary back, we could, but let's keep it simple for now.

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