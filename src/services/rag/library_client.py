from typing import List, Dict, Any
from .core_client import CoreRagClient
from .base import RagQueryRequest, RagQueryResponse

class LibraryRagClient(CoreRagClient):
    """Library/Collection specialized RAG client for user-uploaded content."""

    async def collection_summary(self, user_id: str, collection_id: str, file_ids: List[str]) -> Dict[str, Any]:
        try:
            payload = {"file_ids": file_ids}
            response = await self.client.post(
                f"{self.base_url}/collections/{collection_id}/summary",
                headers=self._get_headers(user_id),
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            self.logger.error(f"Collection summary failed: {e}")
            raise ParkhoError(f"Failed to generate summary: {e}")
        except Exception as e:
            self.logger.error(f"Collection summary unexpected error: {e}")
            raise ParkhoError(f"Unexpected error summary generation: {e}")

    async def collection_chat(self, user_id: str, collection_id: str, query: str, answer_style: str = "detailed", max_chunks: int = 5) -> Dict[str, Any]:
        try:
            payload = {
                "query": query,
                "answer_style": answer_style,
                "max_chunks": max_chunks
            }
            response = await self.client.post(
                f"{self.base_url}/collections/{collection_id}/chat",
                headers=self._get_headers(user_id),
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            self.logger.error(f"Collection chat failed: {e}")
            raise ParkhoError(f"Failed to chat with collection: {e}")
        except Exception as e:
            self.logger.error(f"Collection chat unexpected error: {e}")
            raise ParkhoError(f"Unexpected error collection chat: {e}")

    async def collection_quiz(self, user_id: str, collection_id: str, num_questions: int = 10, difficulty: str = "moderate") -> Dict[str, Any]:
        try:
            params = {
                "num_questions": num_questions,
                "difficulty": difficulty
            }
            response = await self.client.post(
                f"{self.base_url}/collections/{collection_id}/quiz",
                headers=self._get_headers(user_id),
                params=params
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            self.logger.error(f"Collection quiz failed: {e}")
            raise ParkhoError(f"Failed to generate collection quiz: {e}")
        except Exception as e:
            self.logger.error(f"Collection quiz unexpected error: {e}")
            raise ParkhoError(f"Unexpected error quiz generation: {e}")
