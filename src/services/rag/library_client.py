import httpx
import structlog
from typing import List, Dict, Any
from .core_client import CoreRagClient
from .base import RagQueryRequest, RagQueryResponse
from ...exceptions import ParkhoError

logger = structlog.get_logger(__name__)

class LibraryRagClient(CoreRagClient):
    """Library/Collection specialized RAG client for user-uploaded content."""

    async def collection_summary(self, user_id: str, collection_id: str, file_ids: List[str] = None) -> Dict[str, Any]:
        try:
            payload = {}
            if file_ids:
                payload["file_ids"] = file_ids
                
            url = f"{self.base_url}/collections/{collection_id}/summary"
            logger.info("request_rag_collection_summary", url=url, file_ids=file_ids, x_user_id=user_id)
            
            response = await self.client.post(
                url,
                headers=self._get_headers(user_id),
                json=payload
            )
            
            if response.status_code != 200:
                error_msg = response.text
                logger.error("rag_collection_summary_error", status_code=response.status_code, response=error_msg)
                raise ParkhoError(f"RAG summary failed ({response.status_code}): {error_msg}")
                
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Collection summary HTTP error: {e}")
            raise ParkhoError(f"Network error during summary generation: {e}")
        except Exception as e:
            logger.error(f"Collection summary unexpected error: {e}")
            raise ParkhoError(f"Unexpected error in collection summary: {str(e)}")

    async def collection_chat(self, user_id: str, collection_id: str, query: str, answer_style: str = "detailed", max_chunks: int = 5) -> Dict[str, Any]:
        try:
            payload = {
                "query": query,
                "answer_style": answer_style,
                "max_chunks": max_chunks
            }
            url = f"{self.base_url}/collections/{collection_id}/chat"
            logger.info("request_rag_collection_chat", url=url, query=query[:50], x_user_id=user_id)
            
            response = await self.client.post(
                url,
                headers=self._get_headers(user_id),
                json=payload
            )
            
            if response.status_code != 200:
                error_msg = response.text
                logger.error("rag_collection_chat_error", status_code=response.status_code, response=error_msg)
                raise ParkhoError(f"RAG chat failed ({response.status_code}): {error_msg}")
                
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Collection chat HTTP error: {e}")
            raise ParkhoError(f"Network error during collection chat: {e}")
        except Exception as e:
            logger.error(f"Collection chat unexpected error: {e}")
            raise ParkhoError(f"Unexpected error in collection chat: {str(e)}")

    async def collection_quiz(self, user_id: str, collection_id: str, num_questions: int = 10, difficulty: str = "moderate") -> Dict[str, Any]:
        try:
            params = {
                "num_questions": num_questions,
                "difficulty": difficulty
            }
            url = f"{self.base_url}/collections/{collection_id}/quiz"
            logger.info("request_rag_collection_quiz", url=url, num_questions=num_questions, x_user_id=user_id)
            
            response = await self.client.post(
                url,
                headers=self._get_headers(user_id),
                params=params
            )
            
            if response.status_code != 200:
                error_msg = response.text
                logger.error("rag_collection_quiz_error", status_code=response.status_code, response=error_msg)
                raise ParkhoError(f"RAG quiz failed ({response.status_code}): {error_msg}")
                
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Collection quiz HTTP error: {e}")
            raise ParkhoError(f"Network error during collection quiz: {e}")
        except Exception as e:
            logger.error(f"Collection quiz unexpected error: {e}")
            raise ParkhoError(f"Unexpected error in collection quiz: {str(e)}")
