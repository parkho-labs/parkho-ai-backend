from typing import Dict, Any, List
from datetime import datetime
import asyncio
import structlog

from .content_analyzer import ContentAnalyzerAgent
from .question_generator import QuestionGeneratorAgent
from ..models.content_job import ContentJob
from ..core.database import SessionLocal
from ..core.websocket_manager import websocket_manager
from ..parsers.content_parser_factory import ContentParserFactory
from ..services.file_storage import FileStorageService
from ..repositories.file_repository import FileRepository
from ..services.rag_integration_service import get_rag_service

logger = structlog.get_logger(__name__)


class ContentWorkflow:
    def __init__(self):
        self.content_analyzer = ContentAnalyzerAgent()
        self.question_generator = QuestionGeneratorAgent()
        self.parser_factory = ContentParserFactory()
        try:
            self.rag_service = get_rag_service()
        except Exception as e:
            logger.warning(f"RAG service initialization failed: {e}")
            self.rag_service = None

    async def process_content(self, job_id: int):
        logger.info("Starting content processing workflow", job_id=job_id)

        try:
            await self.mark_job_started(job_id)
            job = await self.validate_and_get_job(job_id)

            combined_content, combined_title = await self.parse_all_content_sources(job)
            rag_context = await self.retrieve_rag_context_if_needed(job, combined_title, combined_content)

            analysis_result = await self.run_content_analysis(job_id, job, combined_content, combined_title, rag_context)
            questions_result = await self.run_question_generation(job_id, analysis_result)

            await self.finalize_job(job_id, combined_content, combined_title, analysis_result, questions_result)
            await self.mark_job_completed(job_id)

            logger.info("Content processing workflow completed", job_id=job_id)

        except Exception as e:
            logger.error("Content processing workflow failed", job_id=job_id, error=str(e))
            await self.mark_job_failed(job_id, str(e))
            raise

    async def validate_and_get_job(self, job_id: int):
        job = await self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        input_config = job.input_config_dict
        if not input_config:
            raise ValueError("No input configuration found")

        input_sources = input_config.get("input_config", [])
        if not input_sources:
            raise ValueError("No input sources found")

        return job

    async def parse_all_content_sources(self, job):
        await self.update_job_progress(job.id, 10.0, "Parsing content...")

        input_sources = job.input_config_dict.get("input_config", [])
        parse_tasks = self.create_parse_tasks(input_sources)
        results = await asyncio.gather(*parse_tasks, return_exceptions=True)

        return self.combine_parsed_results(results)

    def create_parse_tasks(self, input_sources):
        parse_tasks = []
        for source in input_sources:
            content_type = source.get("content_type")
            source_id = source.get("id")

            if content_type in ["pdf", "docx"]:
                parse_tasks.append(self._parse_file(content_type, source_id))
            else:
                parse_tasks.append(self._parse_url(content_type, source_id))

        return parse_tasks

    def combine_parsed_results(self, results):
        all_content = []
        all_titles = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Failed to parse content source {i}: {str(result)}")
                continue

            if result and result.success:
                all_content.append(result.content)
                if result.title:
                    all_titles.append(result.title)
            else:
                logger.error(f"Content source {i} failed or returned no content. Result: {result}")
                if result and hasattr(result, 'error'):
                    logger.error(f"Error details: {result.error}")

        if not all_content:
            raise ValueError("No content could be extracted from provided sources")

        combined_content = "\n\n--- NEXT DOCUMENT ---\n\n".join(all_content)
        combined_title = " & ".join(all_titles) if all_titles else "Processed Content"

        return combined_content, combined_title

    async def retrieve_rag_context_if_needed(self, job, combined_title, combined_content):
        if not job.collection_name:
            return ""

        if not self.rag_service:
            logger.warning("Collection specified but RAG service unavailable", job_id=job.id)
            return ""

        await self.update_job_progress(job.id, 25.0, "Retrieving collection context...")

        try:
            context_query = combined_title or combined_content[:200]
            rag_context = await self.rag_service.get_collection_context(
                job.collection_name,
                context_query
            )

            if rag_context:
                job.rag_context_used = True
                await self.update_job_in_db(job)
                logger.info("RAG context retrieved", job_id=job.id, context_length=len(rag_context))

            return rag_context

        except Exception as e:
            logger.warning("Failed to retrieve RAG context", job_id=job.id, error=str(e))
            return ""

    async def run_content_analysis(self, job_id, job, combined_content, combined_title, rag_context):
        await self.update_job_progress(job_id, 30.0, "Analyzing content...")

        analysis_data = {
            "transcript": combined_content,
            "video_metadata": {"title": combined_title},
            "rag_context": rag_context,
            **job.input_config_dict
        }

        return await self.content_analyzer.run(job_id, analysis_data)

    async def run_question_generation(self, job_id, analysis_result):
        await self.update_job_progress(job_id, 70.0, "Generating questions...")
        return await self.question_generator.run(job_id, analysis_result)

    async def finalize_job(self, job_id: int, content_text: str, title: str, analysis_result: Dict[str, Any], questions_result: Dict[str, Any]):
        db = SessionLocal()
        try:
            job = db.query(ContentJob).filter(ContentJob.id == job_id).first()
            if job:
                job.title = title
                output_config = {
                    "content_text": content_text,
                    "summary": analysis_result.get("summary"),
                    "questions": questions_result.get("questions", []),
                    "metadata": {
                        "analysis": analysis_result.get("metadata", {}),
                        "question_generation": questions_result.get("metadata", {})
                    }
                }
                job.output_config_dict = output_config
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _detect_url_type(self, url: str) -> str:
        if "youtube.com" in url or "youtu.be" in url:
            return "youtube"
        return "web_url"

    async def get_job(self, job_id: int) -> ContentJob:
        db = SessionLocal()
        try:
            return db.query(ContentJob).filter(ContentJob.id == job_id).first()
        finally:
            db.close()

    #Should be in helper class? doesn't look cgood int this file?
    async def update_job_in_db(self, job: ContentJob):
        """Update job in database"""
        db = SessionLocal()
        try:
            db.merge(job)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    #REVISIT - for all three methods, create a common method, pass job status and progress and name the method, update job status. 
    async def mark_job_started(self, job_id: int):
        db = SessionLocal()
        try:
            job = db.query(ContentJob).filter(ContentJob.id == job_id).first()
            if job:
                job.status = "processing" #REVISIT - use enumbs here no hardcoding
                job.progress = 0.0
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    async def mark_job_completed(self, job_id: int):
        db = SessionLocal()
        try:
            job = db.query(ContentJob).filter(ContentJob.id == job_id).first()
            if job:
                job.status = "completed"
                job.completed_at = datetime.now()
                job.progress = 100.0
            db.commit()

            await websocket_manager.broadcast_to_job(job_id, {
                "type": "completion",
                "status": "completed",
                "message": "Content processing completed! Your results are ready.",
                "progress": 100.0
            })
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    async def mark_job_failed(self, job_id: int, error_message: str):
        db = SessionLocal()
        try:
            job = db.query(ContentJob).filter(ContentJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.completed_at = datetime.now()
                job.error_message = error_message
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    async def update_job_progress(self, job_id: int, progress: float, message: str = None):
        db = SessionLocal()
        try:
            job = db.query(ContentJob).filter(ContentJob.id == job_id).first()
            if job:
                job.progress = progress
            db.commit()

            websocket_data = {
                "type": "progress",
                "progress": progress,
                "status": "processing"
            }
            if message:
                websocket_data["message"] = message

            await websocket_manager.broadcast_to_job(job_id, websocket_data)

        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    async def _parse_url(self, content_type: str, url: str):
        parser = self.parser_factory.get_parser(content_type)
        if not parser:
            raise ValueError(f"No parser available for content type: {content_type}")
        return await parser.parse(url)

    async def _parse_file(self, content_type: str, file_id: str):
        db = SessionLocal()
        try:
            file_repo = FileRepository(db)
            file_storage = FileStorageService(file_repo)
            file_path = file_storage.get_file_path(file_id)

            if not file_path:
                raise ValueError(f"File not found: {file_id}")

            parser = self.parser_factory.get_parser(content_type)
            if not parser:
                raise ValueError(f"No parser available for content type: {content_type}")

            return await parser.parse(file_path)
        finally:
            db.close()