"""News API response schemas with structured content support"""

from datetime import datetime
from typing import List, Optional, Union
from pydantic import BaseModel, Field


# ============================================================================
# Content Section Types
# ============================================================================

class ContentSection(BaseModel):
    """A section of formatted content for rendering"""
    type: str  # paragraph, heading, quote, list, case_citation, highlight
    text: Optional[str] = None
    level: Optional[int] = None  # For headings (2, 3)
    items: Optional[List[str]] = None  # For lists
    attribution: Optional[str] = None  # For quotes
    style: Optional[str] = None  # bullet, numbered
    # For case citations
    case_name: Optional[str] = None
    citation: Optional[str] = None
    court: Optional[str] = None


class FormattedContent(BaseModel):
    """Structured content for rendering - frontend just maps and displays"""
    sections: List[ContentSection] = []


# ============================================================================
# Metadata
# ============================================================================

class ContentMeta(BaseModel):
    """Article metadata for display"""
    reading_time_minutes: int = 0
    word_count: int = 0
    difficulty: str = "general"  # general, intermediate, advanced
    court: Optional[str] = None
    bench: Optional[str] = None


# ============================================================================
# Suggestions (AI-generated, context-specific)
# ============================================================================

class SuggestedQuestion(BaseModel):
    """AI-generated contextual question for the article"""
    id: str
    question: str
    category: str  # legal_procedure, constitutional, criminal_law, civil_law, etc.
    icon: str  # Emoji for frontend display


class ExploreTopic(BaseModel):
    """Topic to explore further with RAG"""
    topic: str
    description: str
    icon: str
    action: str = "explore_topic"
    query: str  # Query to send to RAG system


# ============================================================================
# Related Articles
# ============================================================================

class RelatedArticle(BaseModel):
    """Related article with relevance context"""
    id: int
    title: str
    source: str
    category: str
    featured_image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    published_at: datetime
    relevance_reason: str  # Why this article is related

    class Config:
        from_attributes = True


# ============================================================================
# Article Summary (for list views)
# ============================================================================

class NewsArticleSummary(BaseModel):
    """Summary view of a news article for list responses"""
    id: int
    title: str
    url: str
    source: str
    category: str
    published_at: datetime
    summary: Optional[str] = None
    # Use quick_summary if available, fallback to summary
    quick_summary: Optional[str] = None
    featured_image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    image_caption: Optional[str] = None
    image_alt_text: Optional[str] = None
    reading_time_minutes: Optional[int] = None
    ai_enabled: bool = False  # Indicates if RAG features are available

    class Config:
        from_attributes = True


# ============================================================================
# List Response
# ============================================================================

class NewsListResponse(BaseModel):
    """Response for news list endpoint"""
    articles: List[NewsArticleSummary]
    total: int
    has_more: bool


# ============================================================================
# Detail Response (Full article with all structured content)
# ============================================================================

class NewsDetailResponse(BaseModel):
    """
    Complete news response with structured content.
    Frontend becomes a 'dumb renderer' - just displays what backend sends.
    """
    # Core info
    id: int
    title: str
    url: str
    source: str
    category: str
    published_at: datetime
    
    # Images
    featured_image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    image_caption: Optional[str] = None
    image_alt_text: Optional[str] = None
    
    # Metadata
    meta: ContentMeta = Field(default_factory=ContentMeta)
    
    # Structured content (AI-formatted)
    quick_summary: Optional[str] = None  # 2-3 sentence summary
    key_points: List[str] = []  # 3-5 bullet points
    content: FormattedContent = Field(default_factory=FormattedContent)  # Structured sections
    
    # Contextual suggestions (AI-generated)
    suggested_questions: List[SuggestedQuestion] = []
    explore_topics: List[ExploreTopic] = []
    
    # Related articles
    related_articles: List[RelatedArticle] = []
    
    # Raw content (fallback)
    full_content: str = ""
    summary: Optional[str] = None
    keywords: List[str] = []
    
    # RAG integration
    rag_document_id: Optional[str] = None
    ai_enabled: bool = False  # Indicates if RAG features are available

    class Config:
        from_attributes = True


# ============================================================================
# Category Response
# ============================================================================

class NewsCategoryResponse(BaseModel):
    """Response for news categories endpoint"""
    name: str
    count: int
    display_name: str


class NewsCategoriesListResponse(BaseModel):
    """Response for news categories list endpoint"""
    categories: List[NewsCategoryResponse]
    total_categories: int


# ============================================================================
# Ask Question Response (Q&A for news articles)
# ============================================================================

class NewsAnswerSource(BaseModel):
    """Source information for a news answer"""
    text: str
    title: Optional[str] = None
    source: Optional[str] = None


class NewsAskQuestionResponse(BaseModel):
    """
    Response model for news question answering.
    
    This response is returned by POST /news/{news_id}/ask-question
    
    Attributes:
        answer: AI-generated answer based on the article
        sources: Source snippets from the article content
        article_title: Title of the article being queried
        article_id: ID of the article
        rag_indexed: True if RAG was used, False if direct LLM fallback
        context_type: "rag" | "direct_article" | "fallback"
    """
    answer: str
    sources: List[NewsAnswerSource] = []
    article_title: str
    article_id: int
    rag_indexed: bool  # Indicates if RAG was used or direct LLM
    context_type: str  # "rag" or "direct_article" or "fallback"
