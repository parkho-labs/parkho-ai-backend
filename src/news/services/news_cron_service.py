"""
News Cron Service
Background processing pipeline for news articles:
1. Fetch from multiple sources
2. Extract full content
3. Download and store images
4. Format content with AI (structured sections, summaries, etc.)
5. Generate suggestions (questions, topics)
6. Index in RAG system
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from ...core.database import SessionLocal
from ..models.news_article import NewsArticle
from .sources.manager import NewsSourceManager
from .content_scraper import ContentScraperService
from .content_formatter import ContentFormatterService
from .question_generator import QuestionGeneratorService
from ...services.background_jobs import index_article_immediately

logger = logging.getLogger(__name__)


class NewsCronService:
    """Main service for background news processing"""

    def __init__(self):
        self.source_manager = NewsSourceManager()
        self.content_scraper = ContentScraperService()
        self.content_formatter = ContentFormatterService()
        self.question_generator = QuestionGeneratorService()

    async def run_complete_pipeline(self, fetch_limit: int = 50) -> Dict[str, Any]:
        """
        Run the complete news processing pipeline
        This is the main function called by cron jobs

        Args:
            fetch_limit: Maximum number of new articles to fetch

        Returns:
            Dict with pipeline statistics
        """
        pipeline_start = datetime.now()
        logger.info(f"🚀 Starting news pipeline at {pipeline_start}")

        stats = {
            "pipeline_start": pipeline_start,
            "fetch_stats": {},
            "content_extraction_stats": {},
            "formatting_stats": {},
            "rag_indexing_stats": {},
            "total_processing_time": 0,
            "success": True,
            "errors": []
        }

        try:
            # Step 1: Fetch new articles from sources
            logger.info("📰 Step 1: Fetching articles from sources...")
            fetch_stats = await self._fetch_and_store_articles(fetch_limit)
            stats["fetch_stats"] = fetch_stats

            # Step 2: Extract content for articles without content
            logger.info("📝 Step 2: Extracting article content...")
            content_stats = await self._extract_content_for_articles()
            stats["content_extraction_stats"] = content_stats

            # Step 3: Format articles with AI
            logger.info("✨ Step 3: Formatting articles with AI...")
            formatting_stats = await self._format_articles_with_ai()
            stats["formatting_stats"] = formatting_stats

            # Step 4: Index articles in RAG system
            logger.info("🤖 Step 4: Indexing articles in RAG...")
            rag_stats = await self._index_articles_in_rag()
            stats["rag_indexing_stats"] = rag_stats

            # Calculate total time
            pipeline_end = datetime.now()
            stats["total_processing_time"] = (pipeline_end - pipeline_start).total_seconds()

            logger.info(f"✅ Pipeline completed successfully in {stats['total_processing_time']:.2f} seconds")
            return stats

        except Exception as e:
            logger.error(f"❌ Pipeline failed: {e}")
            stats["success"] = False
            stats["errors"].append(str(e))
            return stats

    async def _fetch_and_store_articles(self, limit: int) -> Dict[str, Any]:
        """Fetch articles from sources and store basic info"""
        db = SessionLocal()
        try:
            # Fetch from all sources
            fresh_articles = self.source_manager.get_diverse_articles(limit)

            stats = {
                "total_fetched": len(fresh_articles),
                "stored": 0,
                "duplicates": 0,
                "errors": 0,
                "sources": {}
            }

            for article in fresh_articles:
                try:
                    # Check if article already exists
                    existing = db.query(NewsArticle).filter(
                        or_(
                            NewsArticle.url == article.url,
                            NewsArticle.title == article.title
                        )
                    ).first()

                    if existing:
                        stats["duplicates"] += 1
                        continue

                    # Create new article
                    db_article = NewsArticle(
                        title=article.title,
                        url=article.url,
                        source=article.source,
                        category=article.category,
                        published_at=article.published_at,
                        description=article.description,
                        summary=article.description[:500] if article.description else "",
                        keywords=article.keywords,
                        featured_image_url=article.featured_image_url,
                        thumbnail_url=article.thumbnail_url,
                        image_caption=article.image_caption,
                        image_alt_text=article.image_alt_text,
                    )

                    db.add(db_article)
                    stats["stored"] += 1

                    # Track sources
                    source_name = article.source
                    stats["sources"][source_name] = stats["sources"].get(source_name, 0) + 1

                except Exception as e:
                    logger.error(f"Error storing article '{article.title}': {e}")
                    stats["errors"] += 1

            db.commit()
            logger.info(f"✅ Stored {stats['stored']} new articles, skipped {stats['duplicates']} duplicates")
            return stats

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to fetch and store articles: {e}")
            raise e
        finally:
            db.close()

    async def _extract_content_for_articles(self) -> Dict[str, Any]:
        """Extract full content for articles that don't have it"""
        db = SessionLocal()
        try:
            # Find articles without content (limit to recent articles to avoid processing old ones)
            articles_needing_content = db.query(NewsArticle).filter(
                or_(
                    NewsArticle.full_content.is_(None),
                    NewsArticle.full_content == ''
                )
            ).order_by(NewsArticle.created_at.desc()).limit(50).all()

            stats = {
                "articles_processed": 0,
                "content_extracted": 0,
                "images_downloaded": 0,
                "extraction_failures": 0,
                "image_failures": 0
            }

            for article in articles_needing_content:
                try:
                    logger.info(f"📄 Extracting content for: {article.title[:50]}...")

                    # Extract content and image with smart extraction
                    content, image_gcs_url = self.content_scraper.process_article(
                        url=article.url,
                        article_id=article.id,
                        source=article.news_source or article.source,
                        category=article.category
                    )

                    # Update article
                    if content:
                        article.full_content = content
                        article.word_count = len(content.split())
                        article.reading_time_minutes = max(1, article.word_count // 200)
                        stats["content_extracted"] += 1
                        logger.info(f"  ✅ Extracted {len(content)} characters")

                    if image_gcs_url:
                        article.featured_image_url = image_gcs_url
                        article.thumbnail_url = image_gcs_url
                        stats["images_downloaded"] += 1
                        logger.info(f"  🖼️ Downloaded image: {image_gcs_url}")

                    article.updated_at = datetime.now()
                    stats["articles_processed"] += 1

                except Exception as e:
                    logger.error(f"Failed to extract content for article {article.id}: {e}")
                    stats["extraction_failures"] += 1

            db.commit()
            logger.info(f"✅ Content extraction completed: {stats['content_extracted']}/{stats['articles_processed']} successful")
            return stats

        except Exception as e:
            db.rollback()
            logger.error(f"Failed content extraction process: {e}")
            raise e
        finally:
            db.close()

    async def _format_articles_with_ai(self) -> Dict[str, Any]:
        """Format articles with AI - generate structured content, summaries, and suggestions"""
        db = SessionLocal()
        try:
            # Find articles with content but not yet formatted
            articles_to_format = db.query(NewsArticle).filter(
                and_(
                    NewsArticle.full_content.isnot(None),
                    NewsArticle.full_content != '',
                    or_(
                        NewsArticle.is_formatted.is_(None),
                        NewsArticle.is_formatted == False
                    )
                )
            ).order_by(NewsArticle.created_at.desc()).limit(20).all()

            stats = {
                "articles_processed": 0,
                "successfully_formatted": 0,
                "questions_generated": 0,
                "formatting_failures": 0
            }

            for article in articles_to_format:
                try:
                    logger.info(f"✨ Formatting article: {article.title[:50]}...")

                    # Step 1: Format content with AI
                    formatted = await self.content_formatter.format_article(
                        title=article.title,
                        content=article.full_content,
                        source=article.source,
                        category=article.category
                    )

                    # Update article with formatted content
                    article.quick_summary = formatted.quick_summary
                    article.key_points = formatted.key_points
                    article.formatted_content = formatted.formatted_content
                    article.reading_time_minutes = formatted.reading_time_minutes
                    article.word_count = formatted.word_count
                    article.court_name = formatted.court_name
                    article.bench_info = formatted.bench_info

                    logger.info(f"  📝 Formatted content with {len(formatted.formatted_content)} sections")

                    # Step 2: Generate suggestions
                    suggestions = await self.question_generator.generate_suggestions(
                        title=article.title,
                        content=article.full_content[:2000],  # Use first 2000 chars
                        category=article.category,
                        keywords=article.keywords or []
                    )

                    # Convert to serializable format
                    article.suggested_questions = [
                        {
                            "id": q.id,
                            "question": q.question,
                            "category": q.category,
                            "icon": q.icon
                        }
                        for q in suggestions.suggested_questions
                    ]

                    article.explore_topics = [
                        {
                            "topic": t.topic,
                            "description": t.description,
                            "icon": t.icon,
                            "query": t.query
                        }
                        for t in suggestions.explore_topics
                    ]

                    logger.info(f"  💡 Generated {len(suggestions.suggested_questions)} questions, {len(suggestions.explore_topics)} topics")

                    # Mark as formatted
                    article.is_formatted = True
                    article.updated_at = datetime.now()

                    stats["successfully_formatted"] += 1
                    stats["questions_generated"] += len(suggestions.suggested_questions)
                    stats["articles_processed"] += 1

                except Exception as e:
                    logger.error(f"Failed to format article {article.id}: {e}")
                    stats["formatting_failures"] += 1
                    stats["articles_processed"] += 1

            db.commit()
            logger.info(f"✅ AI formatting completed: {stats['successfully_formatted']}/{stats['articles_processed']} successful")
            return stats

        except Exception as e:
            db.rollback()
            logger.error(f"Failed AI formatting process: {e}")
            raise e
        finally:
            db.close()

    async def _index_articles_in_rag(self) -> Dict[str, Any]:
        """Index articles in RAG system that have content but aren't indexed"""
        db = SessionLocal()
        try:
            # Find articles ready for RAG indexing (formatted and not indexed)
            articles_for_rag = db.query(NewsArticle).filter(
                NewsArticle.full_content.isnot(None),
                NewsArticle.full_content != '',
                NewsArticle.is_rag_indexed == False
            ).order_by(NewsArticle.created_at.desc()).limit(30).all()

            stats = {
                "articles_processed": 0,
                "successfully_indexed": 0,
                "indexing_failures": 0,
                "skipped": 0
            }

            for article in articles_for_rag:
                try:
                    logger.info(f"🤖 Indexing in RAG: {article.title[:50]}...")

                    # Use existing background indexing function
                    result = await index_article_immediately(article.id)

                    if result.get("success"):
                        article.is_rag_indexed = True
                        article.rag_document_id = result.get("document_id")
                        stats["successfully_indexed"] += 1
                        logger.info(f"  ✅ Successfully indexed with document ID: {result.get('document_id')}")
                    else:
                        stats["indexing_failures"] += 1
                        logger.warning(f"  ⚠️ Indexing failed: {result.get('error', 'Unknown error')}")

                    stats["articles_processed"] += 1

                except Exception as e:
                    logger.error(f"Failed to index article {article.id}: {e}")
                    stats["indexing_failures"] += 1

            db.commit()
            logger.info(f"✅ RAG indexing completed: {stats['successfully_indexed']}/{stats['articles_processed']} successful")
            return stats

        except Exception as e:
            db.rollback()
            logger.error(f"Failed RAG indexing process: {e}")
            raise e
        finally:
            db.close()

    def get_pipeline_health(self) -> Dict[str, Any]:
        """Check the health of the news processing pipeline"""
        db = SessionLocal()
        try:
            # Get statistics about articles in different states
            total_articles = db.query(NewsArticle).count()

            articles_with_content = db.query(NewsArticle).filter(
                NewsArticle.full_content.isnot(None),
                NewsArticle.full_content != ''
            ).count()

            articles_formatted = db.query(NewsArticle).filter(
                NewsArticle.is_formatted == True
            ).count()

            articles_rag_indexed = db.query(NewsArticle).filter(
                NewsArticle.is_rag_indexed == True
            ).count()

            # Calculate percentages
            content_extraction_rate = (articles_with_content / total_articles * 100) if total_articles > 0 else 0
            formatting_rate = (articles_formatted / total_articles * 100) if total_articles > 0 else 0
            rag_indexing_rate = (articles_rag_indexed / total_articles * 100) if total_articles > 0 else 0

            health_status = {
                "total_articles": total_articles,
                "articles_with_content": articles_with_content,
                "articles_formatted": articles_formatted,
                "articles_rag_indexed": articles_rag_indexed,
                "content_extraction_rate": round(content_extraction_rate, 2),
                "formatting_rate": round(formatting_rate, 2),
                "rag_indexing_rate": round(rag_indexing_rate, 2),
                "source_health": self.source_manager.health_check(),
                "overall_health": "healthy" if content_extraction_rate > 80 and formatting_rate > 70 else "needs_attention"
            }

            logger.info(f"Pipeline health check: {health_status['overall_health']}")
            return health_status

        except Exception as e:
            logger.error(f"Failed to check pipeline health: {e}")
            return {"error": str(e), "overall_health": "error"}
        finally:
            db.close()


# Main function for cron job execution
async def run_news_cron_job(fetch_limit: int = 50):
    """
    Main function to be called by cron jobs

    Args:
        fetch_limit: Number of articles to fetch in this run
    """
    service = NewsCronService()
    return await service.run_complete_pipeline(fetch_limit)


# Health check function
def check_news_pipeline_health():
    """
    Quick health check function
    """
    service = NewsCronService()
    return service.get_pipeline_health()
