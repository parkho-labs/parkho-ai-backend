"""
Legal Assistant API (Chatbot) Endpoint

Provides /legal/ask-question endpoint for interactive Q&A on constitutional law queries.
Business-focused frontend API that uses RagClient internally.

Features:
- RAG-based responses using legal document collections
- Direct LLM mode with adaptive prompts based on user expertise
- Intent classification for personalized responses
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from typing import List

from src.api.dependencies import get_legal_user_id_required, get_law_rag_client
from src.services.rag import LawRagClient
from src.api.v1.schemas import LawChatRequest, LawChatResponse, LawSource
from src.core.database import get_db
from src.news.models.news_article import NewsArticle
from src.services.news_rag_service import create_news_rag_service
from src.services.intent_classifier import get_intent_classifier
from src.ask_assistant.services.memory_service import get_memory_service
from src.ask_assistant.models.enums import MemoryType
from sqlalchemy.orm import Session

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/ask-question", response_model=LawChatResponse)
async def legal_assistant_chat(
    request: LawChatRequest,
    user_id: str = Depends(get_legal_user_id_required),
    rag_client: LawRagClient = Depends(get_law_rag_client),
    db: Session = Depends(get_db)
) -> LawChatResponse:
    """
    Interactive Q&A chatbot for constitutional law queries.

    Endpoint: POST /api/v1/legal/ask-question

    Required Headers:
        x-user-id: User identifier

    Request Body:
        question: Legal question (10-500 characters)

    Response:
        answer: AI-generated answer
        sources: List of source chunks with article references
        total_chunks: Total number of source chunks used
    """
    try:
        logger.info("Processing legal chat request", user_id=user_id, question_length=len(request.question), enable_rag=request.enable_rag, news_context_id=request.news_context_id)

        # Handle news context using NewsRagService
        if request.news_context_id:
            # Get news article for context
            news_article = db.query(NewsArticle).filter(NewsArticle.id == request.news_context_id).first()
            if news_article:
                try:
                    # Use NewsRagService for contextual query
                    async with create_news_rag_service() as news_rag_service:
                        rag_result = await news_rag_service.query_with_context(
                            question=request.question,
                            news_id=request.news_context_id,
                            article_rag_id=news_article.rag_document_id
                        )

                    if rag_result.get("success") != False and rag_result.get("answer"):
                        # Transform response to LawChatResponse format
                        legal_sources = []
                        if rag_result.get("sources"):
                            for source in rag_result["sources"]:
                                legal_sources.append(LawSource(
                                    text=source.get("text", "")[:200] + ("..." if len(source.get("text", "")) > 200 else ""),
                                    article=f"News: {news_article.title[:50]}..."
                                ))

                        response = LawChatResponse(
                            answer=rag_result["answer"],
                            sources=legal_sources,
                            total_chunks=len(rag_result.get("sources", [])),
                            context_used="news"
                        )

                        logger.info("News context query completed", user_id=user_id, news_id=request.news_context_id)
                        return response

                except Exception as e:
                    logger.warning("News context query failed, falling back to general", error=str(e), news_id=request.news_context_id)

        if request.enable_rag:
            # RAG Mode: Use all legal content (constitution + BNS)
            all_scopes = ["constitution", "bns"]
            rag_response = await rag_client.legal_chat(user_id, request.question, all_scopes)

            if not rag_response.success:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to process legal query. Please try again."
                )

            # Transform RAG response to legal chat response format
            legal_sources = []
            if rag_response.sources:
                for source in rag_response.sources:
                    legal_sources.append(LawSource(
                        text=source.chunk_text[:200] + ("..." if len(source.chunk_text) > 200 else ""),
                        article=source.concepts[0] if source.concepts else "Constitutional Law"
                    ))

            total_chunks = len(rag_response.sources) if rag_response.sources else 0

            response = LawChatResponse(
                answer=rag_response.answer,
                sources=legal_sources,
                total_chunks=total_chunks,
                context_used="general"
            )
        else:
            # Direct LLM Mode: Use LLM with adaptive system prompt (no RAG)
            # IntentClassifier builds a dynamic prompt that adapts to user expertise
            from src.services.llm_service import LLMService
            from src.config import get_settings
            
            settings = get_settings()
            llm_service = LLMService(
                openai_api_key=settings.openai_api_key,
                anthropic_api_key=settings.anthropic_api_key,
                google_api_key=settings.google_api_key
            )
            
            # Use IntentClassifier to build adaptive system prompt
            # The classifier instructs the LLM to assess user expertise and question type,
            # then adapt the response style accordingly
            intent_classifier = get_intent_classifier()
            system_prompt = intent_classifier.build_adaptive_prompt(request.question)
            
            logger.debug(
                "Using adaptive prompt for direct LLM mode",
                user_id=user_id,
                question_preview=request.question[:50] + "..." if len(request.question) > 50 else request.question
            )
            
            user_prompt = request.question
            
            # Generate answer using LLM with adaptive prompt
            answer = await llm_service.generate_with_fallback(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.3,
                max_tokens=1500  # Increased to accommodate richer responses
            )
            
            response = LawChatResponse(
                answer=answer,
                sources=[],  # No sources in direct LLM mode
                total_chunks=0,
                context_used="general"
            )

        logger.info(
            "Legal chat completed successfully",
            user_id=user_id,
            answer_length=len(response.answer),
            sources_count=len(response.sources),
            total_chunks=response.total_chunks,
            mode="RAG" if request.enable_rag else "Direct LLM"
        )

        # Store interaction in memory
        try:
            memory_service = get_memory_service()
            memory_content = f"User asked: {request.question}\n\nAnswer: {response.answer}"
            memory_metadata = {
                "enable_rag": request.enable_rag,
                "sources_count": len(response.sources),
                "total_chunks": response.total_chunks,
                "context_used": response.context_used,
                "mode": "RAG" if request.enable_rag else "Direct LLM"
            }
            if request.news_context_id:
                memory_metadata["news_context_id"] = request.news_context_id

            memory_service.add_interaction_memory(
                user_id=user_id,
                interaction_type=MemoryType.GENERAL_CHAT,
                content=memory_content,
                metadata=memory_metadata
            )
        except Exception as e:
            # Don't fail the request if memory storage fails
            logger.warning("Failed to store memory for legal chat", error=str(e), user_id=user_id)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Legal chat failed", user_id=user_id, error=str(e), exc_info=e)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing your legal query. Please try again."
        )