"""
Background job service for news RAG indexing
Handles automatic indexing of news articles in batches
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import List
from sqlalchemy.orm import Session

from ..core.database import SessionLocal
from ..models.news_article import NewsArticle
from .news_rag_service import create_news_rag_service

logger = logging.getLogger(__name__)

class BackgroundIndexingService:
    """Service for background RAG indexing operations"""

    def __init__(self, batch_size: int = 10):
        self.batch_size = batch_size

    async def index_pending_articles(self) -> dict:
        """
        Index articles that haven't been indexed yet

        Returns:
            Dictionary with indexing results
        """
        db = SessionLocal()
        try:
            # Find articles not yet indexed
            pending_articles = db.query(NewsArticle).filter(
                NewsArticle.rag_document_id.is_(None)
            ).limit(self.batch_size).all()

            if not pending_articles:
                logger.info("No pending articles to index")
                return {"total": 0, "successful": 0, "failed": 0}

            logger.info(f"Found {len(pending_articles)} articles to index")

            # Index articles using NewsRagService
            async with create_news_rag_service() as rag_service:
                result = await rag_service.batch_index_articles(pending_articles)

            # Update articles with RAG document IDs
            if result.get("results"):
                successful_results = [r for r in result["results"] if r.get("status") == "INDEXING_SUCCESS"]

                for i, article in enumerate(pending_articles):
                    if i < len(successful_results):
                        result_item = successful_results[i]
                        if result_item.get("status") == "INDEXING_SUCCESS":
                            article.rag_document_id = result_item.get("document_id")
                            article.rag_indexed_at = datetime.now()

                db.commit()
                logger.info(f"Updated {len(successful_results)} articles with RAG document IDs")

            return result

        except Exception as e:
            db.rollback()
            logger.error(f"Error in background indexing: {e}")
            return {"total": 0, "successful": 0, "failed": 0, "error": str(e)}

        finally:
            db.close()

    async def reindex_failed_articles(self, max_age_hours: int = 24) -> dict:
        """
        Retry indexing articles that failed in the past

        Args:
            max_age_hours: Only retry articles newer than this age

        Returns:
            Dictionary with reindexing results
        """
        db = SessionLocal()
        try:
            # Find articles that failed indexing in the last N hours
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)

            failed_articles = db.query(NewsArticle).filter(
                NewsArticle.rag_document_id.is_(None),
                NewsArticle.created_at >= cutoff_time
            ).limit(self.batch_size).all()

            if not failed_articles:
                logger.info("No failed articles to reindex")
                return {"total": 0, "successful": 0, "failed": 0}

            logger.info(f"Retrying indexing for {len(failed_articles)} failed articles")

            # Retry indexing
            async with create_news_rag_service() as rag_service:
                result = await rag_service.batch_index_articles(failed_articles)

            # Update successful articles
            if result.get("results"):
                successful_results = [r for r in result["results"] if r.get("status") == "INDEXING_SUCCESS"]

                for i, article in enumerate(failed_articles):
                    if i < len(successful_results):
                        result_item = successful_results[i]
                        if result_item.get("status") == "INDEXING_SUCCESS":
                            article.rag_document_id = result_item.get("document_id")
                            article.rag_indexed_at = datetime.now()

                db.commit()
                logger.info(f"Successfully reindexed {len(successful_results)} articles")

            return result

        except Exception as e:
            db.rollback()
            logger.error(f"Error in reindexing: {e}")
            return {"total": 0, "successful": 0, "failed": 0, "error": str(e)}

        finally:
            db.close()

    async def check_indexing_health(self) -> dict:
        """
        Check the health of RAG indexing

        Returns:
            Health status dictionary
        """
        db = SessionLocal()
        try:
            total_articles = db.query(NewsArticle).count()
            indexed_articles = db.query(NewsArticle).filter(
                NewsArticle.rag_document_id.isnot(None)
            ).count()
            pending_articles = total_articles - indexed_articles

            # Check for old unindexed articles (older than 1 hour)
            old_cutoff = datetime.now() - timedelta(hours=1)
            old_unindexed = db.query(NewsArticle).filter(
                NewsArticle.rag_document_id.is_(None),
                NewsArticle.created_at < old_cutoff
            ).count()

            indexing_rate = (indexed_articles / total_articles * 100) if total_articles > 0 else 100

            health_status = {
                "total_articles": total_articles,
                "indexed_articles": indexed_articles,
                "pending_articles": pending_articles,
                "old_unindexed_articles": old_unindexed,
                "indexing_rate_percent": round(indexing_rate, 2),
                "health_status": "healthy" if old_unindexed == 0 and indexing_rate > 95 else "needs_attention"
            }

            logger.info(f"Indexing health check: {health_status}")
            return health_status

        except Exception as e:
            logger.error(f"Error checking indexing health: {e}")
            return {"error": str(e), "health_status": "error"}

        finally:
            db.close()

# Scheduled job function for cron or task scheduler
async def run_background_indexing():
    """
    Main function to run background indexing
    Can be called by cron job or task scheduler
    """
    logger.info("Starting background RAG indexing job")

    service = BackgroundIndexingService(batch_size=20)

    # Index new articles
    index_result = await service.index_pending_articles()

    # Retry failed articles (from last 24 hours)
    retry_result = await service.reindex_failed_articles(max_age_hours=24)

    # Check overall health
    health_result = await service.check_indexing_health()

    results = {
        "timestamp": datetime.now().isoformat(),
        "new_indexing": index_result,
        "retry_indexing": retry_result,
        "health_check": health_result
    }

    logger.info(f"Background indexing job completed: {results}")
    return results

# Function for immediate indexing (can be called from endpoints)
async def index_article_immediately(article_id: int) -> dict:
    """
    Index a specific article immediately

    Args:
        article_id: ID of the article to index

    Returns:
        Indexing result
    """
    db = SessionLocal()
    try:
        article = db.query(NewsArticle).filter(NewsArticle.id == article_id).first()

        if not article:
            return {"success": False, "error": "Article not found"}

        if article.rag_document_id:
            return {"success": True, "message": "Article already indexed", "document_id": article.rag_document_id}

        # Index the single article
        async with create_news_rag_service() as rag_service:
            result = await rag_service.batch_index_articles([article])

        # Update article if successful
        if result.get("successful", 0) > 0 and result.get("results"):
            first_result = result["results"][0]
            if first_result.get("status") == "INDEXING_SUCCESS":
                article.rag_document_id = first_result.get("document_id")
                article.rag_indexed_at = datetime.now()
                db.commit()

                return {
                    "success": True,
                    "document_id": article.rag_document_id,
                    "indexed_at": article.rag_indexed_at
                }

        return {"success": False, "error": "Indexing failed", "details": result}

    except Exception as e:
        db.rollback()
        logger.error(f"Error indexing article {article_id}: {e}")
        return {"success": False, "error": str(e)}

    finally:
        db.close()