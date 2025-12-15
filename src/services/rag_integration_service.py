import logging
from typing import List, Dict, Any, Optional
import httpx
from src.config import get_settings
from src.api.v1.constants import RAGEndpoint, RAGResponseKey, RAGStatus

logger = logging.getLogger(__name__)

class RAGIntegrationService:
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.rag_engine_url
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def register_user(self, user_id: str, email: str = None, name: str = None) -> bool:
        try:
            payload = {
                "user_id": user_id,
                "email": email or f"{user_id}@example.com",
                "name": name or f"User {user_id}"
            }
            response = await self.client.post(f"{self.base_url}{RAGEndpoint.USER_REGISTER}", json=payload)
            response.raise_for_status()
            data = response.json()

            if data.get(RAGResponseKey.STATUS) == RAGStatus.SUCCESS:
                logger.info(f"Successfully registered user {user_id} with RAG engine")
                return True
            else:
                logger.error(f"RAG engine registration failed for user {user_id}: {data.get('message', 'Unknown error')}")
                raise Exception(f"RAG registration failed: {data.get('message', 'Unknown error')}")

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during RAG user registration for {user_id}: {e}")
            raise Exception(f"RAG registration HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Failed to register user {user_id} with RAG engine: {e}")
            raise Exception(f"RAG registration failed: {str(e)}")


    async def upload_file(self, file_content: bytes, filename: str, user_id: str, file_id: str = None) -> Optional[Dict[str, Any]]:
        try:
            files = {"files": (filename, file_content, "application/octet-stream")}
            data = {"file_id": file_id} if file_id else {}
            headers = {"x-user-id": user_id}
            response = await self.client.post(f"{self.base_url}{RAGEndpoint.FILES}", files=files, data=data, headers=headers)
            response.raise_for_status()
            data = response.json()

            if data.get(RAGResponseKey.STATUS) == RAGStatus.SUCCESS:
                return {
                    RAGResponseKey.FILE_ID: data.get(RAGResponseKey.FILE_ID),
                    RAGResponseKey.FILENAME: data.get(RAGResponseKey.FILENAME),
                    RAGResponseKey.STATUS: data.get(RAGResponseKey.STATUS),
                    RAGResponseKey.MESSAGE: data.get(RAGResponseKey.MESSAGE)
                }
            return None
        except Exception as e:
            logger.error(f"Failed to upload file {filename}: {e}")
            return None

    async def upload_file_from_url(
        self, 
        file_url: str, 
        filename: str, 
        user_id: str, 
        file_id: str,
        content_type: str = "application/pdf"
    ) -> Optional[Dict[str, Any]]:
        try:
            payload = {
                "url": file_url,
                "file_id": file_id,
                "filename": filename,
                "content_type": content_type
            }
            headers = {"x-user-id": user_id, "Content-Type": "application/json"}
            
            response = await self.client.post(
                f"{self.base_url}{RAGEndpoint.FILES}", 
                json=payload, 
                headers=headers
            )
            response.raise_for_status()
            data = response.json()

            if data.get(RAGResponseKey.STATUS) == RAGStatus.SUCCESS:
                return {
                    RAGResponseKey.FILE_ID: data.get(RAGResponseKey.FILE_ID, file_id),
                    RAGResponseKey.FILENAME: data.get(RAGResponseKey.FILENAME, filename),
                    RAGResponseKey.STATUS: data.get(RAGResponseKey.STATUS),
                    RAGResponseKey.MESSAGE: data.get(RAGResponseKey.MESSAGE)
                }
            return None
        except Exception as e:
            logger.error(f"Failed to trigger RAG upload from URL for {filename}: {e}")
            return None

    async def list_files(self, user_id: str) -> Dict[str, Any]:
        try:
            headers = {"x-user-id": user_id}
            response = await self.client.get(f"{self.base_url}{RAGEndpoint.FILES}", headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return {RAGResponseKey.STATUS: RAGStatus.FAILED, RAGResponseKey.MESSAGE: str(e), RAGResponseKey.BODY: {RAGResponseKey.FILES: []}}

    async def link_content_to_collection(
        self,
        collection_name: str,
        content_items: List[Dict[str, str]],
        user_id: str = "default_user"
    ) -> List[Dict[str, Any]]:

        try:
            headers = {"x-user-id": user_id}
            url = f"{self.base_url}{RAGEndpoint.COLLECTION_LINK_CONTENT}".format(collection_name=collection_name)
            response = await self.client.post(
                url,
                json=content_items,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to link content to collection {collection_name}: {e}")
            return []

    async def query_collection(
        self,
        collection_name: str,
        query: str,
        user_id: str,
        enable_critic: bool = True
    ) -> Dict[str, Any]:

        try:
            payload = {
                "query": query,
                "enable_critic": enable_critic
            }
            headers = {
                "x-user-id": user_id,
                "Content-Type": "application/json"
            }
            url = f"{self.base_url}{RAGEndpoint.COLLECTION_QUERY}".format(collection_name=collection_name)
            response = await self.client.post(
                url,
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to query collection {collection_name}: {e}")
            return {
                "answer": "",
                "confidence": 0.0,
                "is_relevant": False,
                "chunks": []
            }



    async def upload_and_link_content(
        self,
        collection_name: str,
        content_data: Dict[str, Any],
        user_id: str = "default_user"
    ) -> bool:

        try:
            file_content = content_data.get('content', '').encode('utf-8')
            filename = content_data.get('filename', 'content.txt')
            upload_result = await self.upload_file(file_content, filename, user_id)

            if not upload_result:
                return False

            content_items = [{
                "name": filename,
                "file_id": upload_result.get('file_id'),
                "type": content_data.get('content_type', 'text')
            }]

            link_results = await self.link_content_to_collection(collection_name, content_items, user_id)

            for result in link_results:
                if result.get('status_code') == 200:
                    return True

            return False
        except Exception as e:
            logger.error(f"Failed to upload and link content: {e}")
            return False

    async def create_collection(self, collection_name: str, user_id: str) -> Dict[str, Any]:
        try:
            headers = {"x-user-id": user_id}
            payload = {"name": collection_name}
            response = await self.client.post(
                f"{self.base_url}{RAGEndpoint.COLLECTION}",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to create collection {collection_name}: {e}")
            return {RAGResponseKey.STATUS: RAGStatus.FAILED, RAGResponseKey.MESSAGE: str(e)}

    async def list_collections(self, user_id: str) -> Dict[str, Any]:
        try:
            headers = {"x-user-id": user_id}
            response = await self.client.get(
                f"{self.base_url}{RAGEndpoint.COLLECTIONS}",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return {RAGResponseKey.STATUS: RAGStatus.FAILED, RAGResponseKey.MESSAGE: str(e), RAGResponseKey.BODY: {RAGResponseKey.COLLECTIONS: []}}

    async def get_collection_files(self, collection_name: str, user_id: str) -> Dict[str, Any]:
        try:
            headers = {"x-user-id": user_id}
            url = f"{self.base_url}{RAGEndpoint.COLLECTION_FILES}".format(collection_name=collection_name)
            response = await self.client.get(
                url,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get files for collection {collection_name}: {e}")
            return {RAGResponseKey.STATUS: RAGStatus.FAILED, RAGResponseKey.MESSAGE: str(e), RAGResponseKey.BODY: {RAGResponseKey.FILES: []}}

    async def delete_file(self, file_id: str, user_id: str) -> Dict[str, Any]:
        try:
            headers = {"x-user-id": user_id}
            url = f"{self.base_url}{RAGEndpoint.FILE_BY_ID}".format(file_id=file_id)
            response = await self.client.delete(
                url,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to delete file {file_id}: {e}")
            return {RAGResponseKey.STATUS: RAGStatus.FAILED, RAGResponseKey.MESSAGE: str(e)}

    async def unlink_content(self, collection_name: str, file_ids: List[str], user_id: str) -> List[Dict[str, Any]]:
        try:
            headers = {"x-user-id": user_id}
            url = f"{self.base_url}{RAGEndpoint.COLLECTION_UNLINK_CONTENT}".format(collection_name=collection_name)
            response = await self.client.post(
                url,
                json=file_ids,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to unlink content from collection {collection_name}: {e}")
            return []


    async def query_with_filters(
        self,
        query: str,
        user_id: str,
        file_ids: List[str]
    ) -> Dict[str, Any]:
        try:
            payload = {
                "query": query,
                "filters": {"file_ids": file_ids},
                "enable_critic": True
            }
            headers = {"x-user-id": user_id}
            response = await self.client.post(
                f"{self.base_url}/query", 
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to query with filters for files {file_ids}: {e}")
            raise

    async def batch_link_content(
        self,
        items: List[Dict[str, Any]],
        user_id: str
    ) -> Dict[str, Any]:
        try:
            headers = {"x-user-id": user_id}
            response = await self.client.post(
                f"{self.base_url}{RAGEndpoint.LINK_CONTENT}",
                json={"items": items},
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to batch link content: {e}")
            return {
                "message": "Batch processing failed",
                "batch_id": "sync_job",
                "results": [{"file_id": item.get("file_id", ""), "status": "failed", "error": str(e)} for item in items]
            }

    async def get_indexing_status(
        self,
        file_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        try:
            headers = {"x-user-id": user_id}
            # Updated to POST /status with file_ids list
            response = await self.client.post(
                f"{self.base_url}{RAGEndpoint.STATUS}", 
                json={"file_ids": [file_id]},
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract result for specific file
            results = data.get("results", [])
            for res in results:
                if res.get("file_id") == file_id:
                    # Map new response format to expected format if needed, or return as is
                    return res
            
            return {"file_id": file_id, "status": "UNKNOWN", "message": "Status not found in response"}
        except Exception as e:
            logger.error(f"Failed to get indexing status for {file_id}: {e}")
            return {"file_id": file_id, "status": "INDEXING_FAILED", "error": str(e)}

    async def retrieve_content(
        self,
        query: str,
        user_id: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
        include_graph_context: bool = True
    ) -> Dict[str, Any]:
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
            return response.json()
        except Exception as e:
            logger.error(f"Failed to retrieve content: {e}")
            return {"success": False, "results": []}



    async def delete_collection_data(
        self,
        collection_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        try:
            headers = {"x-user-id": user_id}
            payload = {"collection_id": collection_id}
            response = await self.client.delete(
                f"{self.base_url}{RAGEndpoint.DELETE_COLLECTION}",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to delete collection {collection_id}: {e}")
            return {"message": f"Failed to delete collection: {str(e)}"}


_rag_service = None

def get_rag_service() -> RAGIntegrationService:
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGIntegrationService()
    return _rag_service