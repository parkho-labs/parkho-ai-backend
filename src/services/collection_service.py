from typing import List, Dict, Any
from fastapi import HTTPException
from src.repositories.collection_repository import CollectionRepository
from src.services.rag_integration_service import RAGIntegrationService
from src.models.collection import Collection

class CollectionService:
    def __init__(self, repository: CollectionRepository, rag_service: RAGIntegrationService):
        self.repository = repository
        # We need RAG service only for Querying, not for Management anymore!
        self.rag_service = rag_service

    async def create_collection(self, user_id: str, name: str) -> Collection:
        return self.repository.create(user_id, name)

    async def list_collections(self, user_id: str) -> List[Collection]:
        return self.repository.get_all_by_user(user_id)

    async def delete_collection(self, user_id: str, collection_id: str) -> bool:
        collection = self.repository.get_by_id(collection_id)
        if not collection or collection.user_id != user_id:
            raise HTTPException(status_code=404, detail="Collection not found or unauthorized")
        return self.repository.delete(collection_id)

    async def link_files(self, user_id: str, collection_id: str, file_ids: List[str]) -> List[str]:
        # Verify collection ownership
        collection = self.repository.get_by_id(collection_id)
        if not collection or collection.user_id != user_id:
            raise HTTPException(status_code=404, detail="Collection not found or unauthorized")

        # Optimization: Use Bulk Insert
        count = self.repository.add_files_bulk(collection_id, file_ids)
        
        # We assume all valid IDs were added. 
        # Ideally we'd return exactly which IDs were new, but for now returning the input list 
        # (or just the count) is acceptable for the UI to update optimistically.
        return file_ids 

    async def unlink_files(self, user_id: str, collection_id: str, file_ids: List[str]) -> List[str]:
        # Verify collection ownership
        collection = self.repository.get_by_id(collection_id)
        if not collection or collection.user_id != user_id:
            raise HTTPException(status_code=404, detail="Collection not found or unauthorized")

        # Optimization: Use Bulk Delete
        count = self.repository.remove_files_bulk(collection_id, file_ids)
        return file_ids

    async def get_collection_files(self, user_id: str, collection_id: str) -> List[Dict[str, Any]]:
        collection = self.repository.get_by_id(collection_id)
        if not collection or collection.user_id != user_id:
            raise HTTPException(status_code=404, detail="Collection not found or unauthorized")
        
        # Convert ORM objects to dicts
        files = []
        for f in collection.files:
            files.append({
                "file_id": f.id,
                "filename": f.filename,
                "file_size": f.file_size,
                "upload_date": f.upload_timestamp.isoformat() if f.upload_timestamp else ""
            })
        return files

    async def query_collection(self, user_id: str, collection_id: str, query: str) -> Dict[str, Any]:
        collection = self.repository.get_by_id(collection_id)
        if not collection or collection.user_id != user_id:
            raise HTTPException(status_code=404, detail="Collection not found or unauthorized")

        file_ids = [f.id for f in collection.files]
        if not file_ids:
            return {"answer": "Collection is empty.", "chunks": []}

        # Call RAG Service with file filter
        return await self.rag_service.query_with_filters(query, user_id, file_ids)
