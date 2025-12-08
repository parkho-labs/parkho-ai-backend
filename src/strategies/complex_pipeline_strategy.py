"""
Complex Pipeline Strategy

Wraps the existing multi-agent content processing workflow that includes:
 - Parallel content parsing (YouTube, Files, Web, Collections)
- RAG context retrieval
- Multi-agent question generation
- Comprehensive error handling and progress tracking
"""

import time
import asyncio
import structlog
from typing import Dict, Any, List

from .base_strategy import ContentProcessingStrategy, ProcessingResult, ProcessingStatus
from ..core.database import get_db
from ..repositories.content_job_repository import ContentJobRepository

logger = structlog.get_logger(__name__)


class ComplexPipelineStrategy(ContentProcessingStrategy):
    """
    Strategy that uses the existing complex multi-agent processing pipeline.

    This strategy provides maximum flexibility and control by:
    - Supporting all content types (YouTube, Web URLs, Collections, Files)
    - Using specialized parsers for each content type
    - Performing parallel content parsing
    - Integrating RAG context when available
    - Using subject-specific question generation agents
    - Providing detailed progress tracking
    """

    def get_strategy_name(self) -> str:
        return "Complex Multi-Agent Pipeline"

    def get_supported_content_types(self) -> List[str]:
        return ["youtube", "web_url", "collection", "files"]

    def supports_content_type(self, content_type: str) -> bool:
        return content_type in self.get_supported_content_types()

    async def process_content(self, job_id: int) -> ProcessingResult:
        """
        Process content using the existing complex pipeline workflow.

        This method delegates to the existing ContentWorkflow implementation
        but wraps it in the strategy interface.
        """
        start_time = time.time()

        try:
            logger.info("Starting complex pipeline strategy", job_id=job_id)

            # Import here to avoid circular dependencies
            from ..agents.content_workflow import ContentWorkflow

            # Create workflow instance and process content using legacy method
            # This avoids circular dependency since legacy method doesn't use strategies
            workflow = ContentWorkflow()
            await workflow.process_content_legacy(job_id)

            # Retrieve the processed results from the database
            db_session = next(get_db())
            try:
                repo = ContentJobRepository(db_session)
                job = repo.get_by_id(job_id)

                if not job:
                    return ProcessingResult(
                        status=ProcessingStatus.FAILED,
                        error="Job not found after processing",
                        strategy_used="complex_pipeline",
                        processing_time_seconds=time.time() - start_time
                    )

                # Extract results from job output
                output_config = job.output_config_dict or {}

                processing_time = time.time() - start_time
                logger.info(
                    "Complex pipeline strategy completed successfully",
                    job_id=job_id,
                    processing_time=processing_time
                )

                return ProcessingResult(
                    status=ProcessingStatus.SUCCESS,
                    content_text=output_config.get("content_text"),
                    summary=output_config.get("summary"),
                    questions=output_config.get("questions"),
                    metadata=output_config.get("metadata", {}),
                    strategy_used="complex_pipeline",
                    processing_time_seconds=processing_time
                )

            finally:
                db_session.close()

        except Exception as e:
            processing_time = time.time() - start_time
            error_message = f"Complex pipeline strategy failed: {str(e)}"

            logger.error(
                "Complex pipeline strategy failed",
                job_id=job_id,
                error=error_message,
                processing_time=processing_time,
                exc_info=True
            )

            return ProcessingResult(
                status=ProcessingStatus.FAILED,
                error=error_message,
                strategy_used="complex_pipeline",
                processing_time_seconds=processing_time
            )

    def get_expected_processing_time(self, input_config: List[Dict[str, Any]]) -> float:
        """
        Estimate processing time for complex pipeline based on content analysis.

        YouTube videos typically take longer due to download + transcription.
        Files (pdf/doc/docx) are faster to parse.
        """
        total_time = 0.0

        for source in input_config:
            content_type = source.get("content_type")

            if content_type == "youtube":
                # YouTube: download + transcription + processing
                total_time += 300.0  # 5 minutes average per video
            elif content_type in ["files", "pdf", "docx"]:
                # Document parsing is relatively fast
                total_time += 30.0  # 30 seconds per document
            elif content_type == "web_url":
                # Web scraping + processing
                total_time += 60.0  # 1 minute per web page
            else:
                # Default estimate for unknown content types
                total_time += 120.0  # 2 minutes

        # Add base processing time for question generation
        total_time += 60.0  # 1 minute for question generation

        # Add time for RAG context retrieval if applicable
        job_config = self.config
        if job_config.get("collection_name"):
            total_time += 30.0  # 30 seconds for RAG retrieval

        return total_time

    def get_priority_score(self, input_config: List[Dict[str, Any]]) -> int:
        """
        Calculate priority score for complex pipeline strategy.

        Higher scores for:
        - Mixed content types (complex pipeline excels here)
        - Large number of content sources
        - When detailed control is needed
        """
        if not self.can_process_job(input_config):
            return 0

        content_types = [source.get("content_type") for source in input_config]
        unique_types = set(content_types)
        num_sources = len(input_config)

        # Base score for being able to process the content
        score = 60

        # Higher score for mixed content types (complex pipeline's strength)
        if len(unique_types) > 1:
            score += 20

        # Higher score for multiple sources
        if num_sources > 1:
            score += 10

        # Higher score for non-YouTube content (where Gemini isn't as strong)
        non_youtube_types = unique_types - {"youtube"}
        if non_youtube_types:
            score += 15

        # Bonus for RAG integration capability
        if self.config.get("collection_name"):
            score += 10

        return min(score, 100)  # Cap at 100

    def can_handle_fallback(self, failed_strategy: str) -> bool:
        """Check if this strategy can serve as fallback for another strategy"""
        # Complex pipeline can handle fallback from any strategy
        # since it supports all content types
        return True

    def get_strategy_metadata(self) -> Dict[str, Any]:
        """Get metadata about this strategy's capabilities"""
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