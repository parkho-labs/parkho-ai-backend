from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_

from ..models.news_article import NewsArticle
from ..api.v1.schemas import NewsListResponse, NewsDetailResponse, NewsArticleSummary
from .rag.law_client import LawRagClient
from .background_jobs import index_article_immediately
from .news_sources.manager import NewsSourceManager

class NewsService:
    def __init__(self, db: Session, rag_client: Optional[LawRagClient] = None):
        self.db = db
        self.rag_client = rag_client
        self.news_manager = NewsSourceManager()

    def get_news_list(
        self,
        source: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 20,
        offset: int = 0,
        sort: str = "date"
    ) -> NewsListResponse:
        """Get filtered news list"""
        query = self.db.query(NewsArticle)

        # Apply filters
        if source:
            query = query.filter(NewsArticle.source.ilike(f'%{source}%'))

        if start_date:
            query = query.filter(NewsArticle.published_at >= start_date)

        if end_date:
            query = query.filter(NewsArticle.published_at <= end_date)

        # Apply sorting
        if sort == "date":
            query = query.order_by(desc(NewsArticle.published_at))

        # Get total count
        total = query.count()

        # Apply pagination
        articles = query.offset(offset).limit(limit).all()

        # Convert to response format
        article_summaries = []
        for article in articles:
            summary = NewsArticleSummary(
                id=article.id,
                title=article.title,
                url=article.url,
                source=article.source,
                category=article.category,
                published_at=article.published_at,
                summary=article.summary,
                featured_image_url=article.featured_image_url,
                thumbnail_url=article.thumbnail_url,
                image_caption=article.image_caption,
                image_alt_text=article.image_alt_text
            )
            article_summaries.append(summary)

        return NewsListResponse(
            articles=article_summaries,
            total=total,
            has_more=(offset + limit < total)
        )

    async def get_news_detail(self, news_id: int) -> Optional[NewsDetailResponse]:
        """Get full news article with RAG indexing"""
        article = self.db.query(NewsArticle).filter(NewsArticle.id == news_id).first()

        if not article:
            return None

        # Index in RAG if not already indexed - trigger immediate indexing
        if not article.rag_document_id:
            index_result = await index_article_immediately(article.id)
            if index_result.get("success") and index_result.get("document_id"):
                # Refresh article from DB to get updated rag_document_id
                self.db.refresh(article)

        # Get related articles
        related_articles = self.find_related_articles(news_id, limit=5)

        return NewsDetailResponse(
            id=article.id,
            title=article.title,
            url=article.url,
            source=article.source,
            category=article.category,
            published_at=article.published_at,
            full_content=article.full_content or "",
            summary=article.summary,
            keywords=article.keywords or [],
            related_articles=related_articles,
            rag_document_id=article.rag_document_id,
            featured_image_url=article.featured_image_url,
            thumbnail_url=article.thumbnail_url,
            image_caption=article.image_caption,
            image_alt_text=article.image_alt_text
        )


    def find_related_articles(self, article_id: int, limit: int = 5) -> List[NewsArticleSummary]:
        """Find similar articles by category and source"""
        current_article = self.db.query(NewsArticle).filter(NewsArticle.id == article_id).first()

        if not current_article:
            return []

        # Find related articles by category or source
        related = self.db.query(NewsArticle).filter(
            and_(
                NewsArticle.id != article_id,
                or_(
                    NewsArticle.category == current_article.category,
                    NewsArticle.source == current_article.source
                )
            )
        ).order_by(desc(NewsArticle.published_at)).limit(limit).all()

        related_summaries = []
        for article in related:
            summary = NewsArticleSummary(
                id=article.id,
                title=article.title,
                url=article.url,
                source=article.source,
                category=article.category,
                published_at=article.published_at,
                summary=article.summary,
                featured_image_url=article.featured_image_url,
                thumbnail_url=article.thumbnail_url,
                image_caption=article.image_caption,
                image_alt_text=article.image_alt_text
            )
            related_summaries.append(summary)

        return related_summaries

    def fetch_and_store_fresh_news(self, limit: int = 30) -> dict:
        """
        Fetch fresh news from multiple sources and store in database.
        Returns statistics about the operation.
        """
        print(f"🔄 Fetching {limit} fresh articles from multiple sources...")

        try:
            # Fetch articles from all sources
            fresh_articles = self.news_manager.get_diverse_articles(limit)

            if not fresh_articles:
                return {"success": False, "message": "No articles fetched", "stats": {}}

            stats = {
                "total_fetched": len(fresh_articles),
                "stored": 0,
                "duplicates": 0,
                "errors": 0,
                "sources": {}
            }

            for article in fresh_articles:
                try:
                    # Check if article already exists (by URL or title)
                    existing = self.db.query(NewsArticle).filter(
                        or_(
                            NewsArticle.url == article.url,
                            NewsArticle.title == article.title
                        )
                    ).first()

                    if existing:
                        stats["duplicates"] += 1
                        continue

                    # Create new article in database
                    db_article = NewsArticle(
                        title=article.title,
                        url=article.url,
                        source=article.source,
                        category=article.category,
                        published_at=article.published_at,
                        full_content=article.description,  # Use description as content for now
                        summary=article.description[:500],  # First 500 chars as summary
                        keywords=article.keywords,
                        featured_image_url=article.featured_image_url,
                        thumbnail_url=article.thumbnail_url,
                        image_caption=article.image_caption,
                        image_alt_text=article.image_alt_text
                    )

                    self.db.add(db_article)
                    stats["stored"] += 1

                    # Track sources
                    source_name = article.source
                    stats["sources"][source_name] = stats["sources"].get(source_name, 0) + 1

                except Exception as e:
                    print(f"  ⚠️ Error storing article '{article.title}': {e}")
                    stats["errors"] += 1

            # Commit all changes
            self.db.commit()

            print(f"✅ Successfully stored {stats['stored']} new articles")
            print(f"📊 Duplicates skipped: {stats['duplicates']}")
            print(f"❌ Errors: {stats['errors']}")

            return {
                "success": True,
                "message": f"Stored {stats['stored']} new articles",
                "stats": stats
            }

        except Exception as e:
            self.db.rollback()
            print(f"❌ Failed to fetch and store news: {e}")
            return {
                "success": False,
                "message": f"Failed to fetch news: {str(e)}",
                "stats": {}
            }

    def get_source_health(self) -> dict:
        """Get health status of all news sources"""
        return self.news_manager.health_check()

    def get_available_sources(self) -> List[str]:
        """Get list of available news sources"""
        return self.news_manager.get_available_sources()

    def get_source_info(self) -> dict:
        """Get detailed information about all sources"""
        return self.news_manager.get_source_info()