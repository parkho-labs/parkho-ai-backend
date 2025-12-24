from typing import Dict, List, Optional, Any
from pydantic import BaseModel
import httpx
import logging
from ...config import get_settings
from ...exceptions import ParkhoError

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

class BaseRagClient:
    """Base class for RAG Engine communication with shared infrastructure."""
    
    def __init__(self, base_url: Optional[str] = None):
        settings = get_settings()
        self.base_url = base_url or settings.rag_engine_url
        self.client = httpx.AsyncClient(timeout=120.0)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"🚀 {self.__class__.__name__} initialized with base_url: {self.base_url}")

    def _get_headers(self, user_id: str) -> Dict[str, str]:
        """Get headers with required x-user-id"""
        return {
            "Content-Type": "application/json",
            "x-user-id": user_id
        }

    async def close(self):
        """Close the httpx client"""
        await self.client.aclose()
