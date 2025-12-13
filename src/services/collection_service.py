import structlog
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from ..repositories.collection_repository import CollectionRepository
from ..services.rag_integration_service import get_rag_service, RAGIntegrationService
from ..models.collection import Collection

logger = structlog.get_logger(__name__)

class CollectionService:
    def __init__(self, db: Session):
        self.repository = CollectionRepository(db)
        self.rag_service = get_rag_service()

    async def create_collection(self, user_id: str, name: str, description: str = None) -> Collection:
        return self.repository.create(user_id, name, description)

    async def list_collections(self, user_id: str) -> List[Collection]:
        return self.repository.get_by_user(user_id)
    
    async def get_collection(self, collection_id: str) -> Optional[Collection]:
        return self.repository.get_by_id(collection_id)

    async def delete_collection(self, user_id: str, collection_id: str) -> bool:
        collection = self.repository.get_by_id(collection_id)
        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found")
        if collection.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this collection")
        
        return self.repository.delete(collection_id)

    async def link_files(self, user_id: str, collection_id: str, file_ids: List[str]) -> List[str]:
        collection = self.repository.get_by_id(collection_id)
        if not collection or collection.user_id != user_id:
            raise HTTPException(status_code=404, detail="Collection not found or unauthorized")

        success_ids = []
        for fid in file_ids:
            if self.repository.add_file(collection_id, fid):
                success_ids.append(fid)
        return success_ids

    async def unlink_files(self, user_id: str, collection_id: str, file_ids: List[str]) -> List[str]:
        collection = self.repository.get_by_id(collection_id)
        if not collection or collection.user_id != user_id:
            raise HTTPException(status_code=404, detail="Collection not found or unauthorized")

        success_ids = []
        for fid in file_ids:
            if self.repository.remove_file(collection_id, fid):
                success_ids.append(fid)
        return success_ids

    async def query_collection(self, user_id: str, collection_id: str, query: str) -> Dict[str, Any]:
        """
        Query a native collection.
        1. Fetch file IDs linked to the collection.
        2. Pass those file IDs as a filter to the RAG engine.
        """
        collection = self.repository.get_by_id(collection_id)
        if not collection or collection.user_id != user_id:
            raise HTTPException(status_code=404, detail="Collection not found or unauthorized")

        file_ids = [f.id for f in collection.files]
        if not file_ids:
            return {"answer": "Collection is empty.", "chunks": []}

        # Call RAG Service with file filter
        # Note: We need to implement query_files in RAGIntegrationService or reuse query_collection if configurable
        # For now, assuming we add a method `query_with_filters` to RAG service
        return await self.rag_service.query_with_filters(query, user_id, file_ids)
