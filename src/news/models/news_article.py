from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON
from sqlalchemy.sql import func

from ...core.database import Base


class NewsArticle(Base):
    """
    NewsArticle model with structured content for rich frontend display.
    Supports AI-formatted content, suggested questions, and related topics.
    """
    __tablename__ = "news_articles"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Core article info
    title = Column(String(500), nullable=False)
    url = Column(String(1000), nullable=False, unique=True)
    source = Column(String(200), nullable=False)
    category = Column(String(100), nullable=False)

    # Content fields (raw)
    description = Column(Text)
    full_content = Column(Text)
    summary = Column(Text)
    keywords = Column(JSON)

    # Structured content (AI-formatted)
    formatted_content = Column(JSON)  # Structured sections: paragraph, heading, quote, list, etc.
    quick_summary = Column(Text)  # AI-generated 2-3 sentence summary
    key_points = Column(JSON)  # List of 3-5 bullet points
    
    # Contextual suggestions (AI-generated)
    suggested_questions = Column(JSON)  # Context-specific questions for the article
    explore_topics = Column(JSON)  # Related topics to explore with RAG queries
    
    # Article metadata
    reading_time_minutes = Column(Integer)  # Calculated reading time
    word_count = Column(Integer)  # Word count of full content
    court_name = Column(String(200))  # Court name if judicial news
    bench_info = Column(String(500))  # Bench/judge information

    # Image fields
    featured_image_url = Column(String(1000))
    thumbnail_url = Column(String(1000))
    image_caption = Column(String(500))
    image_alt_text = Column(String(200))

    # RAG integration
    rag_document_id = Column(String(255))
    is_rag_indexed = Column(Boolean, default=False)

    # Source tracking and processing
    news_source = Column(String(200))  # Specific source (e.g., "Indian Kanoon - Supreme Court")
    content_processed = Column(Boolean, default=False)  # Track if content has been cleaned
    is_formatted = Column(Boolean, default=False)  # Track if AI formatting is complete

    # Timestamps
    published_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<NewsArticle(id={self.id}, title='{self.title[:50]}...', source='{self.source}')>"

    @property
    def has_content(self) -> bool:
        """Check if article has extracted content"""
        return self.full_content is not None and self.full_content.strip() != ""

    @property
    def ai_enabled(self) -> bool:
        """User-facing property to indicate if AI features are available"""
        return bool(self.is_rag_indexed)