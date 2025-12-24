from typing import List, Optional
import httpx
from .base import (
    BaseRagClient, RagLinkRequest, RagLinkResponse, 
    RagStatusResponse, RagQueryRequest, RagQueryResponse, 
    RagRetrieveResponse, RagDeleteResponse
)
from ...exceptions import ParkhoError

class CoreRagClient(BaseRagClient):
    """Core RAG operations for content management (linking, status, basic querying)."""

    async def link_content(self, user_id: str, items: List[RagLinkRequest]) -> RagLinkResponse:
        try:
            payload = {"items": [item.dict() for item in items]}
            response = await self.client.post(
                f"{self.base_url}/link-content",
                headers=self._get_headers(user_id),
                json=payload
            )
            if response.status_code == 207:
                data = response.json()
                return RagLinkResponse(**data)
            else:
                response.raise_for_status()
        except httpx.HTTPError as e:
            self.logger.error(f"RAG link_content failed: {e}")
            raise ParkhoError(f"Failed to link content to RAG engine: {e}")
        except Exception as e:
            self.logger.error(f"RAG link_content unexpected error: {e}")
            raise ParkhoError(f"Unexpected error linking content: {e}")

    async def check_indexing_status(self, user_id: str, file_ids: List[str]) -> RagStatusResponse:
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
            self.logger.error(f"RAG retrieve failed: {e}")
            raise ParkhoError(f"Failed to retrieve content from RAG engine: {e}")
        except Exception as e:
            self.logger.error(f"RAG retrieve unexpected error: {e}")
            raise ParkhoError(f"Unexpected error retrieving content: {e}")

    async def delete_files(self, user_id: str, file_ids: List[str]) -> RagDeleteResponse:
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
            raise ParkhoError(f"Failed to delete files: {e}")
        except Exception as e:
            self.logger.error(f"RAG delete files unexpected error: {e}")
            raise ParkhoError(f"Unexpected error deleting files: {e}")

    async def delete_collection(self, user_id: str, collection_id: str) -> RagDeleteResponse:
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
            self.logger.error(f"RAG delete collection failed: {e}")
            raise ParkhoError(f"Failed to delete collection: {e}")
        except Exception as e:
            self.logger.error(f"RAG delete collection unexpected error: {e}")
            raise ParkhoError(f"Unexpected error deleting collection: {e}")

    async def get_file_chunks(self, user_id: str, file_id: str) -> List[dict]:
        """Fetch raw chunks for a specific file to verify indexing content."""
        try:
            # Use retrieve endpoint with file_id filter
            payload = {
                "query": "the", # Generic query to find everything
                "top_k": 50,
                "filters": {"file_id": file_id}
            }
            response = await self.client.post(
                f"{self.base_url}/retrieve",
                headers=self._get_headers(user_id),
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])
        except Exception as e:
            self.logger.error(f"Failed to fetch chunks for file {file_id}: {e}")
            return []
