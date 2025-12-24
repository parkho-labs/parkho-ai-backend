import asyncio
from typing import List, Dict, Any, Optional
from fastapi import HTTPException
import structlog
from src.repositories.collection_repository import CollectionRepository
from src.services.rag import LibraryRagClient, RagQueryRequest, RagLinkRequest
from src.models.collection import Collection
from src.models.uploaded_file import UploadedFile

logger = structlog.get_logger(__name__)

class CollectionService:
    def __init__(self, repository: CollectionRepository, rag_client: LibraryRagClient):
        self.repository = repository
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
        
        files = []
        for f in collection.files:
            files.append({
                "file_id": f.id,
                "filename": f.filename,
                "file_size": f.file_size,
                "upload_date": f.upload_timestamp.isoformat() if f.upload_timestamp else "",
                "indexing_status": getattr(f, "indexing_status", "pending")
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

        result = await self.rag_client.collection_summary(user_id, collection_id)
        result["collection_id"] = collection_id
        return result

    async def quiz_collection(self, user_id: str, collection_id: str, num_questions: int = 10, difficulty: str = "moderate") -> Dict[str, Any]:
        collection = self.repository.get_by_id(collection_id)
        if not collection or collection.user_id != user_id:
            raise HTTPException(status_code=404, detail="Collection not found or unauthorized")

        result = await self.rag_client.collection_quiz(
            user_id=user_id,
            collection_id=collection_id,
            num_questions=num_questions,
            difficulty=difficulty
        )
        return result

    async def sync_collection_indexing_status(self, user_id: str, collection_id: str) -> List[Dict[str, Any]]:
        """
        Queries RAG engine for the actual status of files and updates local DB.
        """
        collection = self.repository.get_by_id(collection_id)
        if not collection:
            return []
            
        file_ids = [f.id for f in collection.files]
        if not file_ids:
            return []

        try:
            # check_indexing_status is in CoreRagClient (which LibraryRagClient inherits)
            rag_status_resp = await self.rag_client.check_indexing_status(user_id, file_ids)
            
            # Update local DB statuses based on RAG response
            status_map = {res.file_id: res.status for res in rag_status_resp.results}
            
            for file_record in collection.files:
                new_status = status_map.get(file_record.id)
                if new_status and new_status != "UNKNOWN":
                    file_record.indexing_status = new_status.lower()
            
            self.repository.db.commit()
            logger.info("collection_status_synced", collection_id=collection_id, file_count=len(file_ids))
        except Exception as e:
            logger.error("collection_status_sync_failed", collection_id=collection_id, error=str(e))
            
        return await self.get_collection_files(user_id, collection_id)

    async def trigger_indexing(self, user_id: str, file_id: str, gcs_uri: str, collection_id: Optional[str] = None) -> str:
        """
        Triggers RAG indexing with a single retry if it fails.
        Updates the file indexing status in the DB.
        """
        log = logger.bind(user_id=user_id, file_id=file_id, collection_id=collection_id)
        log.info("trigger_indexing_started")

        # 1. Prepare Request
        link_request = RagLinkRequest(
            file_id=file_id,
            type="file",
            gcs_url=gcs_uri,
            collection_id=collection_id
        )

        status = "indexing"
        
        # 2. Call RAG with Retry Logic
        max_retries = 2
        for attempt in range(max_retries):
            try:
                log.info("indexing_attempt", attempt=attempt+1)
                response = await self.rag_client.link_content(user_id, [link_request])
                if response.results and response.results[0].status:
                    status = response.results[0].status
                    log.info("indexing_triggered_successfully", status=status)
                    break
            except Exception as e:
                log.error("indexing_attempt_failed", attempt=attempt+1, error=str(e))
                if attempt < max_retries - 1:
                    log.info("indexing_retry_waiting", delay_seconds=4)
                    await asyncio.sleep(4)
                else:
                    status = "indexing_failed"
                    log.error("indexing_final_failure")

        # 3. Update DB
        try:
            file_record = self.repository.db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
            if file_record:
                file_record.indexing_status = status
                self.repository.db.commit()
                log.info("db_status_updated", status=status)
        except Exception as e:
            log.error("db_update_failed", error=str(e))
            self.repository.db.rollback()

        return status

    async def get_file_chunks(self, user_id: str, file_id: str) -> List[dict]:
        """Debug method to see what chunks exist in the RAG engine for a file."""
        return await self.rag_client.get_file_chunks(user_id, file_id)
