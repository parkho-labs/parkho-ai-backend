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

logger = structlog.get_logger(__name__)


class ContentWorkflow:
    def __init__(self):
        self.content_analyzer = ContentAnalyzerAgent()
        self.question_generator = QuestionGeneratorAgent()
        self.parser_factory = ContentParserFactory()

    async def process_content(self, job_id: int):
        logger.info("Starting content processing workflow", job_id=job_id)

        try:
            await self.mark_job_started(job_id)

            job = await self.get_job(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")

            input_config = job.input_config_dict
            if not input_config:
                raise ValueError("No input configuration found")

            input_sources = input_config.get("input_config", [])
            if not input_sources:
                raise ValueError("No input sources found")

            await self.update_job_progress(job_id, 10.0, "Parsing content...")

            parse_tasks = []
            for source in input_sources:
                content_type = source.get("content_type")
                source_id = source.get("id")

                if content_type in ["pdf", "docx"]:
                    parse_tasks.append(self._parse_file(content_type, source_id))
                else:
                    parse_tasks.append(self._parse_url(content_type, source_id))

            results = await asyncio.gather(*parse_tasks, return_exceptions=True)

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

            await self.update_job_progress(job_id, 30.0, "Analyzing content...")

            analysis_data = {
                "transcript": combined_content,
                "video_title": combined_title,
                **input_config
            }

            analysis_result = await self.content_analyzer.run(job_id, analysis_data)

            await self.update_job_progress(job_id, 70.0, "Generating questions...")

            questions_result = await self.question_generator.run(job_id, analysis_result)

            await self.finalize_job(job_id, combined_content, combined_title, analysis_result, questions_result)

            await self.mark_job_completed(job_id)
            logger.info("Content processing workflow completed", job_id=job_id)

        except Exception as e:
            logger.error("Content processing workflow failed", job_id=job_id, error=str(e))
            await self.mark_job_failed(job_id, str(e))
            raise

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

    async def mark_job_started(self, job_id: int):
        db = SessionLocal()
        try:
            job = db.query(ContentJob).filter(ContentJob.id == job_id).first()
            if job:
                job.status = "processing"
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