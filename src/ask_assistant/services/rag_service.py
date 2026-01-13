"""RAG Service for Ask Assistant - Knowledge Base Integration"""

import structlog
from typing import Optional, List, Dict, Any
import httpx

from src.config import get_settings

logger = structlog.get_logger(__name__)

# Singleton instance
_rag_instance: Optional["RAGService"] = None


class RAGService:
    """
    RAG Service for querying knowledge base.
    Integrates with the existing RAG engine for legal documents.
    """
    
    # System collections (legal documents)
    SYSTEM_COLLECTIONS = ["constitution", "bns"]
    
    def __init__(self):
        """Initialize RAG service"""
        self.settings = get_settings()
        self.base_url = self.settings.rag_engine_url
        self.timeout = self.settings.rag_questions_timeout
        logger.info("RAG service initialized", base_url=self.base_url)
    
    async def retrieve_context(
        self,
        query: str,
        user_id: str,
        collection_ids: Optional[List[str]] = None,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Retrieve relevant context from knowledge base.
        
        Args:
            query: Search query
            user_id: User identifier
            collection_ids: Specific collections to search (None = all)
            top_k: Number of results to return
        
        Returns:
            Dict with success status and results
        """
        try:
            # Determine collections to query
            if collection_ids is None:
                # Query all system collections
                target_collections = self.SYSTEM_COLLECTIONS
            else:
                target_collections = collection_ids
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {
                    "query": query,
                    "user_id": user_id,
                    "collection_ids": target_collections,
                    "top_k": top_k
                }
                
                response = await client.post(
                    f"{self.base_url}/law/retrieve",
                    headers={"x-user-id": user_id},
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                
                # Format results
                results = []
                if data.get("success") and data.get("results"):
                    for result in data["results"]:
                        results.append({
                            "text": result.get("chunk_text", ""),
                            "title": result.get("concepts", ["Legal Document"])[0] if result.get("concepts") else "Legal Document",
                            "article": result.get("concepts", [None])[0],
                            "relevance_score": result.get("relevance_score", 0.0),
                            "collection_id": result.get("collection_id", "")
                        })
                
                logger.debug(
                    "Retrieved RAG context",
                    query_length=len(query),
                    results_count=len(results)
                )
                
                return {
                    "success": True,
                    "results": results
                }
                
        except httpx.HTTPError as e:
            logger.error("RAG retrieve HTTP error", error=str(e))
            return {"success": False, "results": [], "error": str(e)}
        except Exception as e:
            logger.error("RAG retrieve failed", error=str(e))
            return {"success": False, "results": [], "error": str(e)}
    
    async def query_with_answer(
        self,
        question: str,
        user_id: str,
        scope: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Query RAG engine and get an answer with sources.
        
        Args:
            question: User's question
            user_id: User identifier
            scope: Legal document scope (constitution, bns)
        
        Returns:
            Dict with answer and sources
        """
        try:
            if scope is None:
                scope = self.SYSTEM_COLLECTIONS
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {
                    "question": question,
                    "scope": scope
                }
                
                response = await client.post(
                    f"{self.base_url}/law/chat",
                    headers={"x-user-id": user_id},
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                
                # Format sources
                sources = []
                if data.get("sources"):
                    for source in data["sources"]:
                        sources.append({
                            "text": source.get("text", ""),
                            "title": source.get("article", "Legal Document"),
                            "article": source.get("article")
                        })
                
                return {
                    "success": True,
                    "answer": data.get("answer", ""),
                    "sources": sources
                }
                
        except httpx.HTTPError as e:
            logger.error("RAG query HTTP error", error=str(e))
            return {"success": False, "answer": "", "sources": [], "error": str(e)}
        except Exception as e:
            logger.error("RAG query failed", error=str(e))
            return {"success": False, "answer": "", "sources": [], "error": str(e)}
    
    def format_context_for_prompt(
        self,
        results: List[Dict[str, Any]],
        max_length: int = 3000
    ) -> str:
        """
        Format RAG results into context string for the agent prompt.
        
        Args:
            results: RAG search results
            max_length: Maximum total context length
        
        Returns:
            Formatted context string
        """
        if not results:
            return ""
        
        context_parts = ["## Relevant Legal Information (Knowledge Base):\n"]
        current_length = len(context_parts[0])
        
        for i, result in enumerate(results, 1):
            text = result.get("text", "")
            title = result.get("title", "Legal Document")
            article = result.get("article", "")
            
            # Format entry
            if article:
                entry = f"### {article}\n{text}\n"
            else:
                entry = f"### {title}\n{text}\n"
            
            # Check length limit
            if current_length + len(entry) > max_length:
                break
            
            context_parts.append(entry)
            current_length += len(entry)
        
        return "\n".join(context_parts)
    
    def get_available_collections(self) -> List[Dict[str, str]]:
        """Get list of available system collections"""
        return [
            {"id": "constitution", "name": "Constitution of India"},
            {"id": "bns", "name": "Bharatiya Nyaya Sanhita (BNS)"}
        ]


def get_rag_service() -> RAGService:
    """Get or create the RAGService singleton"""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = RAGService()
    return _rag_instance
