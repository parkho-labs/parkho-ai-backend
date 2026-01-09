from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON
from sqlalchemy.sql import func

from ..core.database import Base

class NewsArticle(Base):
    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    url = Column(String(1000), nullable=False, unique=True)
    description = Column(Text)
    source = Column(String(200), nullable=False)
    category = Column(String(100), nullable=False)

    full_content = Column(Text)
    summary = Column(Text)
    keywords = Column(JSON)

    published_at = Column(DateTime)
    fetched_at = Column(DateTime, default=func.now())

    # Image fields
    featured_image_url = Column(String(1000))
    thumbnail_url = Column(String(1000))
    image_caption = Column(String(500))
    image_alt_text = Column(String(200))

    rag_document_id = Column(String(255))
    rag_indexed_at = Column(DateTime)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())