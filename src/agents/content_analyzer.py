import json
import structlog
from typing import Dict, Any, List

import openai

from .base import ContentTutorAgent
from .prompts import ContentAnalysisPrompts
from ..config import get_settings
from ..models.content_job import ContentJob
from ..core.database import SessionLocal
from ..services.llm_service import LLMService

settings = get_settings()
logger = structlog.get_logger(__name__)


class ContentAnalyzerAgent(ContentTutorAgent):
    def __init__(self):
        super().__init__("content_analyzer")
        self.chunk_size = 2000
        self.chunk_overlap = 200

        # Initialize multi-provider LLM service
        self.llm_service = LLMService(
            openai_api_key=settings.openai_api_key,
            anthropic_api_key=settings.anthropic_api_key,
            google_api_key=settings.google_api_key
        )


    def get_model_client(self):
        return openai.OpenAI(api_key=settings.openai_api_key)


    async def run(self, job_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        transcript = data.get("transcript")
        video_metadata = data.get("video_metadata", {})

        if not transcript:
            raise ValueError("No transcript available for content analysis")

        try:
            await self.update_job_progress(job_id, 60.0, "Analyzing content structure")
            chunks = self.split_transcript(transcript)
            content_analysis = await self.analyze_content_structure(chunks, video_metadata)
            key_concepts = await self.extract_key_concepts(transcript, video_metadata)

            generate_summary = data.get("generate_summary", True)
            summary = ""
            if generate_summary:
                await self.update_job_progress(job_id, 65.0, "Generating summary")
                summary = await self.generate_summary(transcript, content_analysis)

            await self.update_job_progress(job_id, 70.0, "Content analysis completed")

            analysis_data = {
                "content_analysis": content_analysis,
                "key_concepts": key_concepts,
                "summary": summary,
                "chunks": chunks
            }

            await self.update_summary(job_id, summary)
            data.update(analysis_data)
            return data

        except Exception as e:
            await self.mark_job_failed(job_id, f"Content analysis failed: {str(e)}")
            raise

    def split_transcript(self, transcript: str) -> List[str]:
        text_length = len(transcript)
        boundaries = self._calculate_chunk_boundaries(transcript, text_length)

        chunks = []
        for start, end in boundaries:
            chunks.append(transcript[start:end])

        return chunks

    def _calculate_chunk_boundaries(self, transcript: str, text_length: int) -> List[tuple[int, int]]:
        boundaries = []
        start = 0

        while start < text_length:
            end = min(start + self.chunk_size, text_length)

            if end < text_length:
                end = self._find_word_boundary(transcript, start, end)

            boundaries.append((start, end))
            start = end - self.chunk_overlap

        return boundaries

    def _find_word_boundary(self, text: str, start: int, proposed_end: int) -> int:
        chunk = text[start:proposed_end]
        last_space = chunk.rfind(' ')
        return start + last_space if last_space > 0 else proposed_end

    async def analyze_content_structure(self, chunks: List[str], video_metadata: Dict[str, Any]) -> Dict[str, Any]:
        full_text = " ".join(chunks[:5])
        system_prompt = ContentAnalysisPrompts.get_analysis_prompt()

        user_content = f"Video Title: {video_metadata.get('title', 'Unknown')}\n\nTranscript: {full_text[:3000]}"

        try:
            response = await self.llm_service.generate_with_fallback(
                system_prompt=system_prompt,
                user_prompt=user_content,
                temperature=0.1
            )

            result = await self.llm_service.parse_json_response(response)
            return result if result else self._get_fallback_analysis()

        except Exception as e:
            logger.error(f"Content structure analysis failed: {e}")
            return self._get_fallback_analysis()

    def _get_fallback_analysis(self) -> Dict[str, Any]:
        return {
            "main_topics": ["Content analysis failed"],
            "content_type": "unknown",
            "difficulty_level": "intermediate",
            "structure": "Unable to analyze structure",
            "learning_objectives": ["Analysis failed"]
        }

    async def extract_key_concepts(self, transcript: str, video_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        system_prompt = ContentAnalysisPrompts.get_key_concepts_prompt()

        user_content = f"Video Title: {video_metadata.get('title', 'Unknown')}\n\nTranscript: {transcript[:4000]}"

        try:
            response = await self.llm_service.generate_with_fallback(
                system_prompt=system_prompt,
                user_prompt=user_content,
                temperature=0.1
            )

            result = await self.llm_service.parse_json_response(response)
            if isinstance(result, list):
                return result
            elif isinstance(result, dict) and 'concepts' in result:
                concepts = result.get('concepts', [])
                return concepts if isinstance(concepts, list) else []
            else:
                return []

        except Exception as e:
            logger.error(f"Key concepts extraction failed: {e}")
            return []

    async def generate_summary(self, transcript: str, content_analysis: Dict[str, Any]) -> str:
        system_prompt = ContentAnalysisPrompts.get_summary_prompt()

        main_topics = content_analysis.get('main_topics', [])
        topics_text = ", ".join(main_topics) if main_topics else "various topics"

        user_content = f"Topics covered: {topics_text}\n\nContent: {transcript[:4000]}"

        try:
            response = await self.llm_service.generate_with_fallback(
                system_prompt=system_prompt,
                user_prompt=user_content,
                temperature=0.1
            )
            return response

        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return "Summary generation failed - all LLM providers unavailable"


    async def update_summary(self, job_id: int, summary: str):
        if not summary:
            return

        db = SessionLocal()
        try:
            job = self._get_job(db, job_id)
            if job:
                job.update_output_config(summary=summary)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
