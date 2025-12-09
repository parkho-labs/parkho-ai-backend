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
from ..repositories.quiz_repository import QuizRepository
from ..api.v1.schemas import JobStatus

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

                # Save results to database - REMOVED: let orchestrator handle it
                # await self._save_results_to_job(job_id, combined_result, repo)

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
        import tempfile
        import shutil

        # Get LLM service with Gemini configuration
        settings = self.config.get("settings")
        llm_service = LLMService(
            openai_api_key=settings.openai_api_key,
            anthropic_api_key=settings.anthropic_api_key,
            google_api_key=settings.google_api_key,
            openai_model_name=settings.openai_model_name,
            anthropic_model_name=settings.anthropic_model_name,
            google_model_name=settings.gemini_video_model_name
        )

        # Generate comprehensive prompt for video analysis
        prompt = self._build_gemini_prompt(job_config)

        logger.info("Starting Gemini video processing flow", url=url)

        video_path = None
        uploaded_file = None
        
        try:
            # 1. Download video locally
            logger.info("Downloading video for Gemini analysis...", url=url)
            # Use job_id for uniqueness if available in context, otherwise random temp
            video_path = await self._download_video(url)
            
            # 2. Upload to Gemini
            logger.info("Uploading video to Gemini...", file_path=str(video_path))
            uploaded_file = llm_service.upload_file(str(video_path), mime_type="video/mp4")
            
            # 3. Wait for processing
            logger.info("Waiting for Gemini to process video...", file_uri=uploaded_file.uri)
            await llm_service.wait_for_files_active([uploaded_file])

            # 4. Generate content
            logger.info("Calling Gemini video analysis API")
            response = await llm_service.generate_video_content(
                video_file=uploaded_file,
                prompt=prompt,
                model_name=settings.gemini_video_model_name
            )

            # Parse Gemini response into structured format
            return self._parse_gemini_response(response, url)

        finally:
            # Cleanup: Delete local file
            if video_path and video_path.exists():
                try:
                    video_path.unlink()
                    # Also try to remove parent temp dir if empty
                    if not any(video_path.parent.iterdir()):
                        video_path.parent.rmdir()
                except Exception as e:
                    logger.warning("Failed to cleanup temp video file", path=str(video_path), error=str(e))

            # Cleanup: Delete from Gemini (optional but good practice if not caching)
            # if uploaded_file:
            #     try:
            #         genai.delete_file(uploaded_file.name)
            #     except:
            #         pass

    async def _download_video(self, url: str) -> Path:
        """
        Download YouTube video to a temporary file using yt-dlp.
        Downloads in 360p/480p to accept speed vs quality trade-off for analysis.
        """
        import yt_dlp
        from pathlib import Path
        import tempfile
        
        temp_dir = Path(tempfile.mkdtemp())
        output_path = temp_dir / "video.mp4"

        def _download_sync():
            ydl_opts = {
                'format': 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]',  # Limit resolution for speed
                'outtmpl': str(output_path.with_suffix('')),
                'merge_output_format': 'mp4',
                'quiet': True,
                'no_warnings': True,
                # 'cookiesfrombrowser': ('chrome',), # Optional: might be needed for some videos
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _download_sync)

            # Handling yt-dlp output naming quirks (sometimes adds extension even if specified)
            # Check for the expected file, if not found look for others in temp dir
            target_file = output_path
            
            # yt-dlp might not append .mp4 if it's already in the template, or might append it if it's not.
            # safe check:
            if not target_file.exists():
                potential_files = list(temp_dir.glob("*.mp4"))
                if potential_files:
                    target_file = potential_files[0]
                else:
                     raise ValueError("Video download failed - file not found")

            file_size = target_file.stat().st_size
            logger.info("Video downloaded successfully", size_mb=round(file_size / (1024 * 1024), 2), path=str(target_file))
            
            # Rename to ensure it matches what we expect if we found a different file
            if target_file != output_path:
                 target_file.rename(output_path)
                 target_file = output_path

            return target_file

        except Exception as e:
            if temp_dir.exists():
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            raise ValueError(f"Video download failed: {str(e)}")

    def _build_gemini_prompt(self, job_config: Dict[str, Any]) -> str:
        """
        Build comprehensive prompt for Gemini video analysis.
        """
        num_questions = job_config.get("num_questions", 10)
        question_types = job_config.get("question_types", {"multiple_choice": 10})
        difficulty_level = job_config.get("difficulty_level", "intermediate")
        generate_summary = job_config.get("generate_summary", True)

        # Construct question requirements string
        if isinstance(question_types, dict):
            # Format: "X multiple_choice, Y true_false"
            type_reqs = []
            for q_type, count in question_types.items():
                type_reqs.append(f"{count} {q_type}")
            question_requirements = ", ".join(type_reqs)
        else:
            # Fallback if list
            question_requirements = ", ".join(question_types)

        prompt = f"""
Analyze this video and provide a comprehensive educational analysis.

IMPORTANT: Return ONLY valid JSON. 
- You MUST properly escape all double quotes within strings (e.g., "The \\"quoted\\" word").
- Do not wrap in markdown code blocks.
- Do not add any text before or after the JSON.

Return EXACTLY this JSON structure:

{{
    "title": "Video title",
    "transcript": "Full transcript of the video content (ensure all quotes are escaped)",
    "summary": "2-3 paragraph summary (ensure all quotes are escaped)",
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
        "duration": "Duration",
        "subject": "detected subject",
        "difficulty_assessed": "difficulty",
        "key_topics": ["topic1", "topic2"]
    }}
}}

CRITICAL REQUIREMENTS:
- "options" MUST be an object with keys A, B, C, D.
- Generate exactly {num_questions} questions.
- Question types distribution: {question_requirements}
- Difficulty level: {difficulty_level}
- {'Include a comprehensive summary' if generate_summary else 'Summary not required'}
- ESCAPE ALL DOUBLE QUOTES inside strings with backslash (\\").
- Return ONLY the raw JSON string.

Focus on creating high-quality educational content.
"""

        return prompt.strip()

    def _parse_gemini_response(self, response: str, url: str) -> Dict[str, Any]:
        """
        Parse Gemini API response into structured format.
        """
        import json
        import re

        logger.info(
            "Parsing Gemini response",
            response_length=len(response),
            starts_with_json=response.strip().startswith('{'),
            response_preview=response[:200]
        )

        # Strip markdown code blocks if present (```json ... ```)
        cleaned_response = response.strip()
        if cleaned_response.startswith('```'):
            # Remove markdown code block wrapper
            cleaned_response = re.sub(r'^```(?:json)?\n', '', cleaned_response)
            cleaned_response = re.sub(r'\n```$', '', cleaned_response)
            logger.info("Stripped markdown code blocks from response")

        try:
            # Try to parse as JSON first
            if cleaned_response.strip().startswith('{'):
                data = json.loads(cleaned_response)
                logger.info(
                    "Successfully parsed JSON response",
                    has_questions=bool(data.get("questions")),
                    question_count=len(data.get("questions", [])),
                    json_keys=list(data.keys())
                )
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
                logger.warning(
                    "Response doesn't start with JSON, using text extraction",
                    response_start=cleaned_response[:100]
                )
                return self._extract_from_text_response(cleaned_response, url)

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse Gemini response as JSON", error=str(e))
            
            # Attempt to rescue questions even if full JSON is invalid
            try:
                # Robust extraction using JSONDecoder to handle nested brackets correctly
                # Find "questions" key and the opening bracket with flexible whitespace
                match = re.search(r'"questions"\s*:\s*\[', cleaned_response)
                
                if match:
                    # Start decoding from the opening bracket '['
                    # match.end() gives index after '[', so match.end()-1 is the '['
                    start_pos = match.end() - 1
                    questions, _ = json.JSONDecoder().raw_decode(cleaned_response[start_pos:])
                    
                    logger.info("Successfully extracted questions using raw_decode", count=len(questions))
                    
                    # Return partial structured result
                    return {
                        "title": "YouTube Video Analysis (Partial Parse)",
                        "transcript": cleaned_response, # Fallback to full text
                        "summary": "Summary unavailable due to parsing error", 
                        "questions": questions,
                        "metadata": {
                            "source_url": url,
                            "processing_method": "direct_gemini",
                            "parsing_note": "Partial parse: questions recovered from invalid JSON"
                        }
                    }
            except Exception as rescue_error:
                logger.warning("Failed to rescue questions from invalid JSON", error=str(rescue_error))

            logger.warning("Falling back to text extraction")
            return self._extract_from_text_response(cleaned_response, url)

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



    async def _update_progress(
        self,
        job_id: int,
        progress: int,
        message: str,
        status: str = JobStatus.RUNNING
    ):
        """Update job progress (polling only, no websocket broadcast)."""
        db_session = next(get_db())
        try:
            repo = ContentJobRepository(db_session)
            repo.update_progress(job_id, progress, message)

            if status == "failed":
                repo.mark_failed(job_id, message)

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