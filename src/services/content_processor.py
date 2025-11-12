import asyncio
import structlog
from concurrent.futures import ThreadPoolExecutor
import threading
from typing import Dict, Any, List

from ..agents.content_workflow import ContentWorkflow
from ..services.question_enhancement_service import QuestionEnhancementService
from ..config import get_settings
from ..services.rag_integration_service import get_rag_service
from ..core.database import SessionLocal
from ..models.content_job import ContentJob

logger = structlog.get_logger(__name__)
settings = get_settings()


class ContentProcessorService:
    def __init__(self):
        self.workflow = ContentWorkflow()
        self.question_enhancement_service = QuestionEnhancementService()
        self.executor = ThreadPoolExecutor(max_workers=settings.max_concurrent_jobs)
        self.running_jobs = set()
        try:
            self.rag_service = get_rag_service()
        except Exception as e:
            logger.warning(f"RAG service initialization failed: {e}")
            self.rag_service = None

    def process_content_background_sync(self, job_id: int):
        def run_in_thread():
            logger.info("Content processing thread started", job_id=job_id)
            try:
                asyncio.run(self.process_content_background(job_id))
            except Exception as e:
                logger.error("Content processing thread failed", job_id=job_id, error=str(e), exc_info=True)

        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()

    async def process_content_background(self, job_id: int):
        if job_id in self.running_jobs:
            logger.warning("Job already running", job_id=job_id)
            return

        self.running_jobs.add(job_id)

        try:
            # Check if this is a structured response (question generation) request
            job = await self.get_job(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")

            input_config = job.input_config_dict or {}
            structured_response = input_config.get("structured_response", False)

            if structured_response and settings.question_enhancement_enabled:
                logger.info("Processing with QuestionEnhancementService (structured response)", job_id=job_id)
                await self.process_with_question_enhancement(job_id, job)
            else:
                logger.info("Processing with ContentWorkflow (standard processing)", job_id=job_id)
                await self.workflow.process_content(job_id)

            # Process collection linking regardless of processing type
            await self.process_collection_linking(job_id)

        except Exception as e:
            logger.error("Content processing failed", job_id=job_id, error=str(e), exc_info=True)
        finally:
            self.running_jobs.discard(job_id)
            logger.info("Job removed from running jobs", job_id=job_id)

    def is_job_running(self, job_id: int) -> bool:
        return job_id in self.running_jobs

    def get_running_jobs_count(self) -> int:
        return len(self.running_jobs)

    async def process_with_question_enhancement(self, job_id: int, job: ContentJob):
        try:
            # Mark job as processing
            await self.update_job_status(job_id, "processing", 0.0)

            # Extract input configuration
            input_config = job.input_config_dict or {}

            # Build query from input config (fallback if no explicit query)
            query = self.build_query_from_config(input_config)

            # Extract input sources
            input_sources = input_config.get("input_config", [])

            # Prepare options for question enhancement service
            enhancement_options = {
                "num_questions": input_config.get("num_questions", 5),
                "difficulty_level": input_config.get("difficulty_level", "intermediate"),
                "question_types": input_config.get("question_types", ["multiple_choice"]),
                "llm_provider": input_config.get("llm_provider", "openai"),
                "collection_name": job.collection_name,
                "should_add_to_collection": job.should_add_to_collection
            }

            logger.info("Starting question enhancement processing",
                       job_id=job_id,
                       query=query,
                       input_sources_count=len(input_sources),
                       options=enhancement_options)

            # Process with QuestionEnhancementService
            enhanced_response = await self.question_enhancement_service.process_question_request(
                query=query,
                input_config=input_sources,
                options=enhancement_options,
                job_id=job_id
            )

            # Update job with enhanced response
            await self.update_job_with_enhanced_response(job_id, enhanced_response, query)

            logger.info("Question enhancement processing completed successfully",
                       job_id=job_id,
                       questions_count=len(enhanced_response.get("questions", [])))

        except Exception as e:
            logger.error("Question enhancement processing failed", job_id=job_id, error=str(e))
            await self.update_job_status(job_id, "failed", error_message=str(e))
            raise

    def build_query_from_config(self, input_config: Dict[str, Any]) -> str:
        num_questions = input_config.get("num_questions", 5)
        question_types = input_config.get("question_types", ["multiple_choice"])
        difficulty_level = input_config.get("difficulty_level", "intermediate")

        # Build a query that describes what we want
        type_text = " and ".join(question_types).replace("_", " ")
        query = f"Generate {num_questions} {type_text} questions at {difficulty_level} level"

        return query

    async def update_job_with_enhanced_response(
        self,
        job_id: int,
        enhanced_response: Dict[str, Any],
        query: str
    ):
        db = SessionLocal()
        try:
            job = db.query(ContentJob).filter(ContentJob.id == job_id).first()
            if job:
                # Set the output_config to the enhanced response structure
                job.output_config_dict = enhanced_response

                # Set title if not already set
                if not job.title:
                    job.title = enhanced_response.get("content_text", f"Questions for: {query}")

                # Mark as completed
                job.status = "completed"
                job.progress = 100.0
                from datetime import datetime
                job.completed_at = datetime.now()

            db.commit()

            # Send WebSocket completion notification
            from ..core.websocket_manager import websocket_manager
            await websocket_manager.broadcast_to_job(job_id, {
                "type": "completion",
                "status": "completed",
                "message": "Question generation completed! Your results are ready.",
                "progress": 100.0
            })

        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    async def update_job_status(
        self,
        job_id: int,
        status: str,
        progress: float = None,
        error_message: str = None
    ):
        db = SessionLocal()
        try:
            job = db.query(ContentJob).filter(ContentJob.id == job_id).first()
            if job:
                job.status = status
                if progress is not None:
                    job.progress = progress
                if error_message:
                    job.error_message = error_message
                    from datetime import datetime
                    job.completed_at = datetime.now()

            db.commit()

        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    async def process_collection_linking(self, job_id: int):
        try:
            job = await self.get_job(job_id)
            if not job or not job.should_add_to_collection or not job.collection_name:
                logger.debug("No collection linking required", job_id=job_id)
                return

            if not self.rag_service:
                logger.warning("Collection linking requested but RAG service unavailable", job_id=job_id)
                return

            logger.info("Starting collection linking", job_id=job_id, collection=job.collection_name)

            # Get processed content
            output_config = job.output_config_dict
            if not output_config or not output_config.get("content_text"):
                logger.warning("No processed content available for collection linking", job_id=job_id)
                return

            # Prepare content for upload
            content_text = output_config.get("content_text", "")
            title = job.title or "Processed Content"
            summary = output_config.get("summary", "")

            # Combine content with summary for better context
            combined_content = f"Title: {title}\n\nSummary: {summary}\n\nContent:\n{content_text}"

            # Upload content to RAG engine and link to collection
            success = await self.rag_service.upload_and_link_content(
                collection_name=job.collection_name,
                content_data={
                    "content": combined_content,
                    "filename": f"job_{job_id}_{title.replace(' ', '_')}.txt",
                    "content_type": "text"
                }
            )

            if success:
                logger.info("Content successfully linked to collection",
                           job_id=job_id, collection=job.collection_name)
            else:
                logger.error("Failed to link content to collection",
                            job_id=job_id, collection=job.collection_name)

        except Exception as e:
            logger.error("Collection linking failed", job_id=job_id, error=str(e))

    async def get_job(self, job_id: int) -> ContentJob:
        db = SessionLocal()
        try:
            return db.query(ContentJob).filter(ContentJob.id == job_id).first()
        finally:
            db.close()


content_processor = ContentProcessorService()