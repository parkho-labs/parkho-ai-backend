"""
RAG Integration Service - Thin wrapper around the RAG Engine API
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
import httpx
from src.config import get_settings

logger = logging.getLogger(__name__)

class RAGIntegrationService:
    """Service to interface with the RAG Engine API"""

    def __init__(self):
        settings = get_settings()
        self.base_url = settings.rag_engine_url
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

    # Collection Management
    async def list_collections(self) -> List[Dict[str, Any]]:
        """Get list of all collections from RAG engine"""
        try:
            response = await self.client.get(f"{self.base_url}/collections")
            response.raise_for_status()
            data = response.json()
            return data.get('data', [])
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []

    async def create_collection(self, name: str) -> bool:
        """Create a new collection in RAG engine"""
        try:
            payload = {"name": name}
            response = await self.client.post(f"{self.base_url}/collection", json=payload)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to create collection {name}: {e}")
            return False

    async def collection_exists(self, name: str) -> bool:
        """Check if collection exists"""
        try:
            response = await self.client.get(f"{self.base_url}/collection/{name}")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to check collection {name}: {e}")
            return False

    async def delete_collection(self, name: str) -> bool:
        """Delete a collection"""
        try:
            response = await self.client.delete(f"{self.base_url}/collection/{name}")
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection {name}: {e}")
            return False

    # File Management
    async def upload_file(self, file_content: bytes, filename: str) -> Optional[str]:
        """Upload file to RAG engine and return file_id"""
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
        """Get list of all uploaded files"""
        try:
            response = await self.client.get(f"{self.base_url}/files")
            response.raise_for_status()
            data = response.json()
            return data.get('data', [])
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return []

    # Content Linking
    async def link_content_to_collection(
        self,
        collection_name: str,
        content_items: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """
        Link content items to a collection

        Args:
            collection_name: Name of the collection
            content_items: List of items with keys: name, file_id, type

        Returns:
            List of LinkContentResponse objects (207 Multi-Status)
        """
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

    async def unlink_content_from_collection(
        self,
        collection_name: str,
        file_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Unlink content from collection"""
        try:
            response = await self.client.post(
                f"{self.base_url}/{collection_name}/unlink-content",
                json=file_ids
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to unlink content from collection {collection_name}: {e}")
            return []

    # Querying
    async def query_collection(
        self,
        collection_name: str,
        query: str,
        enable_critic: bool = True
    ) -> Dict[str, Any]:
        """
        Query a collection for relevant context

        Returns:
            QueryResponse with answer, confidence, chunks, etc.
        """
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

    # Helper Methods for Content Tutor Integration
    async def get_collection_context(self, collection_name: str, topic: str) -> str:
        """
        Get relevant context from collection for quiz generation

        Args:
            collection_name: Collection to search
            topic: Topic/summary to search for

        Returns:
            Relevant context text for quiz generation
        """
        try:
            query_result = await self.query_collection(collection_name, topic)

            if query_result.get('is_relevant', False):
                # Combine answer and relevant chunks
                context_parts = [query_result.get('answer', '')]

                # Add chunk texts for additional context
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
        """
        Upload content and link to collection in one operation

        Args:
            collection_name: Target collection
            content_data: Dict with 'content', 'filename', 'content_type'

        Returns:
            Success status
        """
        try:
            # Upload file first
            file_content = content_data.get('content', '').encode('utf-8')
            filename = content_data.get('filename', 'content.txt')
            file_id = await self.upload_file(file_content, filename)

            if not file_id:
                return False

            # Link to collection
            content_items = [{
                "name": filename,
                "file_id": file_id,
                "type": content_data.get('content_type', 'text')
            }]

            link_results = await self.link_content_to_collection(collection_name, content_items)

            # Check if linking was successful
            for result in link_results:
                if result.get('status_code') == 200:
                    return True

            return False
        except Exception as e:
            logger.error(f"Failed to upload and link content: {e}")
            return False


# Global instance
_rag_service = None

def get_rag_service() -> RAGIntegrationService:
    """Get singleton RAG service instance"""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGIntegrationService()
    return _rag_service