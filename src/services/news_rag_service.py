"""
NewsRagService - All RAG operations for news articles
Handles indexing, querying, and summary generation using the link-content API
"""

import logging
import aiohttp
from typing import List, Dict, Optional, Any
from datetime import datetime
import asyncio

from ..news.models.news_article import NewsArticle
from ..config import get_settings

logger = logging.getLogger(__name__)

class NewsRagService:
    """Service for all news-related RAG operations"""

    def __init__(self):
        self.settings = get_settings()
        self.base_url = "http://localhost:8000/api/v1"  # RAG engine base URL
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    async def batch_index_articles(self, articles: List[NewsArticle]) -> Dict[str, Any]:
        """
        Batch index articles using link-content API

        Args:
            articles: List of NewsArticle objects to index

        Returns:
            Dictionary with indexing results
        """
        if not articles:
            return {"total": 0, "successful": 0, "failed": 0, "results": []}

        try:
            # Prepare batch payload
            items = []
            for article in articles:
                item = self._prepare_link_content_item(article)
                items.append(item)

            payload = {"items": items}

            # Call link-content API
            headers = {
                "Content-Type": "application/json",
                "x-user-id": "system"  # Use system user for shared news content
            }

            async with self.session.post(
                f"{self.base_url}/link-content",
                json=payload,
                headers=headers
            ) as response:
                if response.status == 200:
                    result = await response.json()

                    # Process results
                    successful = sum(1 for r in result.get("results", [])
                                   if r.get("status") == "INDEXING_SUCCESS")
                    failed = len(result.get("results", [])) - successful

                    logger.info(f"Batch indexing completed: {successful} successful, {failed} failed")

                    return {
                        "total": len(articles),
                        "successful": successful,
                        "failed": failed,
                        "batch_id": result.get("batch_id"),
                        "results": result.get("results", [])
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"Link-content API error: {response.status} - {error_text}")
                    return {"total": len(articles), "successful": 0, "failed": len(articles), "error": error_text}

        except Exception as e:
            logger.error(f"Error in batch indexing: {e}")
            return {"total": len(articles), "successful": 0, "failed": len(articles), "error": str(e)}

    async def query_with_context(self, question: str, news_id: int, article_rag_id: str = None) -> Dict[str, Any]:
        """
        Query RAG with news context using specific file ID

        Args:
            question: User question
            news_id: News article ID for context
            article_rag_id: RAG document ID (if available)

        Returns:
            RAG query response
        """
        try:
            # Prepare query payload with news context
            file_id = article_rag_id or f"news_{news_id}"

            query_payload = {
                "query": question,
                "filters": {
                    "content_type": "news",
                    "file_ids": [file_id]
                },
                "top_k": 5,
                "include_sources": True,
                "answer_style": "detailed"
            }

            headers = {
                "Content-Type": "application/json",
                "x-user-id": "system"
            }

            async with self.session.post(
                f"{self.base_url}/query",
                json=query_payload,
                headers=headers
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"News context query completed for article {news_id}")
                    return result
                else:
                    error_text = await response.text()
                    logger.error(f"RAG query error: {response.status} - {error_text}")
                    return {"success": False, "error": error_text}

        except Exception as e:
            logger.error(f"Error in contextual query: {e}")
            return {"success": False, "error": str(e)}

    async def answer_from_article_content(
        self, 
        question: str, 
        article: 'NewsArticle',
        answer_style: str = "detailed"
    ) -> Dict[str, Any]:
        """
        Answer question directly using article content with LLM (fallback when RAG fails).
        This ensures user NEVER gets an error - we always have the article content.

        Args:
            question: User question
            article: NewsArticle object with full_content
            answer_style: "brief" or "detailed"

        Returns:
            Response dict with answer and sources
        """
        try:
            from .llm_service import LLMService

            llm_service = LLMService(
                openai_api_key=self.settings.openai_api_key,
                anthropic_api_key=self.settings.anthropic_api_key,
                google_api_key=self.settings.google_api_key
            )

            # Build context from article
            article_context = self._build_article_context(article)

            # System prompt for answering from article content
            system_prompt = """You are a legal news assistant helping users understand legal news articles.
Answer the user's question based ONLY on the provided article content.

Guidelines:
1. Be accurate and cite specific parts of the article when possible
2. If the article doesn't contain information to answer the question, say so politely
3. Keep the answer focused on what's in the article
4. Use clear, accessible language while maintaining legal accuracy
5. For legal terms, provide brief explanations if helpful

IMPORTANT: Base your answer strictly on the article content provided. Do not make up information."""

            user_prompt = f"""ARTICLE CONTENT:
Title: {article.title}
Source: {article.source}
Category: {article.category}

{article_context}

---

USER QUESTION: {question}

Please answer the question based on the article content above."""

            # Generate answer
            answer = await llm_service.generate_with_fallback(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.3,
                max_tokens=800 if answer_style == "detailed" else 400
            )

            logger.info(f"Generated answer from article content for article {article.id}")

            return {
                "success": True,
                "answer": answer,
                "sources": [
                    {
                        "text": article.full_content[:500] + "..." if len(article.full_content or "") > 500 else (article.full_content or ""),
                        "source": article.source,
                        "title": article.title
                    }
                ],
                "context_type": "direct_article",
                "rag_indexed": bool(article.rag_document_id)
            }

        except Exception as e:
            logger.error(f"Error answering from article content: {e}")
            # Even this fallback failed - return a graceful response
            return {
                "success": True,  # Still mark as success to not show error
                "answer": f"I can help you understand this article about '{article.title}'. However, I'm having trouble processing your specific question right now. Please try rephrasing your question or ask about the main points of the article.",
                "sources": [],
                "context_type": "fallback",
                "rag_indexed": False
            }

    def _build_article_context(self, article: 'NewsArticle') -> str:
        """Build comprehensive context from article for LLM"""
        parts = []

        # Use formatted content if available
        if article.quick_summary:
            parts.append(f"SUMMARY: {article.quick_summary}")

        if hasattr(article, 'key_points') and article.key_points:
            key_points = article.key_points if isinstance(article.key_points, list) else []
            if key_points:
                parts.append("KEY POINTS:\n" + "\n".join(f"- {kp}" for kp in key_points))

        # Full content
        if article.full_content:
            # Limit to avoid token issues
            content = article.full_content
            if len(content) > 6000:
                content = content[:6000] + "... [content truncated]"
            parts.append(f"FULL CONTENT:\n{content}")
        elif article.description:
            parts.append(f"DESCRIPTION:\n{article.description}")

        # Court/legal context
        if hasattr(article, 'court_name') and article.court_name:
            parts.append(f"COURT: {article.court_name}")
        if hasattr(article, 'bench_info') and article.bench_info:
            parts.append(f"BENCH: {article.bench_info}")

        return "\n\n".join(parts)

    async def generate_summary(self, article: NewsArticle, summary_type: str = "brief") -> str:
        """
        Generate summary for news article using specialized legal prompts

        Args:
            article: NewsArticle object
            summary_type: "brief" or "detailed"

        Returns:
            Generated summary text
        """
        try:
            # Import LLM service for summary generation
            from .llm_service import LLMService

            llm_service = LLMService(
                openai_api_key=self.settings.openai_api_key,
                anthropic_api_key=self.settings.anthropic_api_key,
                google_api_key=self.settings.google_api_key
            )

            # Get appropriate prompt based on summary type
            system_prompt = self._get_summary_prompt(summary_type)

            # Prepare content for summarization
            content = self._prepare_content_for_summary(article)

            # Generate summary
            summary = await llm_service.generate_with_fallback(
                system_prompt=system_prompt,
                user_prompt=content,
                temperature=0.3,
                max_tokens=300 if summary_type == "brief" else 500
            )

            logger.info(f"Generated {summary_type} summary for article {article.id}")
            return summary

        except Exception as e:
            logger.error(f"Error generating summary for article {article.id}: {e}")
            return f"Unable to generate summary: {str(e)}"

    def get_collection_id(self, article: NewsArticle) -> str:
        """
        Determine collection ID based on court type and region

        Args:
            article: NewsArticle object

        Returns:
            Collection ID string
        """
        source = article.source.lower()

        # Extract court type and region from source
        if "supreme court" in source:
            return "news_supreme_court_india"
        elif "bombay" in source or "mumbai" in source:
            return "news_high_court_bombay"
        elif "delhi" in source:
            return "news_high_court_delhi"
        elif "madras" in source or "chennai" in source:
            return "news_high_court_madras"
        elif "calcutta" in source or "kolkata" in source:
            return "news_high_court_calcutta"
        elif "high court" in source:
            # Generic high court collection
            return "news_high_court_other"
        elif "tribunal" in source:
            return "news_tribunals_national"
        else:
            # Default collection for other sources
            return "news_general_legal"

    def _prepare_link_content_item(self, article: NewsArticle) -> Dict[str, Any]:
        """Prepare individual item for link-content API"""
        return {
            "type": "web",
            "file_id": f"news_{article.id}",
            "collection_id": self.get_collection_id(article),
            "url": article.url,
            "content_type": "news",
            "metadata": {
                "news_subcategory": article.category,
                "court_type": self._extract_court_type(article.source),
                "region": self._extract_region(article.source),
                "published_date": article.published_at.isoformat() if article.published_at else None,
                "source_name": article.source,
                "title": article.title
            }
        }

    def _extract_court_type(self, source: str) -> str:
        """Extract court type from source string"""
        source_lower = source.lower()

        if "supreme court" in source_lower:
            return "supreme_court"
        elif "high court" in source_lower:
            return "high_court"
        elif "tribunal" in source_lower:
            return "tribunal"
        elif "district court" in source_lower:
            return "district_court"
        else:
            return "other"

    def _extract_region(self, source: str) -> str:
        """Extract region from source string"""
        source_lower = source.lower()

        # Check for specific regions/cities
        regions = {
            "bombay": "mumbai",
            "mumbai": "mumbai",
            "delhi": "delhi",
            "madras": "chennai",
            "chennai": "chennai",
            "calcutta": "kolkata",
            "kolkata": "kolkata",
            "bangalore": "bangalore",
            "hyderabad": "hyderabad",
            "allahabad": "allahabad"
        }

        for region_key, region_value in regions.items():
            if region_key in source_lower:
                return region_value

        return "national"  # Default for national sources

    def _get_summary_prompt(self, summary_type: str) -> str:
        """Get specialized prompt for legal news summarization"""
        base_prompt = """You are an expert legal analyst specializing in Indian law and constitutional matters.
        Summarize the following legal news article with accuracy and clarity.
        Focus on: court decisions, legal principles applied, constitutional aspects, and practical implications.
        Use clear language suitable for legal professionals and law students."""

        if summary_type == "brief":
            return base_prompt + """

            Provide a concise 2-3 sentence summary highlighting:
            1. The key legal decision or ruling
            2. The court involved
            3. The main legal principle or impact

            Keep it factual and precise."""

        elif summary_type == "detailed":
            return base_prompt + """

            Provide a comprehensive summary including:
            1. Background of the case or legal matter
            2. Key legal arguments and court's reasoning
            3. Specific laws, articles, or precedents involved
            4. Immediate and broader implications for Indian jurisprudence
            5. Impact on citizens or legal practice

            Structure it clearly with proper legal context."""

        else:
            return base_prompt + " Provide a balanced summary of the legal news article."

    def _prepare_content_for_summary(self, article: NewsArticle) -> str:
        """Prepare article content for summarization"""
        content_parts = []

        if article.title:
            content_parts.append(f"Title: {article.title}")

        if article.description:
            content_parts.append(f"Description: {article.description}")

        if article.full_content:
            content_parts.append(f"Full Article: {article.full_content}")
        elif article.description:
            # Use description if full content not available
            content_parts.append(f"Article Content: {article.description}")

        return "\n\n".join(content_parts)

    async def check_indexing_status(self, file_ids: List[str]) -> Dict[str, Any]:
        """
        Check indexing status of articles

        Args:
            file_ids: List of file IDs to check

        Returns:
            Status check results
        """
        try:
            payload = {"file_ids": file_ids}
            headers = {
                "Content-Type": "application/json",
                "x-user-id": "system"
            }

            async with self.session.post(
                f"{self.base_url}/collection/status",
                json=payload,
                headers=headers
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result
                else:
                    error_text = await response.text()
                    logger.error(f"Status check error: {response.status} - {error_text}")
                    return {"message": "Status check failed", "results": []}

        except Exception as e:
            logger.error(f"Error checking indexing status: {e}")
            return {"message": f"Status check error: {str(e)}", "results": []}

# Factory function to create service instance
def create_news_rag_service() -> NewsRagService:
    """Create NewsRagService instance"""
    return NewsRagService()