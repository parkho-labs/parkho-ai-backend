from typing import List, Dict, Any, Optional
import httpx
from src.config import get_settings
from src.api.v1.constants import RAGEndpoint
from src.api.v1.schemas import (
    BatchLinkResponse,
    BatchItemResult,
    StatusCheckResponse,
    StatusItemResponse,
    RetrieveResponse,
    SourceChunk,
    DeleteCollectionResponse,
    DeleteFileResponse
)

class RagService:
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.rag_engine_url
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def batch_link_content(self, items: List[Dict[str, Any]], user_id: str) -> BatchLinkResponse:
        try:
            headers = {"x-user-id": user_id}
            response = await self.client.post(
                f"{self.base_url}{RAGEndpoint.LINK_CONTENT}",
                json={"items": items},
                headers=headers
            )
            response.raise_for_status()
            result = response.json()
            
            results = [
                BatchItemResult(
                    file_id=r.get("file_id", ""),
                    status=r.get("status", "failed"),
                    error=r.get("error")
                )
                for r in result.get("results", [])
            ]
            
            return BatchLinkResponse(
                message=result.get("message", "Batch processing complete"),
                batch_id=result.get("batch_id", "sync_job"),
                results=results
            )
        except Exception as e:
            return BatchLinkResponse(
                message="Batch processing failed",
                batch_id="sync_job",
                results=[BatchItemResult(file_id=item.get("file_id", ""), status="failed", error=str(e)) for item in items]
            )

    async def check_indexing_status(self, file_ids: List[str], user_id: str) -> StatusCheckResponse:
        try:
            headers = {"x-user-id": user_id}
            response = await self.client.post(
                f"{self.base_url}{RAGEndpoint.STATUS}",
                json={"file_ids": file_ids},
                headers=headers
            )
            response.raise_for_status()
            result = response.json()
            
            items = [
                StatusItemResponse(
                    file_id=i.get("file_id"),
                    name=i.get("name"),
                    source=i.get("source"),
                    status=i.get("status", "UNKNOWN"),
                    error=i.get("error")
                )
                for i in result.get("results", [])
            ]
            return StatusCheckResponse(message=result.get("message", ""), results=items)
        except Exception as e:
            return StatusCheckResponse(message=f"Failed: {str(e)}", results=[])

    async def query_content(
        self,
        query: str,
        user_id: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
        include_sources: bool = False
    ) -> QueryResponse:
        try:
            payload = {
                "query": query,
                "top_k": top_k,
                "include_sources": include_sources
            }
            if filters:
                payload["filters"] = filters

            headers = {"x-user-id": user_id}
            response = await self.client.post(
                f"{self.base_url}{RAGEndpoint.QUERY}",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            result = response.json()
            
            sources = None
            if include_sources and result.get("sources"):
                sources = [
                    SourceChunk(
                        chunk_id=c.get("chunk_id", "unknown"),
                        chunk_text=c.get("chunk_text", ""),
                        relevance_score=c.get("relevance_score", 0.0),
                        file_id=c.get("file_id", ""),
                        page_number=c.get("page_number"),
                        timestamp=c.get("timestamp"),
                        concepts=c.get("concepts", [])
                    )
                    for c in result.get("sources", [])
                ]

            return QueryResponse(
                success=result.get("success", False),
                answer=result.get("answer", ""),
                sources=sources
            )
        except Exception as e:
            return QueryResponse(success=False, answer="Error querying RAG", sources=[])

    async def retrieve_content(
        self,
        query: str,
        user_id: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
        include_graph_context: bool = True
    ) -> RetrieveResponse:
        try:
            payload = {
                "query": query,
                "top_k": top_k,
                "include_graph_context": include_graph_context
            }
            if filters:
                payload["filters"] = filters

            headers = {"x-user-id": user_id}
            response = await self.client.post(
                f"{self.base_url}{RAGEndpoint.RETRIEVE}",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            result = response.json()
            
            chunks = [
            chunks = [
                SourceChunk(
                    chunk_id=c.get("chunk_id", "unknown"),
                    chunk_text=c.get("chunk_text", ""),
                    relevance_score=c.get("relevance_score", 0.0),
                    file_id=c.get("file_id", ""),
                    page_number=c.get("page_number"),
                    timestamp=c.get("timestamp"),
                    concepts=c.get("concepts", [])
                )
                for c in result.get("results", [])
            ]
            
            return RetrieveResponse(
                success=result.get("success", False),
                results=chunks
            )
        except Exception:
            return RetrieveResponse(success=False, results=[])

    async def delete_collection(self, collection_id: str, user_id: str) -> DeleteCollectionResponse:
        try:
            headers = {"x-user-id": user_id}
            payload = {"collection_id": collection_id}
            response = await self.client.delete(
                f"{self.base_url}{RAGEndpoint.DELETE_COLLECTION}",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            result = response.json()
            return DeleteCollectionResponse(message=result.get("message", "Deleted"))
        except Exception as e:
            return DeleteCollectionResponse(message=f"Failed to delete collection: {str(e)}")

    async def delete_files(self, file_ids: List[str], user_id: str) -> DeleteFileResponse:
        try:
            headers = {"x-user-id": user_id}
            response = await self.client.request(
                "DELETE",
                f"{self.base_url}{RAGEndpoint.DELETE_FILE}",
                json={"file_ids": file_ids},
                headers=headers
            )
            response.raise_for_status()
            result = response.json()
            return DeleteFileResponse(message=result.get("message", "Deleted"))
        except Exception as e:
            return DeleteFileResponse(message=f"Failed to delete files: {str(e)}")

    # Keeping factory for strict compat
    # but removing register_user unless needed? 
    # Current firebase.py USES register_user. Doc deleted USER_REGISTER?
    # Doc says: "1. Ingestion, 2. Retrieval, 3. Management".
    # User Registration is not in the list.
    # User said "Update files".
    # If I remove register_user, firebase.py breaks.
    # I will KEEP register_user for now as it's likely an auth hook not part of main RAG API doc surface but still needed.
    # Or I should comment it out if strict.
    # I will keep it but maybe it's "undocumented" internal API.
    async def register_user(self, user_id: str, email: str = None, name: str = None) -> bool:
        try:
            payload = {
                "user_id": user_id,
                "email": email or f"{user_id}@example.com",
                "name": name or f"User {user_id}"
            }
            # RAG Endpoint for register might still exist in constants even if not in doc md
            response = await self.client.post(f"{self.base_url}{RAGEndpoint.USER_REGISTER}", json=payload)
            response.raise_for_status()
            result = response.json()
            return result.get("status") == "SUCCESS"
        except Exception:
            return False

_rag_service = None

def get_rag_service() -> RagService:
    global _rag_service
    if _rag_service is None:
        _rag_service = RagService()
    return _rag_service
