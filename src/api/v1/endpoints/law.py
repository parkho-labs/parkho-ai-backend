"""
Legal Assistant API (Chatbot) Endpoint

Provides /law/chat endpoint for interactive Q&A on constitutional law queries.
Matches the specification in BACKEND_API_INTEGRATION.md.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from typing import List

from src.api.dependencies import get_legal_user_id_required, get_rag_client
from src.services.rag_client import RagClient
from src.api.v1.schemas import LawChatRequest, LawChatResponse, LawSource

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/chat", response_model=LawChatResponse)
async def legal_assistant_chat(
    request: LawChatRequest,
    user_id: str = Depends(get_legal_user_id_required),
    rag_client: RagClient = Depends(get_rag_client)
) -> LawChatResponse:
    """
    Interactive Q&A chatbot for constitutional law queries.

    Endpoint: POST /api/v1/law/chat

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
        logger.info("Processing legal chat request", user_id=user_id, question_length=len(request.question))

        # Use RAG client to query legal documents
        # Default to constitution-golden-source collection for legal queries
        filters = {
            "collection_ids": ["constitution-golden-source"]
        }

        # Build RAG query request
        from src.services.rag_client import RagQueryRequest
        rag_request = RagQueryRequest(
            query=request.question,
            filters=filters,
            top_k=5,
            include_sources=True
        )

        # Query the RAG engine
        rag_response = await rag_client.query_content(user_id, rag_request)

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
            total_chunks=total_chunks
        )

        logger.info(
            "Legal chat completed successfully",
            user_id=user_id,
            answer_length=len(response.answer),
            sources_count=len(response.sources),
            total_chunks=total_chunks
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Legal chat failed", user_id=user_id, error=str(e), exc_info=e)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing your legal query. Please try again."
        )