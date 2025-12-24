import asyncio
import structlog
from concurrent.futures import ThreadPoolExecutor
import threading
from typing import Dict, Any, List

from ..agents.content_workflow import ContentWorkflow
from ..config import get_settings
from ..services.rag import core_rag_client as rag_client
from ..core.database import SessionLocal
from ..models.content_job import ContentJob

logger = structlog.get_logger(__name__)
settings = get_settings()


class ContentProcessorService:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=settings.max_concurrent_jobs)
        self.running_jobs = set()
        try:
            self.rag_client = rag_client
        except Exception as e:
            logger.warning(f"RAG client initialization failed: {e}")
            self.rag_client = None

    def process_content_background_sync(self, job_id: int):
        """Synchronous wrapper for async content processing that can be run in thread pool."""
        logger.info("=== CONTENT PROCESSOR START ===")
        logger.info("Content processing started", job_id=job_id)

        async def run_async():
            try:
                await self.process_content_background(job_id)
            except Exception as e:
                logger.error("=== CONTENT PROCESSOR FAILED ===")
                logger.error("Content processing failed", job_id=job_id, error=str(e), exc_info=True)
                raise

            logger.info("=== CONTENT PROCESSOR COMPLETED SUCCESSFULLY ===")  # Only if no exception

        # Always create a new event loop in the thread since we're running in ThreadPoolExecutor
        try:
            # This ensures we have a clean event loop in the thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(run_async())
                logger.info(f"Task completed successfully for job {job_id}")
            except Exception as e:
                logger.error(f"Failed to execute async task for job {job_id}: {e}")
                raise
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Failed to execute async task for job {job_id}: {e}")
            raise

    async def process_content_background(self, job_id: int):
        if job_id in self.running_jobs:
            logger.warning("Job already running", job_id=job_id)
            return

        self.running_jobs.add(job_id)

        try:
            job = await self.get_job(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")

            logger.info("Processing with ContentWorkflow", job_id=job_id)

            from ..core.database import SessionLocal
            with SessionLocal() as session:
                workflow = ContentWorkflow(session)
                await workflow.process_content(job_id)

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

    async def process_collection_linking(self, job_id: int):
        # Unsupported in new RagService (strict doc compliance)
        pass
        # try:
        #     job = await self.get_job(job_id)
        #     # ... (Logic Removed) ...
        # except Exception as e:
        #     logger.error("Collection linking failed", job_id=job_id, error=str(e))

    async def get_job(self, job_id: int) -> ContentJob:
        db = SessionLocal()
        try:
            return db.query(ContentJob).filter(ContentJob.id == job_id).first()
        finally:
            db.close()


content_processor = ContentProcessorService()