from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
import structlog

from src.core.database import get_db
from src.api.dependencies import get_law_rag_client
from src.services.rag.law_client import LawRagClient
from src.services.news_rag_service import create_news_rag_service

# Import from news module
from src.news.services.news_service import NewsService
from src.news.schemas.responses import (
    NewsListResponse, 
    NewsDetailResponse, 
    NewsCategoriesListResponse,
    NewsAskQuestionResponse,
    NewsAnswerSource
)
from src.news.schemas.requests import SummarizeRequest, NewsAskQuestionRequest
from src.news.models.news_article import NewsArticle

logger = structlog.get_logger(__name__)

router = APIRouter()


# Local response model for summarize endpoint
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


@router.post("/{news_id}/ask-question", response_model=NewsAskQuestionResponse)
async def ask_question_about_news(
    news_id: int,
    request: NewsAskQuestionRequest,
    db: Session = Depends(get_db)
):
    """
    Ask a question about a specific news article.
    
    This endpoint provides intelligent Q&A for news articles:
    - If article is indexed in RAG: Uses RAG for semantic search
    - If RAG fails or not indexed: Falls back to direct LLM with article content
    - NEVER returns an error to user - always provides an answer
    
    Endpoint: POST /api/v1/news/{news_id}/ask-question
    
    Request Body:
        question: The question about the news article (5-500 characters)
    
    Response:
        answer: AI-generated answer based on the article
        sources: Source snippets from the article
        article_title: Title of the article
        article_id: ID of the article
        rag_indexed: Whether RAG was used (true) or direct LLM (false)
        context_type: "rag", "direct_article", or "fallback"
    """
    # Get the article - this is the only 404 we allow
    article = db.query(NewsArticle).filter(NewsArticle.id == news_id).first()
    
    if not article:
        raise HTTPException(status_code=404, detail="News article not found")
    
    # Check if article has content
    if not article.full_content and not article.description:
        raise HTTPException(
            status_code=400, 
            detail="This article doesn't have content available yet"
        )
    
    logger.info(
        "Processing news question",
        news_id=news_id,
        question_length=len(request.question),
        rag_indexed=bool(article.rag_document_id)
    )
    
    async with create_news_rag_service() as news_rag_service:
        result = None
        context_type = "direct_article"
        
        # Strategy 1: Try RAG if article is indexed
        if article.rag_document_id:
            try:
                logger.info(f"Trying RAG query for article {news_id}")
                rag_result = await news_rag_service.query_with_context(
                    question=request.question,
                    news_id=news_id,
                    article_rag_id=article.rag_document_id
                )
                
                # Check if RAG returned a valid answer
                if rag_result.get("success") != False and rag_result.get("answer"):
                    result = rag_result
                    context_type = "rag"
                    logger.info(f"RAG query successful for article {news_id}")
                else:
                    logger.warning(f"RAG returned no answer for article {news_id}, using fallback")
                    
            except Exception as e:
                logger.warning(f"RAG query failed for article {news_id}: {e}, using fallback")
        
        # Strategy 2: Fallback to direct LLM with article content
        if not result:
            logger.info(f"Using direct LLM fallback for article {news_id}")
            result = await news_rag_service.answer_from_article_content(
                question=request.question,
                article=article,
                answer_style="detailed"
            )
            context_type = result.get("context_type", "direct_article")
    
    # Build response - we ALWAYS return a valid response, never an error
    sources = []
    for src in result.get("sources", []):
        sources.append(NewsAnswerSource(
            text=src.get("text", "")[:300] + "..." if len(src.get("text", "")) > 300 else src.get("text", ""),
            title=src.get("title", article.title),
            source=src.get("source", article.source)
        ))
    
    # If no sources, add the article as source
    if not sources:
        sources.append(NewsAnswerSource(
            text=article.quick_summary or article.summary or article.title,
            title=article.title,
            source=article.source
        ))
    
    response = NewsAskQuestionResponse(
        answer=result.get("answer", "I couldn't generate an answer. Please try rephrasing your question."),
        sources=sources,
        article_title=article.title,
        article_id=article.id,
        rag_indexed=context_type == "rag",
        context_type=context_type
    )
    
    logger.info(
        "News question answered",
        news_id=news_id,
        context_type=context_type,
        answer_length=len(response.answer)
    )
    
    return response


# Note: News fetching and processing is now handled by background cron jobs only.
# Frontend APIs are read-only for optimal performance.
