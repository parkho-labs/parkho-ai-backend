import json
from typing import Dict, Any, List

import openai

from .base import ContentTutorAgent
from ..config import get_settings
from ..models.content_job import ContentJob
from ..core.database import SessionLocal

settings = get_settings()

# Testing for pr raise


class ContentAnalyzerAgent(ContentTutorAgent):
    def __init__(self):
        super().__init__("content_analyzer")
        self.chunk_size = 2000
        self.chunk_overlap = 200

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
        chunks = []
        start = 0
        text_length = len(transcript)

        while start < text_length:
            end = start + self.chunk_size
            if end < text_length:
                chunk = transcript[start:end]
                last_space = chunk.rfind(' ')
                if last_space > 0:
                    end = start + last_space

            chunk = transcript[start:end]
            chunks.append(chunk)
            start = end - self.chunk_overlap

        return chunks

    async def analyze_content_structure(self, chunks: List[str], video_metadata: Dict[str, Any]) -> Dict[str, Any]:
        full_text = " ".join(chunks[:5])

        system_prompt = """Analyze the following video transcript and return a JSON object with:
- main_topics: List of 3-5 main topics covered
- content_type: Type of content (lecture, tutorial, discussion, etc.)
- difficulty_level: beginner, intermediate, or advanced
- structure: brief description of how content is organized
- learning_objectives: 3-5 key learning objectives"""

        user_content = f"Video Title: {video_metadata.get('title', 'Unknown')}\n\nTranscript: {full_text[:3000]}"

        try:
            client = self.get_model_client()

            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                temperature=0.1,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ]
            )
            content = response.choices[0].message.content

            return json.loads(content)

        except Exception:
            return {
                "main_topics": ["Content analysis failed"],
                "content_type": "unknown",
                "difficulty_level": "intermediate",
                "structure": "Unable to analyze structure",
                "learning_objectives": ["Analysis failed"]
            }

    async def extract_key_concepts(self, transcript: str, video_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        system_prompt = """Extract key concepts from the transcript and return a JSON array where each concept has:
- concept: the concept name
- definition: brief definition or explanation
- importance: why this concept is important (1 sentence)
- context: where in the content this appears

Extract 5-10 key concepts maximum."""

        user_content = f"Video Title: {video_metadata.get('title', 'Unknown')}\n\nTranscript: {transcript[:4000]}"

        try:
            client = self.get_model_client()

            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                temperature=0.1,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ]
            )
            content = response.choices[0].message.content

            concepts = json.loads(content)
            return concepts if isinstance(concepts, list) else []

        except Exception:
            return []

    async def generate_summary(self, transcript: str, content_analysis: Dict[str, Any]) -> str:
        system_prompt = """Create a comprehensive summary of the video content with:
        1. Executive summary (2-3 sentences)
        2. Key points covered (bullet points)
        3. Main takeaways

        Return as clean text, not JSON."""

        main_topics = content_analysis.get('main_topics', [])
        topics_text = ", ".join(main_topics) if main_topics else "various topics"

        user_content = f"Topics covered: {topics_text}\n\nContent: {transcript[:4000]}"

        try:
            client = self.get_model_client()

            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                temperature=0.1,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ]
            )
            return response.choices[0].message.content

        except Exception:
            return "Summary generation failed"


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

# Test Concluded