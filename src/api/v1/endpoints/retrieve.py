"""
Legal Content Retrieval Endpoint

Provides /retrieve endpoint for direct constitutional content retrieval.
Matches the specification in BACKEND_API_INTEGRATION.md.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List

from src.api.dependencies import get_legal_user_id_required, get_rag_client
from src.services.rag_client import RagClient
from src.api.v1.schemas import LegalRetrieveRequest, LegalRetrieveResponse, LegalChunk

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("", response_model=LegalRetrieveResponse)
async def retrieve_constitutional_content(
    request: LegalRetrieveRequest = Body(...),
    rag_client: RagClient = Depends(get_rag_client)
) -> LegalRetrieveResponse:
    """
    Direct constitutional content retrieval for research.

    Endpoint: POST /api/v1/retrieve

    Required Headers:
        x-user-id: User identifier

    Request Body:
        query: Search query string
        user_id: User identifier
        collection_ids: List of collection IDs to search
        top_k: Maximum number of results (default 10, max 20)

    Response:
        success: Boolean success status
        results: List of matching content chunks with relevance scores
    """
    try:
        logger.info(
            "Processing legal content retrieval",
            user_id=request.user_id,
            query=request.query[:50] + "..." if len(request.query) > 50 else request.query,
            collection_ids=request.collection_ids,
            top_k=request.top_k
        )

        # Validate collection IDs
        if not request.collection_ids:
            raise HTTPException(
                status_code=400,
                detail="At least one collection_id is required"
            )

        # Build RAG retrieve request
        from src.services.rag_client import RagQueryRequest
        rag_request = RagQueryRequest(
            query=request.query,
            filters={"collection_ids": request.collection_ids},
            top_k=request.top_k,
            include_sources=True
        )

        # Retrieve content from RAG engine
        rag_response = await rag_client.retrieve_content(request.user_id, rag_request)

        if not rag_response.success:
            logger.warning("RAG retrieval failed", user_id=request.user_id, query=request.query)
            return LegalRetrieveResponse(
                success=False,
                results=[]
            )

        # Transform RAG results to legal format
        legal_chunks = []
        if rag_response.results:
            for chunk in rag_response.results:
                legal_chunk = LegalChunk(
                    chunk_id=chunk.chunk_id,
                    chunk_text=chunk.chunk_text,
                    relevance_score=chunk.relevance_score,
                    file_id=chunk.file_id,
                    page_number=chunk.page_number,
                    concepts=chunk.concepts
                )
                legal_chunks.append(legal_chunk)

        response = LegalRetrieveResponse(
            success=True,
            results=legal_chunks
        )

        logger.info(
            "Legal content retrieval completed",
            user_id=request.user_id,
            results_count=len(legal_chunks),
            avg_relevance=sum(c.relevance_score for c in legal_chunks) / len(legal_chunks) if legal_chunks else 0
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Legal content retrieval failed", user_id=request.user_id, error=str(e), exc_info=e)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while retrieving legal content. Please try again."
        )