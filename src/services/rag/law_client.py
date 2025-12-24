from typing import List, Dict, Any
import httpx
from .core_client import CoreRagClient
from .base import RagQueryResponse, RagChunk, RagRetrieveResponse

class LawRagClient(CoreRagClient):
    """Legal Assistant specialized RAG client for constitutional law queries."""

    async def legal_chat(self, user_id: str, question: str, scope: List[str] = None) -> RagQueryResponse:
        try:
            if scope is None:
                scope = ["constitution"]
            
            payload = {
                "question": question,
                "scope": scope
            }
            url = f"{self.base_url}/law/chat"
            response = await self.client.post(
                url,
                headers=self._get_headers(user_id),
                json=payload
            )
            response.raise_for_status()
            data = response.json()

            sources = []
            if data.get("sources"):
                for source in data["sources"]:
                    sources.append(RagChunk(
                        chunk_id=f"legal_{hash(source.get('text', ''))}",
                        chunk_text=source.get("text", ""),
                        relevance_score=1.0,
                        file_id="legal_document",
                        concepts=[source.get("article", "Constitutional Law")]
                    ))

            return RagQueryResponse(
                success=True,
                answer=data.get("answer", ""),
                sources=sources
            )
        except httpx.HTTPError as e:
            self.logger.error(f"Legal chat failed: {e}")
            raise ParkhoError(f"Failed to get legal chat response: {e}")
        except Exception as e:
            self.logger.error(f"Legal chat unexpected error: {e}")
            raise ParkhoError(f"Unexpected error in legal chat: {e}")

    async def legal_retrieve(self, user_id: str, query: str, collection_ids: List[str], top_k: int = 10) -> RagRetrieveResponse:
        try:
            payload = {
                "query": query,
                "user_id": user_id,
                "collection_ids": collection_ids,
                "top_k": top_k
            }
            response = await self.client.post(
                f"{self.base_url}/law/retrieve",
                headers=self._get_headers(user_id),
                json=payload
            )
            response.raise_for_status()
            data = response.json()

            chunks = []
            if data.get("success") and data.get("results"):
                for result in data["results"]:
                    chunks.append(RagChunk(
                        chunk_id=result.get("chunk_id", ""),
                        chunk_text=result.get("chunk_text", ""),
                        relevance_score=result.get("relevance_score", 0.0),
                        file_id=result.get("file_id", ""),
                        page_number=result.get("page_number"),
                        concepts=result.get("concepts", [])
                    ))

            return RagRetrieveResponse(
                success=data.get("success", False),
                results=chunks
            )
        except httpx.HTTPError as e:
            self.logger.error(f"Legal retrieve failed: {e}")
            raise ParkhoError(f"Failed to retrieve legal content: {e}")
        except Exception as e:
            self.logger.error(f"Legal retrieve unexpected error: {e}")
            raise ParkhoError(f"Unexpected error in legal retrieve: {e}")

    async def legal_questions(self, user_id: str, questions_spec: List[Dict], context: Dict = None) -> Dict:
        try:
            total_questions = sum(q["count"] for q in questions_spec)
            question_data = []
            type_mapping = {
                "assertion_reasoning": "Assertion_Reason",
                "match_following": "Match the Column",
                "mcq": "MCQ",
                "comprehension": "MCQ"
            }
            difficulty_mapping = {
                "easy": "easy",
                "moderate": "medium",
                "difficult": "hard"
            }

            for q in questions_spec:
                item = {
                    "question_type": type_mapping.get(q["type"], q["type"]),
                    "num_questions": q["count"]
                }
                if "difficulty" in q:
                    item["difficulty"] = difficulty_mapping.get(q["difficulty"], q["difficulty"])
                if "filters" in q:
                    item["filters"] = q["filters"]
                question_data.append(item)

            scope = ["constitution"]
            first_filters = questions_spec[0].get("filters", {}) if questions_spec else {}
            if first_filters.get("collection_ids"):
                collection_ids = first_filters["collection_ids"]
                if "constitution-golden-source" in collection_ids:
                    scope = ["constitution"]
                elif any("bns" in cid.lower() for cid in collection_ids):
                    scope = ["bns"]

            raw_difficulty = questions_spec[0]["difficulty"] if questions_spec else "moderate"
            difficulty = difficulty_mapping.get(raw_difficulty, "medium")

            payload = {
                "title": f"Quiz on {context.get('subject', 'Constitutional Law')}" if context else "Legal Quiz",
                "scope": scope,
                "num_questions": total_questions,
                "difficulty": difficulty,
                "question_data": question_data
            }
            if first_filters:
                if "collection_ids" in first_filters:
                    payload["collection_ids"] = first_filters["collection_ids"]
                if "file_ids" in first_filters:
                    payload["file_ids"] = first_filters["file_ids"]

            response = await self.client.post(
                f"{self.base_url}/law/questions",
                headers=self._get_headers(user_id),
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            self.logger.error(f"Legal questions failed: {e}")
            raise ParkhoError(f"Failed to generate legal questions: {e}")
        except Exception as e:
            self.logger.error(f"Legal questions unexpected error: {e}")
            raise ParkhoError(f"Unexpected error in legal questions: {e}")
