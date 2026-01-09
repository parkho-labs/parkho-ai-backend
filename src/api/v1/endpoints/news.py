from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from src.core.database import get_db
from src.api.dependencies import get_law_rag_client
from src.services.rag.law_client import LawRagClient
from src.services.news_rag_service import create_news_rag_service, NewsRagService

# Import from news module
from src.news.services.news_service import NewsService
from src.news.schemas.responses import NewsListResponse, NewsDetailResponse, NewsCategoriesListResponse
from src.news.schemas.requests import SummarizeRequest
from src.news.models.news_article import NewsArticle

router = APIRouter()

# Response model for summarize endpoint

class SummarizeResponse(BaseModel):
    summary: str
    summary_type: str
    generated_at: datetime



def get_news_service(
    db: Session = Depends(get_db),
    rag_client: LawRagClient = Depends(get_law_rag_client)
) -> NewsService:
    """Get news service with dependencies"""
    return NewsService(db, rag_client)

@router.get("/", response_model=NewsListResponse)
async def get_news_list(
    source: Optional[str] = Query(None, description="Filter by news source"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    limit: int = Query(20, le=100, description="Number of articles (max 100)"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    sort: str = Query("date", description="Sort by date or relevance"),
    news_service: NewsService = Depends(get_news_service)
):
    """Get news articles with filters"""
    try:
        return news_service.get_news_list(
            source=source,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
            sort=sort
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/categories", response_model=NewsCategoriesListResponse)
async def get_news_categories(news_service: NewsService = Depends(get_news_service)):
    """Get all available news categories with article counts"""
    try:
        return news_service.get_news_categories()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{news_id}", response_model=NewsDetailResponse)
async def get_news_detail(
    news_id: int,
    news_service: NewsService = Depends(get_news_service)
):
    """Get full news article details"""
    try:
        result = await news_service.get_news_detail(news_id)

        if not result:
            raise HTTPException(status_code=404, detail="News article not found")

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{news_id}/summarize", response_model=SummarizeResponse)
async def summarize_news_article(
    news_id: int,
    request: SummarizeRequest,
    db: Session = Depends(get_db)
):
    """Generate AI summary for a news article"""
    try:
        # Get the article
        article = db.query(NewsArticle).filter(NewsArticle.id == news_id).first()

        if not article:
            raise HTTPException(status_code=404, detail="News article not found")

        # Use NewsRagService to generate summary
        async with create_news_rag_service() as rag_service:
            summary = await rag_service.generate_summary(article, request.summary_type)

        return SummarizeResponse(
            summary=summary,
            summary_type=request.summary_type,
            generated_at=datetime.now()
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")

# Note: News fetching and processing is now handled by background cron jobs only.
# Frontend APIs are read-only for optimal performance.

