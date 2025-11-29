"""
Direct Gemini Strategy

Uses Google Gemini's video understanding API to process YouTube content directly.
Single API call provides transcript, summary, and questions all at once.
"""

import time
import asyncio
import structlog
from typing import Dict, Any, List

from .base_strategy import ContentProcessingStrategy, ProcessingResult, ProcessingStatus
from ..core.database import get_db
from ..repositories.content_job_repository import ContentJobRepository
from ..api.v1.schemas import JobStatus
from ..core.websocket_manager import websocket_manager

logger = structlog.get_logger(__name__)


class DirectGeminiStrategy(ContentProcessingStrategy):
    """
    Strategy that uses Google Gemini's video understanding API directly.

    This strategy provides:
    - Fast processing (single API call)
    - High reliability (Google's infrastructure)
    - Direct video understanding (no download/transcription needed)
    - Cost efficiency for simple YouTube processing

    Limitations:
    - Only supports YouTube URLs
    - Less customization than complex pipeline
    - Dependent on Google's API availability
    """

    def get_strategy_name(self) -> str:
        return "Direct Gemini Video API"

    def get_supported_content_types(self) -> List[str]:
        return ["youtube"]

    def supports_content_type(self, content_type: str) -> bool:
        return content_type == "youtube"

    async def process_content(self, job_id: int) -> ProcessingResult:
        """
        Process YouTube content using direct Gemini video API.
        """
        start_time = time.time()

        try:
            logger.info("Starting direct Gemini strategy", job_id=job_id)

            # Get job configuration
            db_session = next(get_db())
            try:
                repo = ContentJobRepository(db_session)
                job = repo.get(job_id)

                if not job:
                    return ProcessingResult(
                        status=ProcessingStatus.FAILED,
                        error="Job not found",
                        strategy_used="direct_gemini",
                        processing_time_seconds=time.time() - start_time
                    )

                # Mark job as started
                await self._update_progress(job_id, 0, "Starting Gemini video analysis...")

                input_config = job.input_config_dict.get("input_config", [])
                job_config = job.input_config_dict

                # Validate that all content sources are YouTube URLs
                youtube_urls = []
                for source in input_config:
                    if source.get("content_type") != "youtube":
                        return ProcessingResult(
                            status=ProcessingStatus.FAILED,
                            error=f"Direct Gemini strategy only supports YouTube URLs, got: {source.get('content_type')}",
                            strategy_used="direct_gemini",
                            processing_time_seconds=time.time() - start_time
                        )
                    youtube_urls.append(source.get("id"))

                await self._update_progress(job_id, 25, "Analyzing video content with Gemini...")

                # Process all YouTube URLs with Gemini
                processed_results = []
                for i, url in enumerate(youtube_urls):
                    progress = 25 + (50 * i // len(youtube_urls))
                    await self._update_progress(job_id, progress, f"Processing video {i+1} of {len(youtube_urls)}...")

                    result = await self._process_youtube_url_with_gemini(url, job_config)
                    processed_results.append(result)

                await self._update_progress(job_id, 75, "Generating final output...")

                # Combine results from multiple videos
                combined_result = self._combine_results(processed_results, youtube_urls)

                # Save results to database
                await self._save_results_to_job(job_id, combined_result, repo)

                await self._update_progress(job_id, 100, "Gemini analysis completed successfully")

                processing_time = time.time() - start_time
                logger.info(
                    "Direct Gemini strategy completed successfully",
                    job_id=job_id,
                    processing_time=processing_time,
                    video_count=len(youtube_urls)
                )

                return ProcessingResult(
                    status=ProcessingStatus.SUCCESS,
                    content_text=combined_result["content_text"],
                    summary=combined_result["summary"],
                    questions=combined_result["questions"],
                    metadata=combined_result["metadata"],
                    strategy_used="direct_gemini",
                    processing_time_seconds=processing_time
                )

            finally:
                db_session.close()

        except Exception as e:
            processing_time = time.time() - start_time
            error_message = f"Direct Gemini strategy failed: {str(e)}"

            logger.error(
                "Direct Gemini strategy failed",
                job_id=job_id,
                error=error_message,
                processing_time=processing_time,
                exc_info=True
            )

            await self._update_progress(job_id, 100, f"Failed: {error_message}", status="failed")

            return ProcessingResult(
                status=ProcessingStatus.FAILED,
                error=error_message,
                strategy_used="direct_gemini",
                processing_time_seconds=processing_time
            )

    async def _process_youtube_url_with_gemini(self, url: str, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single YouTube URL using Gemini video API.
        """
        # Import here to avoid circular dependencies
        from ..services.llm_service import LLMService

        # Get LLM service with Gemini configuration
        settings = self.config.get("settings")
        llm_service = LLMService(
            openai_api_key=settings.openai_api_key,
            anthropic_api_key=settings.anthropic_api_key,
            google_api_key=settings.google_api_key,
            google_model_name=settings.gemini_video_model_name
        )

        # Generate comprehensive prompt for video analysis
        prompt = self._build_gemini_prompt(job_config)

        logger.info("Calling Gemini video API", url=url)

        # Call Gemini with video URL
        response = await llm_service.generate_video_content(
            video_url=url,
            prompt=prompt,
            model_name=settings.gemini_video_model_name
        )

        # Parse Gemini response into structured format
        return self._parse_gemini_response(response, url)

    def _build_gemini_prompt(self, job_config: Dict[str, Any]) -> str:
        """
        Build comprehensive prompt for Gemini video analysis.
        """
        num_questions = job_config.get("num_questions", 10)
        question_types = job_config.get("question_types", ["multiple_choice"])
        difficulty_level = job_config.get("difficulty_level", "intermediate")
        generate_summary = job_config.get("generate_summary", True)

        prompt = f"""
Analyze this YouTube video and provide a comprehensive educational analysis.

Please provide your response in the following JSON format:

{{
    "title": "Video title",
    "transcript": "Full transcript of the video content",
    "summary": "2-3 paragraph summary of the main concepts and key points",
    "questions": [
        {{
            "question_id": "q1",
            "question": "Question text here?",
            "type": "multiple_choice",
            "answer_config": {{
                "options": {{"A": "Option A", "B": "Option B", "C": "Option C", "D": "Option D"}},
                "correct_answer": "A"
            }},
            "context": "Brief explanation of why this answer is correct",
            "max_score": 1
        }}
    ],
    "metadata": {{
        "duration": "Video duration in seconds if available",
        "subject": "Detected subject (Physics, Mathematics, Chemistry, Biology, General)",
        "difficulty_assessed": "Assessed difficulty level",
        "key_topics": ["List of key topics covered"]
    }}
}}

Requirements:
- Generate exactly {num_questions} questions
- Question types: {', '.join(question_types)}
- Difficulty level: {difficulty_level}
- {'Include a comprehensive summary' if generate_summary else 'Summary not required'}
- Ensure questions test understanding of key concepts from the video
- Provide clear explanations for correct answers
- Make questions educational and relevant to the content

Focus on creating high-quality educational content that helps learners understand and retain the key concepts presented in the video.
"""

        return prompt.strip()

    def _parse_gemini_response(self, response: str, url: str) -> Dict[str, Any]:
        """
        Parse Gemini API response into structured format.
        """
        import json

        try:
            # Try to parse as JSON first
            if response.strip().startswith('{'):
                data = json.loads(response)
                return {
                    "title": data.get("title", "YouTube Video"),
                    "transcript": data.get("transcript", ""),
                    "summary": data.get("summary", ""),
                    "questions": data.get("questions", []),
                    "metadata": {
                        **data.get("metadata", {}),
                        "source_url": url,
                        "processing_method": "direct_gemini"
                    }
                }
            else:
                # If not JSON, try to extract information from text response
                return self._extract_from_text_response(response, url)

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse Gemini response as JSON, falling back to text extraction", error=str(e))
            return self._extract_from_text_response(response, url)

    def _extract_from_text_response(self, response: str, url: str) -> Dict[str, Any]:
        """
        Extract structured information from text response when JSON parsing fails.
        """
        # Simple fallback extraction - can be enhanced with more sophisticated parsing
        lines = response.split('\\n')

        return {
            "title": "YouTube Video Analysis",
            "transcript": response,  # Use full response as transcript fallback
            "summary": response[:500] + "..." if len(response) > 500 else response,
            "questions": [],  # Empty questions if parsing fails
            "metadata": {
                "source_url": url,
                "processing_method": "direct_gemini",
                "parsing_note": "Fallback text extraction used"
            }
        }

    def _combine_results(self, results: List[Dict[str, Any]], urls: List[str]) -> Dict[str, Any]:
        """
        Combine results from multiple YouTube videos.
        """
        if not results:
            return {
                "content_text": "",
                "summary": "",
                "questions": [],
                "metadata": {}
            }

        if len(results) == 1:
            result = results[0]
            return {
                "content_text": result["transcript"],
                "summary": result["summary"],
                "questions": result["questions"],
                "metadata": result["metadata"]
            }

        # Combine multiple videos
        combined_transcript = ""
        combined_summary = ""
        all_questions = []
        combined_metadata = {"source_urls": urls, "video_count": len(results)}

        for i, result in enumerate(results):
            # Add source markers for multiple videos
            combined_transcript += f"\\n\\n=== VIDEO {i+1}: {result['title']} ===\\n\\n"
            combined_transcript += result["transcript"]

            if result["summary"]:
                combined_summary += f"**Video {i+1} Summary:**\\n{result['summary']}\\n\\n"

            # Add questions with source indication
            for question in result["questions"]:
                question["metadata"] = question.get("metadata", {})
                question["metadata"]["source_video"] = i + 1
                all_questions.append(question)

        return {
            "content_text": combined_transcript.strip(),
            "summary": combined_summary.strip(),
            "questions": all_questions,
            "metadata": combined_metadata
        }

    async def _save_results_to_job(
        self,
        job_id: int,
        results: Dict[str, Any],
        repo: ContentJobRepository
    ):
        """Save processing results to the job in database."""
        job = repo.get_by_id(job_id)
        if job:
            output_config = {
                "content_text": results["content_text"],
                "summary": results["summary"],
                "questions": results["questions"],
                "metadata": results["metadata"]
            }
            repo.update_output_config(job_id, output_config)
            repo.mark_completed(job_id)

    async def _update_progress(
        self,
        job_id: int,
        progress: int,
        message: str,
        status: str = JobStatus.RUNNING
    ):
        """Update job progress and broadcast via WebSocket."""
        db_session = next(get_db())
        try:
            repo = ContentJobRepository(db_session)
            repo.update_progress(job_id, progress, message)

            if status == "failed":
                repo.mark_failed(job_id, message)

            # Broadcast progress update
            await websocket_manager.broadcast_to_job(job_id, {
                "type": "progress_update",
                "job_id": job_id,
                "progress": progress,
                "message": message,
                "status": status
            })

        finally:
            db_session.close()

    def get_expected_processing_time(self, input_config: List[Dict[str, Any]]) -> float:
        """
        Estimate processing time for direct Gemini strategy.
        Much faster than complex pipeline due to single API call.
        """
        youtube_count = len([s for s in input_config if s.get("content_type") == "youtube"])

        # Base time per video (Gemini API is quite fast)
        time_per_video = 30.0  # 30 seconds per video

        return youtube_count * time_per_video + 15.0  # 15 seconds overhead

    def get_priority_score(self, input_config: List[Dict[str, Any]]) -> int:
        """
        Calculate priority score for direct Gemini strategy.

        Higher scores for:
        - YouTube-only content
        - Single video processing
        - When speed is preferred
        """
        if not self.can_process_job(input_config):
            return 0

        content_types = [source.get("content_type") for source in input_config]
        unique_types = set(content_types)
        num_sources = len(input_config)

        # Only process YouTube content
        if unique_types != {"youtube"}:
            return 0

        # Base score for YouTube-only content
        score = 80

        # Higher score for single video (Gemini excels here)
        if num_sources == 1:
            score += 15

        # Lower score for many videos (complex pipeline may be better for batch processing)
        if num_sources > 3:
            score -= 20

        # Check if Gemini is enabled and available
        settings = self.config.get("settings")
        if not (settings and settings.gemini_video_api_enabled and settings.google_api_key):
            return 0

        return min(score, 100)  # Cap at 100

    def get_strategy_metadata(self) -> Dict[str, Any]:
        """Get metadata about this strategy's capabilities"""
        return {
            "supports_parallel_parsing": False,
            "supports_rag_integration": False,
            "supports_multi_agent_processing": False,
            "supports_progress_tracking": True,
            "supports_youtube_only": True,
            "typical_processing_time_minutes": "0.5-2",
            "reliability": "high",
            "flexibility": "low",
            "speed": "very_high"
        }