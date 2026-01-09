"""News API response schemas"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class NewsArticleSummary(BaseModel):
    """Summary view of a news article for list responses"""
    id: int
    title: str
    url: str
    source: str
    category: str
    published_at: datetime
    summary: Optional[str] = None
    featured_image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    image_caption: Optional[str] = None
    image_alt_text: Optional[str] = None
    ai_enabled: bool = False  # Indicates if RAG features are available

    class Config:
        from_attributes = True


class NewsListResponse(BaseModel):
    """Response for news list endpoint"""
    articles: List[NewsArticleSummary]
    total: int
    has_more: bool


class NewsDetailResponse(BaseModel):
    """Response for news detail endpoint with full content"""
    id: int
    title: str
    url: str
    source: str
    category: str
    published_at: datetime
    full_content: str
    summary: Optional[str] = None
    keywords: List[str] = []
    related_articles: List[NewsArticleSummary] = []
    rag_document_id: Optional[str] = None
    featured_image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    image_caption: Optional[str] = None
    image_alt_text: Optional[str] = None
    ai_enabled: bool = False  # Indicates if RAG features are available

    class Config:
        from_attributes = True


class NewsCategoryResponse(BaseModel):
    """Response for news categories endpoint"""
    name: str
    count: int
    display_name: str


class NewsCategoriesListResponse(BaseModel):
    """Response for news categories list endpoint"""
    categories: List[NewsCategoryResponse]
    total_categories: int