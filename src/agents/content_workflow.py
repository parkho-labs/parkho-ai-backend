from typing import Dict, Any, List
from datetime import datetime
import asyncio
import time
import structlog

from .question_generator import QuestionGeneratorAgent
from ..models.content_job import ContentJob
from ..core.database import SessionLocal
from ..core.websocket_manager import websocket_manager
from ..parsers.content_parser_factory import ContentParserFactory
from ..services.file_storage import FileStorageService
from ..repositories.file_repository import FileRepository
from ..services.rag_integration_service import get_rag_service
from ..strategies.strategy_factory import ContentProcessingStrategyFactory
from ..strategies.base_strategy import ProcessingStatus
from ..api.v1.schemas import JobStatus

logger = structlog.get_logger(__name__)


class ContentWorkflow:
    def __init__(self):
        self.question_generator = QuestionGeneratorAgent()
        self.parser_factory = ContentParserFactory()
        self.strategy_factory = ContentProcessingStrategyFactory()
        try:
            self.rag_service = get_rag_service()
        except Exception as e:
            logger.warning(f"RAG service initialization failed: {e}")
            self.rag_service = None

    async def process_content(self, job_id: int):
        """
        Process content using strategy pattern.

        This is the new entry point that selects and delegates to the appropriate
        content processing strategy (Complex Pipeline or Direct Gemini).
        """
        logger.info("=== CONTENT WORKFLOW START (Strategy Pattern) ===")
        logger.info("Starting content processing workflow", job_id=job_id)

        try:
            # Get job configuration to determine strategy
            with SessionLocal() as session:
                from ..repositories.content_job_repository import ContentJobRepository
                repo = ContentJobRepository(session)
                job = repo.get(job_id)

                if not job:
                    raise ValueError(f"Job {job_id} not found")

                input_config = job.input_config_dict.get("input_config", [])
                job_config = job.input_config_dict

                logger.info(
                    "Job configuration loaded for strategy selection",
                    job_id=job_id,
                    input_config=input_config,
                    job_config=job_config
                )

            # Select appropriate strategy
            strategy_result = self.strategy_factory.select_strategy(input_config, job_config)
            strategy = strategy_result.strategy
            strategy_name = strategy_result.strategy_name

            logger.info(
                "Strategy selected",
                job_id=job_id,
                strategy=strategy_name,
                reason=strategy_result.selection_reason,
                fallback_available=strategy_result.fallback_available
            )

            # Execute strategy with fallback
            result = await self._execute_strategy_with_fallback(
                job_id, strategy, strategy_name, input_config, job_config
            )

            if result.success:
                logger.info(
                    "Content processing completed successfully",
                    job_id=job_id,
                    strategy=result.strategy_used,
                    processing_time=result.processing_time_seconds
                )
            else:
                logger.error(
                    "Content processing failed",
                    job_id=job_id,
                    error=result.error,
                    strategy=result.strategy_used
                )
                raise ValueError(f"Content processing failed: {result.error}")

        except Exception as e:
            logger.error("Content workflow failed", job_id=job_id, error=str(e), exc_info=True)

            # Mark job as failed
            with SessionLocal() as session:
                from ..repositories.content_job_repository import ContentJobRepository
                repo = ContentJobRepository(session)
                repo.mark_failed(job_id, f"Workflow failed: {str(e)}")

            await websocket_manager.broadcast_to_job(job_id, {
                "type": "job_failed",
                "job_id": job_id,
                "error": str(e)
            })

            raise

    async def _execute_strategy_with_fallback(
        self,
        job_id: int,
        primary_strategy,
        primary_strategy_name: str,
        input_config: List[Dict[str, Any]],
        job_config: Dict[str, Any]
    ):
        """Execute strategy with automatic fallback on failure"""

        try:
            # Try primary strategy
            logger.info("Executing primary strategy", job_id=job_id, strategy=primary_strategy_name)
            result = await primary_strategy.process_content(job_id)

            if result.success:
                return result
            else:
                logger.warning(
                    "Primary strategy failed, attempting fallback",
                    job_id=job_id,
                    primary_strategy=primary_strategy_name,
                    error=result.error
                )

        except Exception as e:
            logger.warning(
                "Primary strategy threw exception, attempting fallback",
                job_id=job_id,
                primary_strategy=primary_strategy_name,
                error=str(e)
            )

        # Try fallback strategy
        fallback_strategy = self.strategy_factory.get_fallback_strategy(
            primary_strategy_name, input_config, job_config
        )

        if fallback_strategy:
            logger.info(
                "Executing fallback strategy",
                job_id=job_id,
                fallback_strategy=fallback_strategy.get_strategy_name()
            )

            try:
                result = await fallback_strategy.process_content(job_id)

                if result.success:
                    logger.info(
                        "Fallback strategy succeeded",
                        job_id=job_id,
                        fallback_strategy=result.strategy_used
                    )
                    return result
                else:
                    logger.error(
                        "Fallback strategy also failed",
                        job_id=job_id,
                        error=result.error
                    )

            except Exception as e:
                logger.error(
                    "Fallback strategy threw exception",
                    job_id=job_id,
                    error=str(e)
                )

        # Both strategies failed
        error_msg = f"All processing strategies failed for job {job_id}"
        logger.error(error_msg, job_id=job_id)

        from ..strategies.base_strategy import ProcessingResult, ProcessingStatus
        return ProcessingResult(
            status=ProcessingStatus.FAILED,
            error=error_msg,
            strategy_used="none"
        )

    # Legacy method - kept for backward compatibility and complex pipeline strategy
    async def process_content_legacy(self, job_id: int):
        """
        Legacy content processing method.

        This is the original implementation that's now wrapped by ComplexPipelineStrategy.
        Kept for backward compatibility and to avoid circular dependencies.
        """
        logger.info(f"=== LEGACY CONTENT WORKFLOW START ===")
        logger.info("Starting legacy content processing workflow", job_id=job_id)

        workflow_start = time.time()
        print(f"[TIMER] === WORKFLOW START ===")

        try:
            step_start = time.time()
            logger.info(f"Step 1: Marking job {job_id} as started")
            await self.mark_job_started(job_id)

            logger.info(f"Step 2: Validating and getting job {job_id}")
            job = await self.validate_and_get_job(job_id)
            logger.info(
                "Job configuration loaded",
                job_id=job_id,
                input_config=job.input_config_dict,
                has_output_config=bool(job.output_config)
            )
            step_time = time.time() - step_start
            print(f"[TIMER] Job Initialization: {step_time:.3f}s")

            step_start = time.time()
            logger.info(f"Step 3: Parsing content sources for job {job_id}")
            combined_content, combined_title, source_metadata = await self.parse_all_content_sources(job)
            logger.info(f"Content parsed - length: {len(combined_content)}, title: {combined_title}")
            logger.info("Source metadata captured", job_id=job_id, source_metadata=source_metadata)
            step_time = time.time() - step_start
            print(f"[TIMER] Content Parsing: {step_time:.3f}s")

            step_start = time.time()
            logger.info(f"Step 4: Retrieving RAG context for job {job_id}")
            rag_context = await self.retrieve_rag_context_if_needed(job, combined_title, combined_content)
            logger.info(f"RAG context retrieved - length: {len(rag_context) if rag_context else 0}")
            step_time = time.time() - step_start
            print(f"[TIMER] RAG Context Retrieval: {step_time:.3f}s")

            step_start = time.time()
            logger.info(f"Step 5: Generating summary for job {job_id}")
            summary = await self.generate_summary(job_id, combined_content, combined_title, rag_context)
            logger.info(f"Summary generated - length: {len(summary) if summary else 0}")
            step_time = time.time() - step_start
            print(f"[TIMER] Summary Generation: {step_time:.3f}s")

            step_start = time.time()
            logger.info(f"Step 6: Running question generation for job {job_id}")
            questions_result = await self.run_question_generation(job_id, job, combined_content, combined_title, rag_context)
            logger.info(f"Question generation completed - result keys: {list(questions_result.keys()) if questions_result else 'None'}")
            step_time = time.time() - step_start
            print(f"[TIMER] Question Generation: {step_time:.3f}s")

            step_start = time.time()
            logger.info(f"Step 7: Finalizing job {job_id}")
            logger.info(f"FINALIZE DEBUG - questions_result type: {type(questions_result)}")
            logger.info(f"FINALIZE DEBUG - questions_result value: {questions_result}")
            if questions_result:
                logger.info(f"FINALIZE DEBUG - questions_result keys: {list(questions_result.keys())}")
                if 'questions' in questions_result:
                    logger.info(f"FINALIZE DEBUG - questions count: {len(questions_result.get('questions', []))}")
            await self.finalize_job(job_id, combined_content, combined_title, summary, questions_result)

            logger.info(f"Step 8: Marking job {job_id} as completed")
            await self.mark_job_completed(job_id)
            step_time = time.time() - step_start
            print(f"[TIMER] Job Finalization: {step_time:.3f}s")

            total_time = time.time() - workflow_start
            print(f"[TIMER] === TOTAL WORKFLOW TIME: {total_time:.3f}s ===")

            logger.info(f"=== CONTENT WORKFLOW COMPLETED SUCCESSFULLY ===")
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
        logger.info(
            "Parsing input sources",
            job_id=job.id,
            source_count=len(input_sources),
            sources=input_sources
        )
        parse_tasks = self.create_parse_tasks(input_sources, job.user_id)
        results = await asyncio.gather(*parse_tasks, return_exceptions=True)

        combined_content, combined_title, source_metadata = self.combine_parsed_results(results)
        logger.info(
            "Parse results combined",
            job_id=job.id,
            combined_content_length=len(combined_content),
            combined_title=combined_title,
            metadata_count=len(source_metadata)
        )
        return combined_content, combined_title, source_metadata

    def create_parse_tasks(self, input_sources, user_id):
        parse_tasks = []
        for source in input_sources:
            content_type = source.get("content_type")
            source_id = source.get("id")

            if content_type in ["pdf", "docx"]:
                parse_tasks.append(self._parse_file(content_type, source_id, user_id))
            else:
                parse_tasks.append(self._parse_url(content_type, source_id, user_id))

        return parse_tasks

    def combine_parsed_results(self, results):
        all_content = []
        all_titles = []
        source_metadata = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Failed to parse content source {i}: {str(result)}")
                continue

            if result and result.success:
                source_type = result.metadata.get('source_type', 'unknown')

                if source_type == 'collection':
                    content_with_source = f"=== COLLECTION: {result.title} ===\n{result.content}"
                else:
                    content_with_source = f"=== SOURCE: {result.title or f'Document {i+1}'} ===\n{result.content}"

                all_content.append(content_with_source)
                if result.title:
                    all_titles.append(result.title)

                source_metadata.append({
                    'index': i,
                    'type': source_type,
                    'title': result.title,
                    'metadata': result.metadata
                })
                logger.info(
                    "Content source parsed",
                    index=i,
                    source_type=source_type,
                    title=result.title,
                    content_length=len(result.content),
                    metadata=result.metadata
                )
            else:
                logger.error(f"Content source {i} failed or returned no content. Result: {result}")
                if result and hasattr(result, 'error'):
                    logger.error(f"Error details: {result.error}")

        if not all_content:
            raise ValueError("No content could be extracted from provided sources")

        combined_content = "\n\n".join(all_content)
        combined_title = " & ".join(all_titles) if all_titles else "Processed Content"

        return combined_content, combined_title, source_metadata

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
                context_query,
                job.user_id
            )

            if rag_context:
                job.rag_context_used = True
                await self.update_job_in_db(job)
                logger.info("RAG context retrieved", job_id=job.id, context_length=len(rag_context))

            return rag_context

        except Exception as e:
            logger.warning("Failed to retrieve RAG context", job_id=job.id, error=str(e))
            return ""

    async def run_question_generation(self, job_id, job, combined_content, combined_title, rag_context):
        logger.info(f"=== CONTENT WORKFLOW - QUESTION GENERATION START ===")
        logger.info(f"Job ID: {job_id}")
        logger.info(f"Combined content length: {len(combined_content)}")
        logger.info(f"Title: {combined_title}")
        logger.info(f"RAG context length: {len(rag_context) if rag_context else 0}")

        await self.update_job_progress(job_id, 30.0, "Generating questions...")

        question_data = {
            "transcript": combined_content,
            "title": combined_title,
            "rag_context": rag_context,
            "question_types": job.input_config_dict.get("question_types", ["multiple_choice", "true_false"]),
            "difficulty_level": job.input_config_dict.get("difficulty_level", "intermediate"),
            "num_questions": job.input_config_dict.get("num_questions", 10)
        }

        logger.info(f"Question data keys: {list(question_data.keys())}")
        logger.info(
            "Question generation payload prepared",
            job_id=job_id,
            transcript_length=len(combined_content),
            rag_context_length=len(rag_context) if rag_context else 0,
            question_types=question_data["question_types"],
            difficulty=question_data["difficulty_level"],
            num_questions_requested=question_data["num_questions"]
        )
        logger.info(f"Calling question_generator.run with job_id={job_id}")

        try:
            result = await self.question_generator.run(job_id, question_data)
            question_count = len(result.get("questions", [])) if result else 0
            logger.info(
                "Question generator returned",
                job_id=job_id,
                keys=list(result.keys()) if result else [],
                question_count=question_count
            )
            return result
        except Exception as e:
            logger.error(f"Question generation failed with error: {e}")
            logger.error(f"Error type: {type(e)}")
            raise

    async def generate_summary(self, job_id: int, content: str, title: str, rag_context: str) -> str:
        await self.update_job_progress(job_id, 25.0, "Generating summary...")

        try:
            summary_prompt = f"Summarize the following content in 2-3 paragraphs:\n\nTitle: {title}\nContent: {content[:5000]}"

            from ..services.llm_service import LLMService, LLMProvider
            from ..api.dependencies import get_llm_service

            llm_service = get_llm_service()
            summary = await llm_service.generate_with_fallback(
                system_prompt="You are a helpful assistant that creates clear, concise summaries.",
                user_prompt=summary_prompt,
                temperature=0.3,
                max_tokens=500,
                preferred_provider=LLMProvider.OPENAI
            )

            return summary.strip()
        except Exception as e:
            logger.warning(f"Summary generation failed: {e}")
            return f"Summary of {title}: This content covers topics related to the provided material."

    async def finalize_job(self, job_id: int, content_text: str, title: str, summary: str, questions_result: Dict[str, Any]):
        db = SessionLocal()
        try:
            job = db.query(ContentJob).filter(ContentJob.id == job_id).first()
            if job:
                job.title = title
                questions_to_save = questions_result.get("questions", []) if questions_result else []

                output_config = {
                    "content_text": content_text,
                    "summary": summary,
                    "questions": questions_to_save,
                    "metadata": {
                        "question_generation": questions_result.get("metadata", {}) if questions_result else {}
                    }
                }
                job.output_config_dict = output_config
                logger.info(
                    "Job output config updated",
                    job_id=job_id,
                    content_length=len(content_text),
                    summary_length=len(summary) if summary else 0,
                    question_count=len(output_config["questions"])
                )
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
                job.status = JobStatus.RUNNING
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
                job.status = JobStatus.SUCCESS
                job.completed_at = datetime.now()
                job.progress = 100.0
            db.commit()

            await websocket_manager.broadcast_to_job(job_id, {
                "type": "completion",
                "status": JobStatus.SUCCESS,
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
                job.status = JobStatus.FAILED
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
                "status": JobStatus.RUNNING
            }
            if message:
                websocket_data["message"] = message

            await websocket_manager.broadcast_to_job(job_id, websocket_data)

        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    async def _parse_url(self, content_type: str, url: str, user_id: str):
        parser = self.parser_factory.get_parser(content_type)
        if not parser:
            raise ValueError(f"No parser available for content type: {content_type}")
        return await parser.parse(url, user_id=user_id)

    async def _parse_file(self, content_type: str, file_id: str, user_id: str):
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

            return await parser.parse(file_path, user_id=user_id)
        finally:
            db.close()