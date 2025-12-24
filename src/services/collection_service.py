from typing import List, Dict, Any
from fastapi import HTTPException
from src.repositories.collection_repository import CollectionRepository
from src.services.rag import LibraryRagClient, RagQueryRequest
from src.models.collection import Collection
import structlog

logger = structlog.get_logger(__name__)

class CollectionService:
    def __init__(self, repository: CollectionRepository, rag_client: LibraryRagClient):
        self.repository = repository
        # We need RAG client only for Querying, not for Management anymore!
        self.rag_client = rag_client

    async def create_collection(self, user_id: str, name: str) -> Collection:
        return self.repository.create(user_id, name)

    async def list_collections(self, user_id: str) -> List[Collection]:
        return self.repository.get_all_by_user(user_id)

    async def delete_collection(self, user_id: str, collection_id: str) -> bool:
        collection = self.repository.get_by_id(collection_id)
        if not collection or collection.user_id != user_id:
            raise HTTPException(status_code=404, detail="Collection not found or unauthorized")

        try:
            await self.rag_client.delete_collection(user_id, collection_id)
        except Exception as e:
            logger.warning("Failed to delete collection data from RAG service, proceeding with local deletion", collection_id=collection_id, error=str(e))

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

        # Call RAG Client with file filter
        request = RagQueryRequest(query=query, filters={"file_ids": file_ids})
        result = await self.rag_client.query_content(user_id, request)
        return result.model_dump()

    async def chat_collection(self, user_id: str, collection_id: str, query: str, answer_style: str = "detailed", max_chunks: int = 5) -> Dict[str, Any]:
        collection = self.repository.get_by_id(collection_id)
        if not collection or collection.user_id != user_id:
            raise HTTPException(status_code=404, detail="Collection not found or unauthorized")

        # Native RAG collection chat handles restricting the context internally by collection_id
        result = await self.rag_client.collection_chat(
            user_id=user_id,
            collection_id=collection_id,
            query=query,
            answer_style=answer_style,
            max_chunks=max_chunks
        )
        return result

    async def summary_collection(self, user_id: str, collection_id: str) -> Dict[str, Any]:
        collection = self.repository.get_by_id(collection_id)
        if not collection or collection.user_id != user_id:
            raise HTTPException(status_code=404, detail="Collection not found or unauthorized")

        file_ids = [f.id for f in collection.files]
        if not file_ids:
            return {
                "summary": "Collection is empty. No content to summarize.",
                "processing_time_ms": 0,
                "collection_id": collection_id
            }

        result = await self.rag_client.collection_summary(user_id, collection_id, file_ids)
        result["collection_id"] = collection_id
        return result

    async def quiz_collection(self, user_id: str, collection_id: str, num_questions: int = 10, difficulty: str = "moderate") -> Dict[str, Any]:
        collection = self.repository.get_by_id(collection_id)
        if not collection or collection.user_id != user_id:
            raise HTTPException(status_code=404, detail="Collection not found or unauthorized")

        # Native RAG collection quiz handles context and distribution internally
        result = await self.rag_client.collection_quiz(
            user_id=user_id,
            collection_id=collection_id,
            num_questions=num_questions,
            difficulty=difficulty
        )
        return result
