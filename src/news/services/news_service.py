"""
Read-only News Service for API endpoints
Handles only database reads - no fetching or processing
Returns structured content for rich frontend display
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
    NewsCategoryResponse,
    RelatedArticle,
    SuggestedQuestion,
    ExploreTopic,
    ContentMeta,
    FormattedContent,
    ContentSection
)
from ...services.rag.law_client import LawRagClient
from ...services.background_jobs import index_article_immediately


class NewsService:
    """Read-only news service for API endpoints with structured content"""

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

        # Convert to response format with enhanced fields
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
                quick_summary=article.quick_summary,  # AI-generated summary
                featured_image_url=article.featured_image_url,
                thumbnail_url=article.thumbnail_url,
                image_caption=article.image_caption,
                image_alt_text=article.image_alt_text,
                reading_time_minutes=article.reading_time_minutes,
                ai_enabled=article.ai_enabled
            )
            article_summaries.append(summary)

        return NewsListResponse(
            articles=article_summaries,
            total=total,
            has_more=(offset + limit < total)
        )

    async def get_news_detail(self, news_id: int) -> Optional[NewsDetailResponse]:
        """
        Get full news article with structured content for rich frontend display.
        Frontend becomes a 'dumb renderer' - just displays what backend sends.
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

        # Get related articles with relevance reasons
        related_articles = self._find_related_articles_with_reasons(news_id, article, limit=5)

        # Build content metadata
        meta = ContentMeta(
            reading_time_minutes=article.reading_time_minutes or self._calculate_reading_time(article.full_content),
            word_count=article.word_count or len(article.full_content.split()),
            difficulty="intermediate",  # Could be determined by AI in future
            court=article.court_name,
            bench=article.bench_info
        )

        # Build formatted content from stored JSON
        formatted_content = self._build_formatted_content(article.formatted_content)

        # Build suggested questions from stored JSON
        suggested_questions = self._build_suggested_questions(article.suggested_questions)

        # Build explore topics from stored JSON
        explore_topics = self._build_explore_topics(article.explore_topics)

        # Build key points (ensure it's a list)
        key_points = article.key_points if isinstance(article.key_points, list) else []

        return NewsDetailResponse(
            # Core info
            id=article.id,
            title=article.title,
            url=article.url,
            source=article.source,
            category=article.category,
            published_at=article.published_at,
            
            # Images
            featured_image_url=article.featured_image_url,
            thumbnail_url=article.thumbnail_url,
            image_caption=article.image_caption,
            image_alt_text=article.image_alt_text,
            
            # Metadata
            meta=meta,
            
            # Structured content
            quick_summary=article.quick_summary or article.summary or "",
            key_points=key_points,
            content=formatted_content,
            
            # Suggestions
            suggested_questions=suggested_questions,
            explore_topics=explore_topics,
            
            # Related articles
            related_articles=related_articles,
            
            # Raw content (fallback)
            full_content=article.full_content or "",
            summary=article.summary,
            keywords=article.keywords or [],
            
            # RAG integration
            rag_document_id=article.rag_document_id,
            ai_enabled=article.ai_enabled
        )

    def _find_related_articles_with_reasons(
        self,
        article_id: int,
        current_article: NewsArticle,
        limit: int = 5
    ) -> List[RelatedArticle]:
        """
        Find similar articles by category and source with relevance reasons
        """
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

        related_articles = []
        for article in related:
            # Determine relevance reason
            reasons = []
            if article.category == current_article.category:
                reasons.append(f"Same category: {article.category.title()}")
            if article.source == current_article.source:
                reasons.append(f"Same source")
            
            relevance_reason = " | ".join(reasons) if reasons else "Related legal news"

            related_articles.append(RelatedArticle(
                id=article.id,
                title=article.title,
                source=article.source,
                category=article.category,
                featured_image_url=article.featured_image_url,
                thumbnail_url=article.thumbnail_url,
                published_at=article.published_at,
                relevance_reason=relevance_reason
            ))

        return related_articles

    def _build_formatted_content(self, formatted_content_json) -> FormattedContent:
        """Build FormattedContent from stored JSON"""
        if not formatted_content_json:
            return FormattedContent(sections=[])
        
        sections = []
        content_list = formatted_content_json if isinstance(formatted_content_json, list) else []
        
        for section_data in content_list:
            if isinstance(section_data, dict):
                sections.append(ContentSection(
                    type=section_data.get("type", "paragraph"),
                    text=section_data.get("text"),
                    level=section_data.get("level"),
                    items=section_data.get("items"),
                    attribution=section_data.get("attribution"),
                    style=section_data.get("style"),
                    case_name=section_data.get("case_name"),
                    citation=section_data.get("citation"),
                    court=section_data.get("court")
                ))
        
        return FormattedContent(sections=sections)

    def _build_suggested_questions(self, questions_json) -> List[SuggestedQuestion]:
        """Build SuggestedQuestion list from stored JSON"""
        if not questions_json:
            return []
        
        questions = []
        questions_list = questions_json if isinstance(questions_json, list) else []
        
        for q_data in questions_list:
            if isinstance(q_data, dict) and q_data.get("question"):
                questions.append(SuggestedQuestion(
                    id=q_data.get("id", f"sq_{len(questions)+1}"),
                    question=q_data.get("question", ""),
                    category=q_data.get("category", "legal_general"),
                    icon=q_data.get("icon", "📌")
                ))
        
        return questions

    def _build_explore_topics(self, topics_json) -> List[ExploreTopic]:
        """Build ExploreTopic list from stored JSON"""
        if not topics_json:
            return []
        
        topics = []
        topics_list = topics_json if isinstance(topics_json, list) else []
        
        for t_data in topics_list:
            if isinstance(t_data, dict) and t_data.get("topic"):
                topics.append(ExploreTopic(
                    topic=t_data.get("topic", ""),
                    description=t_data.get("description", ""),
                    icon=t_data.get("icon", "📚"),
                    query=t_data.get("query", t_data.get("topic", ""))
                ))
        
        return topics

    def _calculate_reading_time(self, content: str) -> int:
        """Calculate reading time in minutes (approx 200 words per minute)"""
        if not content:
            return 1
        word_count = len(content.split())
        return max(1, word_count // 200)

    def find_related_articles(self, article_id: int, limit: int = 5) -> List[NewsArticleSummary]:
        """
        Find similar articles by category and source
        Only returns articles with extracted content
        (Kept for backward compatibility)
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
                quick_summary=article.quick_summary,
                featured_image_url=article.featured_image_url,
                thumbnail_url=article.thumbnail_url,
                image_caption=article.image_caption,
                image_alt_text=article.image_alt_text,
                reading_time_minutes=article.reading_time_minutes,
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
