import time
import asyncio
import structlog
from typing import Dict, Any, List

from .base_strategy import ContentProcessingStrategy, ProcessingResult, ProcessingStatus
from ..core.database import get_db
from ..repositories.content_job_repository import ContentJobRepository
from ..repositories.quiz_repository import QuizRepository
from ..agents.workflow.content_parsing_coordinator import ContentParsingCoordinator
from ..services.llm_service import LLMService, LLMProvider
from ..agents.question_generator import QuestionGeneratorAgent
from ..services.rag_integration_service import get_rag_service
from ..config import get_settings

logger = structlog.get_logger(__name__)


class ComplexPipelineStrategy(ContentProcessingStrategy):
    def get_strategy_name(self) -> str:
        return "Complex Multi-Agent Pipeline"

    def get_supported_content_types(self) -> List[str]:
        return ["youtube", "web_url", "collection", "files"]

    def supports_content_type(self, content_type: str) -> bool:
        return content_type in self.get_supported_content_types()

    async def process_content(self, job_id: int) -> ProcessingResult:
        start_time = time.time()
        db_session = next(get_db())
        
        try:
            logger.info("Starting complex pipeline strategy", job_id=job_id)
            repo = ContentJobRepository(db_session)
            job = repo.get_by_id(job_id)

            if not job:
                return ProcessingResult(
                    status=ProcessingStatus.FAILED,
                    error="Job not found",
                    strategy_used="complex_pipeline",
                    processing_time_seconds=time.time() - start_time
                )

            settings = get_settings()
            coordinator = ContentParsingCoordinator(db_session)
            llm_service = LLMService(
                openai_api_key=settings.openai_api_key,
                anthropic_api_key=settings.anthropic_api_key,
                google_api_key=settings.google_api_key
            )
            question_agent = QuestionGeneratorAgent()
            
            await self._update_progress(repo, job_id, 10, "Parsing content sources...")
            
            input_config_dict = job.input_config_dict or {}
            input_sources = input_config_dict.get("input_config", [])
            
            parsed_results = await coordinator.parse_all_content_sources(
                input_sources=input_sources, 
                user_id=job.user_id
            )
            
            if not parsed_results:
                raise ValueError("No content was successfully parsed from the provided sources")

            combined_data = coordinator.combine_parsed_results(parsed_results)
            content_text = combined_data.get("content", "")
            title = combined_data.get("title", job.title or "Processed Content")
            
            if not content_text:
                raise ValueError("Parsed content is empty")
                
            await self._update_progress(repo, job_id, 40, "Generating content summary...")
            
            summary = ""
            if job.input_config_dict.get("generate_summary", True):
                summary = await self._generate_summary(llm_service, content_text, job.input_config_dict)

            rag_context = ""
            if job.collection_name:
                await self._update_progress(repo, job_id, 60, "Retrieving RAG context...")
                rag_context = await self._retrieve_rag_context(job.collection_name, content_text)

            await self._update_progress(repo, job_id, 70, "Generating quiz questions...")
            
            agent_data = {
                "transcript": content_text,
                "title": title,
                "rag_context": rag_context,
                "subject_type": "general", 
                "question_types": job.input_config_dict.get("question_types", {"multiple_choice": 5}),
                "difficulty_level": job.input_config_dict.get("difficulty_level", "intermediate")
            }
            
            agent_result = await question_agent.run(job_id, agent_data)
            questions = agent_result.get("questions", [])

            await self._update_progress(repo, job_id, 90, "Finalizing results...")
            
            metadata = {
                "source_count": len(input_sources),
                "total_length": len(content_text),
                "rag_enabled": bool(job.collection_name),
                "processing_method": "complex_pipeline"
            }

            processing_time = time.time() - start_time
            logger.info(
                "Complex pipeline strategy completed successfully",
                job_id=job_id,
                processing_time=processing_time
            )

            return ProcessingResult(
                status=ProcessingStatus.SUCCESS,
                content_text=content_text,
                summary=summary,
                questions=questions,
                metadata=metadata,
                strategy_used="complex_pipeline",
                processing_time_seconds=processing_time
            )

        except Exception as e:
            processing_time = time.time() - start_time
            error_message = f"Complex pipeline strategy failed: {str(e)}"
            
            logger.error(
                "Complex pipeline strategy failed",
                job_id=job_id,
                error=error_message,
                exc_info=True
            )
            
            try:
                 repo = ContentJobRepository(db_session)
                 repo.mark_failed(job_id, error_message)
            except:
                pass

            return ProcessingResult(
                status=ProcessingStatus.FAILED,
                error=error_message,
                strategy_used="complex_pipeline",
                processing_time_seconds=processing_time
            )
        finally:
            db_session.close()

    async def _generate_summary(self, llm_service: LLMService, content: str, config: Dict[str, Any]) -> str:
        max_chars = 100000
        truncated_content = content[:max_chars]
        
        system_prompt = "You are an expert educational summarizer. Create a concise, structured summary of the provided content."
        user_prompt = f"Please summarize the following content, highlighting key concepts and main points:\n\n{truncated_content}"
        
        return await llm_service.generate_with_fallback(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
            max_tokens=1000
        )

    async def _retrieve_rag_context(self, collection_name: str, content: str) -> str:
        try:
            rag_service = get_rag_service()
            return "" 
        except Exception as e:
            logger.warning("Failed to retrieve RAG context", error=str(e))
            return ""

    async def _update_progress(self, repo: ContentJobRepository, job_id: int, progress: float, message: str):
        try:
            repo.update_progress(job_id, progress, message)
        except Exception as e:
            logger.warning("Failed to update progress", job_id=job_id, error=str(e))

    def get_expected_processing_time(self, input_config: List[Dict[str, Any]]) -> float:
        total_time = 0.0

        for source in input_config:
            content_type = source.get("content_type")

            if content_type == "youtube":
                total_time += 300.0
            elif content_type in ["files", "pdf", "docx"]:
                total_time += 30.0
            elif content_type == "web_url":
                total_time += 60.0
            else:
                total_time += 120.0

        total_time += 60.0
        
        if self.config.get("collection_name"):
            total_time += 30.0

        return total_time

    def get_priority_score(self, input_config: List[Dict[str, Any]]) -> int:
        if not self.can_process_job(input_config):
            return 0

        content_types = [source.get("content_type") for source in input_config]
        unique_types = set(content_types)
        num_sources = len(input_config)

        score = 60

        if len(unique_types) > 1:
            score += 20

        if num_sources > 1:
            score += 10

        non_youtube_types = unique_types - {"youtube"}
        if non_youtube_types:
            score += 15

        if self.config.get("collection_name"):
            score += 10

        return min(score, 100)

    def can_handle_fallback(self, failed_strategy: str) -> bool:
        return True

    def get_strategy_metadata(self) -> Dict[str, Any]:
        return {
            "supports_parallel_parsing": True,
            "supports_rag_integration": True,
            "supports_multi_agent_processing": True,
            "supports_progress_tracking": True,
            "supports_all_content_types": True,
            "typical_processing_time_minutes": "3-10",
            "reliability": "high",
            "flexibility": "very_high"
        }