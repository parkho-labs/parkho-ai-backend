"""
Read-only News Service for API endpoints
Handles only database reads - no fetching or processing
"""

from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_, func

from ..models.news_article import NewsArticle
from ..schemas.responses import (
    NewsListResponse,
    NewsDetailResponse,
    NewsArticleSummary,
    NewsCategoriesListResponse,
    NewsCategoryResponse
)
from ...services.rag.law_client import LawRagClient
from ...services.background_jobs import index_article_immediately


class NewsService:
    """Read-only news service for API endpoints"""

    def __init__(self, db: Session, rag_client: Optional[LawRagClient] = None):
        self.db = db
        self.rag_client = rag_client

    def get_news_list(
        self,
        source: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 20,
        offset: int = 0,
        sort: str = "date"
    ) -> NewsListResponse:
        """
        Get filtered news list - only returns articles with extracted content
        """
        # Base query - only articles with content
        query = self.db.query(NewsArticle).filter(
            and_(
                NewsArticle.full_content.isnot(None),
                NewsArticle.full_content != ''
            )
        )

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
                image_alt_text=article.image_alt_text,
                ai_enabled=article.ai_enabled  # Uses the property from the model
            )
            article_summaries.append(summary)

        return NewsListResponse(
            articles=article_summaries,
            total=total,
            has_more=(offset + limit < total)
        )

    async def get_news_detail(self, news_id: int) -> Optional[NewsDetailResponse]:
        """
        Get full news article with RAG indexing if needed
        Only returns articles with extracted content
        """
        article = self.db.query(NewsArticle).filter(
            and_(
                NewsArticle.id == news_id,
                NewsArticle.full_content.isnot(None),
                NewsArticle.full_content != ''
            )
        ).first()

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
            image_alt_text=article.image_alt_text,
            ai_enabled=article.ai_enabled  # Uses the property from the model
        )

    def find_related_articles(self, article_id: int, limit: int = 5) -> List[NewsArticleSummary]:
        """
        Find similar articles by category and source
        Only returns articles with extracted content
        """
        current_article = self.db.query(NewsArticle).filter(NewsArticle.id == article_id).first()

        if not current_article:
            return []

        # Find related articles by category or source
        related = self.db.query(NewsArticle).filter(
            and_(
                NewsArticle.id != article_id,
                NewsArticle.full_content.isnot(None),
                NewsArticle.full_content != '',
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
                image_alt_text=article.image_alt_text,
                ai_enabled=article.ai_enabled
            )
            related_summaries.append(summary)

        return related_summaries

    def get_news_categories(self) -> NewsCategoriesListResponse:
        """
        Get all available news categories with article counts
        Only counts articles with extracted content
        """
        # Get categories with counts
        categories_data = self.db.query(
            NewsArticle.category,
            func.count(NewsArticle.id).label('count')
        ).filter(
            and_(
                NewsArticle.full_content.isnot(None),
                NewsArticle.full_content != ''
            )
        ).group_by(NewsArticle.category).order_by(NewsArticle.category).all()

        categories = [
            NewsCategoryResponse(
                name=category,
                count=count,
                display_name=category.replace("_", " ").title()
            )
            for category, count in categories_data
        ]

        return NewsCategoriesListResponse(
            categories=categories,
            total_categories=len(categories)
        )