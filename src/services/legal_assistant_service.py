"""
Legal Assistant Service

Business logic wrapper for legal document operations.
Provides high-level methods for legal chat, question generation, and content retrieval.
"""

import structlog
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..services.rag_client import RagClient, RagQueryRequest
from ..services.rag_question_generator_service import RagQuestionGeneratorService
from ..api.v1.schemas import (
    LawChatRequest, LawChatResponse, LawSource,
    LegalQuestionRequest, LegalQuestionResponse,
    LegalRetrieveRequest, LegalRetrieveResponse
)

logger = structlog.get_logger(__name__)


class LegalAssistantService:
    """
    Service for legal document operations.

    Wraps the existing RAG infrastructure to provide legal-specific functionality:
    - Constitutional law queries via chat interface
    - Legal exam question generation
    - Direct legal content retrieval

    This service acts as an adapter between legal API endpoints and the
    underlying RAG services, handling legal-specific transformations and defaults.
    """

    def __init__(self, rag_client: RagClient):
        self.rag_client = rag_client
        self.rag_question_service = RagQuestionGeneratorService.get_instance()
        self.default_collections = ["constitution-golden-source"]

    async def process_legal_chat(
        self,
        request: LawChatRequest,
        user_id: str,
        collections: Optional[List[str]] = None
    ) -> LawChatResponse:
        """
        Process legal assistant chat query.

        Args:
            request: Legal chat request with question
            user_id: User identifier
            collections: Optional list of collections to search (defaults to constitution)

        Returns:
            Legal chat response with answer, sources, and chunk count
        """
        logger.info("Processing legal chat", user_id=user_id, question_length=len(request.question))

        # Use default collections if not specified
        target_collections = collections or self.default_collections

        # Build RAG query
        rag_request = RagQueryRequest(
            query=request.question,
            filters={"collection_ids": target_collections},
            top_k=5,
            include_sources=True
        )

        # Query RAG engine
        rag_response = await self.rag_client.query_content(user_id, rag_request)

        if not rag_response.success:
            raise ValueError("RAG query failed")

        # Transform to legal format
        legal_sources = []
        if rag_response.sources:
            for source in rag_response.sources:
                # Extract article reference from concepts or use fallback
                article_ref = "Constitutional Law"
                if source.concepts:
                    # Look for article-like concepts
                    for concept in source.concepts:
                        if concept.lower().startswith("article") or concept.lower().startswith("art"):
                            article_ref = concept
                            break
                    else:
                        article_ref = source.concepts[0]

                legal_sources.append(LawSource(
                    text=source.chunk_text[:200] + ("..." if len(source.chunk_text) > 200 else ""),
                    article=article_ref
                ))

        return LawChatResponse(
            answer=rag_response.answer,
            sources=legal_sources,
            total_chunks=len(rag_response.sources) if rag_response.sources else 0
        )

    async def generate_legal_questions(
        self,
        request: LegalQuestionRequest,
        collections: Optional[List[str]] = None
    ) -> LegalQuestionResponse:
        """
        Generate legal exam questions.

        Args:
            request: Legal question generation request
            collections: Optional collections to use (defaults to constitution)

        Returns:
            Legal question response with generated questions and stats
        """
        logger.info("Generating legal questions", question_specs=len(request.questions))

        # Use default collections if not specified in filters
        target_collections = collections or self.default_collections

        # Transform legal request to RAG format
        rag_questions = []
        total_requested = 0

        type_mapping = {
            "assertion_reasoning": "assertion_reasoning",
            "match_following": "match_following",
            "comprehension": "comprehension"
        }

        for spec in request.questions:
            total_requested += spec.count

            # Apply default collections if no filters provided
            filters = spec.filters or {"collection_ids": target_collections}
            if "collection_ids" not in filters:
                filters["collection_ids"] = target_collections

            rag_questions.append({
                "type": type_mapping[spec.type.value],
                "difficulty": spec.difficulty.value,
                "count": spec.count,
                "filters": filters
            })

        # Build RAG request
        from ..api.v1.schemas import RagQuestionGenerationRequest
        rag_request = RagQuestionGenerationRequest(
            questions=rag_questions,
            context={"subject": request.context.subject if request.context else "Constitutional Law"}
        )

        # Generate questions
        generation_start = datetime.now()
        rag_response = await self.rag_question_service.generate_questions(rag_request)
        generation_time = (datetime.now() - generation_start).total_seconds()

        # Transform response to legal format
        # (This would include the full transformation logic from questions.py)
        # For now, we'll return the structured response as expected by the API

        return LegalQuestionResponse(
            success=rag_response.success,
            total_generated=rag_response.total_generated,
            questions=rag_response.questions,
            generation_stats=rag_response.generation_stats,
            errors=rag_response.errors,
            warnings=rag_response.warnings
        )

    async def retrieve_legal_content(
        self,
        request: LegalRetrieveRequest
    ) -> LegalRetrieveResponse:
        """
        Retrieve legal content chunks.

        Args:
            request: Legal retrieval request

        Returns:
            Legal retrieval response with matching chunks
        """
        logger.info(
            "Retrieving legal content",
            user_id=request.user_id,
            collections=request.collection_ids,
            top_k=request.top_k
        )

        # Build RAG retrieve request
        rag_request = RagQueryRequest(
            query=request.query,
            filters={"collection_ids": request.collection_ids},
            top_k=request.top_k,
            include_sources=True
        )

        # Retrieve from RAG engine
        rag_response = await self.rag_client.retrieve_content(request.user_id, rag_request)

        # Transform to legal format
        from ..api.v1.schemas import LegalChunk
        legal_chunks = []

        if rag_response.success and rag_response.results:
            for chunk in rag_response.results:
                legal_chunks.append(LegalChunk(
                    chunk_id=chunk.chunk_id,
                    chunk_text=chunk.chunk_text,
                    relevance_score=chunk.relevance_score,
                    file_id=chunk.file_id,
                    page_number=chunk.page_number,
                    concepts=chunk.concepts
                ))

        return LegalRetrieveResponse(
            success=rag_response.success,
            results=legal_chunks
        )

    def get_available_collections(self) -> List[str]:
        """Get list of available legal document collections."""
        return [
            "constitution-golden-source",
            # Future collections as they become available:
            # "bnc-act", "ipc-sections", "evidence-act"
        ]

    def get_supported_question_types(self) -> List[str]:
        """Get list of supported legal question types."""
        return ["assertion_reasoning", "match_following", "comprehension"]

    def get_supported_difficulties(self) -> List[str]:
        """Get list of supported difficulty levels."""
        return ["easy", "moderate", "difficult"]


# Singleton instance for dependency injection
_legal_service_instance: Optional[LegalAssistantService] = None


def get_legal_assistant_service(rag_client: RagClient) -> LegalAssistantService:
    """Get or create legal assistant service instance."""
    global _legal_service_instance
    if _legal_service_instance is None:
        _legal_service_instance = LegalAssistantService(rag_client)
    return _legal_service_instance