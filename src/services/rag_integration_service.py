import logging
from typing import List, Dict, Any, Optional
import httpx
from src.config import get_settings

logger = logging.getLogger(__name__)

class RAGIntegrationService:
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.rag_engine_url
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    
    async def upload_file(self, file_content: bytes, filename: str) -> Optional[str]:
        try:
            files = {"file": (filename, file_content, "application/octet-stream")}
            response = await self.client.post(f"{self.base_url}/files", files=files)
            response.raise_for_status()
            data = response.json()

            if data.get('status') == 'SUCCESS':
                return data.get('body', {}).get('file_id')
            return None
        except Exception as e:
            logger.error(f"Failed to upload file {filename}: {e}")
            return None

    async def list_files(self) -> List[Dict[str, Any]]:
        try:
            response = await self.client.get(f"{self.base_url}/files")
            response.raise_for_status()
            data = response.json()
            return data.get('data', [])
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return []

    async def link_content_to_collection(
        self,
        collection_name: str,
        content_items: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
       
        try:
            response = await self.client.post(
                f"{self.base_url}/{collection_name}/link-content",
                json=content_items
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
        enable_critic: bool = True
    ) -> Dict[str, Any]:
        
        try:
            payload = {
                "query": query,
                "enable_critic": enable_critic
            }
            response = await self.client.post(
                f"{self.base_url}/{collection_name}/query",
                json=payload
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

    async def get_collection_context(self, collection_name: str, topic: str) -> str:
       
        try:
            query_result = await self.query_collection(collection_name, topic)

            if query_result.get('is_relevant', False):
                context_parts = [query_result.get('answer', '')]

                for chunk in query_result.get('chunks', []):
                    if chunk.get('text'):
                        context_parts.append(chunk['text'])

                return "\n\n".join(filter(None, context_parts))

            return ""
        except Exception as e:
            logger.error(f"Failed to get collection context: {e}")
            return ""

    async def upload_and_link_content(
        self,
        collection_name: str,
        content_data: Dict[str, Any]
    ) -> bool:
       
        try:
            file_content = content_data.get('content', '').encode('utf-8')
            filename = content_data.get('filename', 'content.txt')
            file_id = await self.upload_file(file_content, filename)

            if not file_id:
                return False

            content_items = [{
                "name": filename,
                "file_id": file_id,
                "type": content_data.get('content_type', 'text')
            }]

            link_results = await self.link_content_to_collection(collection_name, content_items)

            for result in link_results:
                if result.get('status_code') == 200:
                    return True

            return False
        except Exception as e:
            logger.error(f"Failed to upload and link content: {e}")
            return False


_rag_service = None

def get_rag_service() -> RAGIntegrationService:
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGIntegrationService()
    return _rag_service