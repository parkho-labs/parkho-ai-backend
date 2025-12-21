"""
Unified RAG Client Service

Single source of truth for all RAG Engine API communication.
Implements actual RAG engine endpoints with Pydantic response models.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
import httpx
import logging
from ..config import get_settings
from ..exceptions import ParkhoError


class RagChunk(BaseModel):
    """RAG chunk/source information"""
    chunk_id: str
    chunk_text: str
    relevance_score: float
    file_id: str
    page_number: Optional[int] = None
    timestamp: Optional[str] = None
    concepts: List[str] = []


class RagQueryResponse(BaseModel):
    """Response from RAG query endpoint"""
    success: bool
    answer: str
    sources: List[RagChunk] = []


class RagRetrieveResponse(BaseModel):
    """Response from RAG retrieve endpoint"""
    success: bool
    results: List[RagChunk] = []


class RagLinkItem(BaseModel):
    """Individual item linking result"""
    file_id: str
    status: str
    error: Optional[str] = None


class RagLinkResponse(BaseModel):
    """Response from RAG link-content endpoint"""
    message: str
    batch_id: str
    results: List[RagLinkItem]


class RagStatusItem(BaseModel):
    """Individual file status result"""
    file_id: str
    status: str
    error: Optional[str] = None


class RagStatusResponse(BaseModel):
    """Response from RAG status check endpoint"""
    message: str
    results: List[RagStatusItem]


class RagDeleteResponse(BaseModel):
    """Response from RAG delete operations"""
    message: str


class RagLinkRequest(BaseModel):
    """Request payload for linking content"""
    file_id: str
    type: str  # "file", "youtube", or "web"
    gcs_url: Optional[str] = None
    url: Optional[str] = None
    collection_id: Optional[str] = None


class RagQueryRequest(BaseModel):
    """Request payload for querying"""
    query: str
    top_k: int = 5
    include_sources: bool = True
    filters: Optional[Dict[str, Any]] = None


class RagClient:
    """
    Unified RAG Client - Single service for all RAG Engine communication.
    Implements actual RAG engine API endpoints with proper error handling.
    """

    _instance: Optional['RagClient'] = None
    _lock = None

    def __init__(self, base_url: Optional[str] = None):
        """Initialize RAG client with base URL and httpx client"""
        settings = get_settings()
        self.base_url = base_url or settings.rag_engine_url
        self.client = httpx.AsyncClient(timeout=120.0)  # Increased from 30s to 120s for question generation
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"🚀 RAG Client initialized with base_url: {self.base_url}")

    @classmethod
    def get_instance(cls) -> 'RagClient':
        """Get singleton instance of RagClient"""
        import threading
        if cls._lock is None:
            cls._lock = threading.Lock()

        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _get_headers(self, user_id: str) -> Dict[str, str]:
        """Get headers with required x-user-id"""
        return {
            "Content-Type": "application/json",
            "x-user-id": user_id
        }

    async def link_content(self, user_id: str, items: List[RagLinkRequest]) -> RagLinkResponse:
        """
        Link content to RAG engine for processing and indexing.

        Maps to: POST /link-content
        """
        try:
            payload = {"items": [item.dict() for item in items]}

            response = await self.client.post(
                f"{self.base_url}/link-content",
                headers=self._get_headers(user_id),
                json=payload
            )

            if response.status_code == 207:  # Multi-status success
                data = response.json()
                return RagLinkResponse(**data)
            else:
                response.raise_for_status()

        except httpx.HTTPError as e:
            # Check if this might be a circular call to ourselves
            if "localhost" in str(self.base_url) or "127.0.0.1" in str(self.base_url):
                 self.logger.error(f"RAG link_content failed. Base URL is {self.base_url}. Ensure this is NOT the backend's own port (circular call). Original error: {e}")
            else:
                 self.logger.error(f"RAG link_content failed: {e}")
            raise ParkhoError(f"Failed to link content to RAG engine: {e}")
        except Exception as e:
            self.logger.error(f"RAG link_content unexpected error: {e}")
            raise ParkhoError(f"Unexpected error linking content: {e}")

    async def check_indexing_status(self, user_id: str, file_ids: List[str]) -> RagStatusResponse:
        """
        Check the indexing status of files in RAG engine.

        Maps to: POST /collection/status
        """
        try:
            payload = {"file_ids": file_ids}

            response = await self.client.post(
                f"{self.base_url}/collection/status",
                headers=self._get_headers(user_id),
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            return RagStatusResponse(**data)

        except httpx.HTTPError as e:
            self.logger.error(f"RAG status check failed: {e}")
            raise ParkhoError(f"Failed to check indexing status: {e}")
        except Exception as e:
            self.logger.error(f"RAG status check unexpected error: {e}")
            raise ParkhoError(f"Unexpected error checking status: {e}")

    async def query_content(self, user_id: str, request: RagQueryRequest) -> RagQueryResponse:
        """
        Query RAG engine for answers to questions.

        Maps to: POST /query
        """
        try:
            response = await self.client.post(
                f"{self.base_url}/query",
                headers=self._get_headers(user_id),
                json=request.dict()
            )
            response.raise_for_status()
            data = response.json()
            return RagQueryResponse(**data)

        except httpx.HTTPError as e:
            self.logger.error(f"RAG query failed: {e}")
            raise ParkhoError(f"Failed to query RAG engine: {e}")
        except Exception as e:
            self.logger.error(f"RAG query unexpected error: {e}")
            raise ParkhoError(f"Unexpected error querying content: {e}")

    async def retrieve_content(self, user_id: str, request: RagQueryRequest) -> RagRetrieveResponse:
        """
        Retrieve raw chunks/context from RAG engine.

        Maps to: POST /retrieve
        """
        try:
            response = await self.client.post(
                f"{self.base_url}/retrieve",
                headers=self._get_headers(user_id),
                json=request.dict()
            )
            response.raise_for_status()
            data = response.json()
            return RagRetrieveResponse(**data)

        except httpx.HTTPError as e:
            # Check if this might be a circular call to ourselves
            if "localhost" in str(self.base_url) or "127.0.0.1" in str(self.base_url):
                 self.logger.error(f"RAG link_content failed. Base URL is {self.base_url}. Ensure this is NOT the backend's own port (circular call). Original error: {e}")
            else:
                 self.logger.error(f"RAG link_content failed: {e}")
            raise ParkhoError(f"Failed to link content to RAG engine: {e}")
        except Exception as e:
            self.logger.error(f"RAG retrieve unexpected error: {e}")
            raise ParkhoError(f"Unexpected error retrieving content: {e}")

    async def delete_files(self, user_id: str, file_ids: List[str]) -> RagDeleteResponse:
        """
        Delete files from RAG engine index.

        Maps to: DELETE /delete/file
        """
        try:
            payload = {"file_ids": file_ids}

            response = await self.client.request(
                "DELETE",
                f"{self.base_url}/delete/file",
                headers=self._get_headers(user_id),
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            return RagDeleteResponse(**data)

        except httpx.HTTPError as e:
            self.logger.error(f"RAG delete files failed: {e}")
            raise ParkhoError(f"Failed to delete files from RAG engine: {e}")
        except Exception as e:
            self.logger.error(f"RAG delete files unexpected error: {e}")
            raise ParkhoError(f"Unexpected error deleting files: {e}")

    async def delete_collection(self, user_id: str, collection_id: str) -> RagDeleteResponse:
        """
        Delete a collection from RAG engine.

        Maps to: DELETE /delete/collection
        """
        try:
            payload = {"collection_id": collection_id}

            response = await self.client.request(
                "DELETE",
                f"{self.base_url}/delete/collection",
                headers=self._get_headers(user_id),
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            return RagDeleteResponse(**data)

        except httpx.HTTPError as e:
            msg = f"RAG delete collection failed: {e}"
            if any(host in str(self.base_url) for host in ["localhost", "127.0.0.1"]):
                msg += f". Possible circular call to {self.base_url}. Check RAG_ENGINE_URL configuration."
            self.logger.error(msg)
            raise ParkhoError(msg)
        except Exception as e:
            self.logger.error(f"RAG delete collection unexpected error: {e}")
            raise ParkhoError(f"Unexpected error deleting collection: {e}")

    async def close(self):
        """Close the httpx client"""
        await self.client.aclose()

    # =============================================================================
    # LEGAL-SPECIFIC RAG ENGINE METHODS
    # =============================================================================

    async def legal_chat(self, user_id: str, question: str) -> RagQueryResponse:
        """
        Legal assistant chat via RAG engine.

        Maps to: POST /law/chat
        """
        try:
            payload = {"question": question}
            url = f"{self.base_url}/law/chat"
            
            self.logger.info(f"🔍 RAG Engine Request - URL: {url}, User: {user_id}, Question length: {len(question)}")

            response = await self.client.post(
                url,
                headers=self._get_headers(user_id),
                json=payload
            )
            
            self.logger.info(f"📥 RAG Engine Response - Status: {response.status_code}, URL: {url}")
            
            # Log raw response for debugging
            raw_response = response.text
            self.logger.info(f"📄 RAG Engine Raw Response: {raw_response[:500]}")  # First 500 chars
            
            response.raise_for_status()
            data = response.json()
            
            self.logger.info(f"📊 RAG Engine Data - Answer: '{data.get('answer', '')}', Answer length: {len(data.get('answer', ''))}, Sources: {len(data.get('sources', []))}")
            self.logger.info(f"🔍 RAG Engine Sources Detail: {data.get('sources', [])[:2]}")  # First 2 sources

            # Transform RAG response to our format
            sources = []
            if data.get("sources"):
                for source in data["sources"]:
                    sources.append(RagChunk(
                        chunk_id=f"legal_{hash(source.get('text', ''))}",
                        chunk_text=source.get("text", ""),
                        relevance_score=1.0,  # Legal sources don't have scores
                        file_id="legal_document",
                        concepts=[source.get("article", "Constitutional Law")]
                    ))

            return RagQueryResponse(
                success=True,
                answer=data.get("answer", ""),
                sources=sources
            )

        except httpx.HTTPError as e:
            self.logger.error(f"❌ Legal chat HTTP error - URL: {self.base_url}/law/chat, Error: {e}, Status: {getattr(e.response, 'status_code', 'N/A')}")
            raise ParkhoError(f"Failed to get legal chat response: {e}")
        except Exception as e:
            self.logger.error(f"❌ Legal chat unexpected error - URL: {self.base_url}/law/chat, Error: {e}", exc_info=True)
            raise ParkhoError(f"Unexpected error in legal chat: {e}")

    async def legal_retrieve(self, user_id: str, query: str, collection_ids: List[str], top_k: int = 10) -> RagRetrieveResponse:
        """
        Legal content retrieval via RAG engine.

        Maps to: POST /law/retrieve
        """
        try:
            payload = {
                "query": query,
                "user_id": user_id,
                "collection_ids": collection_ids,
                "top_k": top_k
            }

            response = await self.client.post(
                f"{self.base_url}/law/retrieve",
                headers=self._get_headers(user_id),
                json=payload
            )
            response.raise_for_status()
            data = response.json()

            # Transform RAG response to our format
            chunks = []
            if data.get("success") and data.get("results"):
                for result in data["results"]:
                    chunks.append(RagChunk(
                        chunk_id=result.get("chunk_id", ""),
                        chunk_text=result.get("chunk_text", ""),
                        relevance_score=result.get("relevance_score", 0.0),
                        file_id=result.get("file_id", ""),
                        page_number=result.get("page_number"),
                        concepts=result.get("concepts", [])
                    ))

            return RagRetrieveResponse(
                success=data.get("success", False),
                results=chunks
            )

        except httpx.HTTPError as e:
            self.logger.error(f"Legal retrieve failed: {e}")
            raise ParkhoError(f"Failed to retrieve legal content: {e}")
        except Exception as e:
            self.logger.error(f"Legal retrieve unexpected error: {e}")
            raise ParkhoError(f"Unexpected error in legal retrieve: {e}")

    async def legal_questions(self, user_id: str, questions_spec: List[Dict], context: Dict = None) -> Dict:
        """
        Legal question generation via RAG engine.

        Maps to: POST /law/questions
        """
        try:
            payload = {
                "questions": questions_spec,
                "context": context or {}
            }

            response = await self.client.post(
                f"{self.base_url}/law/questions",
                headers=self._get_headers(user_id),
                json=payload
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPError as e:
            self.logger.error(f"Legal questions failed: {e}")
            raise ParkhoError(f"Failed to generate legal questions: {e}")
        except Exception as e:
            self.logger.error(f"Legal questions unexpected error: {e}")
            raise ParkhoError(f"Unexpected error in legal questions: {e}")


# Global singleton instance
rag_client = RagClient.get_instance()