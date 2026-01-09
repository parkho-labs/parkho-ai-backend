from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON
from sqlalchemy.sql import func

from ...core.database import Base


class NewsArticle(Base):
    """
    Clean NewsArticle model with essential fields only.
    Optimized for performance and simplicity.
    """
    __tablename__ = "news_articles"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Core article info
    title = Column(String(500), nullable=False)
    url = Column(String(1000), nullable=False, unique=True)
    source = Column(String(200), nullable=False)
    category = Column(String(100), nullable=False)

    # Content fields
    description = Column(Text)
    full_content = Column(Text)
    summary = Column(Text)
    keywords = Column(JSON)

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