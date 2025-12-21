from typing import List, Optional
import httpx
import logging
from ..config import get_settings
from ..exceptions import ParkhoError
from ..api.v1.schemas import (
    RagQuestionGenerationRequest,
    RagQuestionGenerationResponse,
    ContentStatsRequest,
    ContentStatsResponse,
    SupportedTypesResponse,
    ContentValidationRequest,
    ContentValidationResponse,
    HealthCheckResponse
)


class RagQuestionGeneratorService:
    _instance: Optional['RagQuestionGeneratorService'] = None
    _lock = None

    def __init__(self, base_url: Optional[str] = None):
        settings = get_settings()
        self.base_url = base_url or f"{settings.rag_engine_url}/questions"
        self.timeout = getattr(settings, 'rag_questions_timeout', 60.0)
        self.client = httpx.AsyncClient(timeout=self.timeout)
        self.logger = logging.getLogger(__name__)

    @classmethod
    def get_instance(cls) -> 'RagQuestionGeneratorService':
        import threading
        if cls._lock is None:
            cls._lock = threading.Lock()

        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _get_headers(self) -> dict:
        return {"Content-Type": "application/json"}

    async def generate_questions(self, request: RagQuestionGenerationRequest) -> RagQuestionGenerationResponse:
        try:
            response = await self.client.post(
                f"{self.base_url}/generate",
                headers=self._get_headers(),
                json=request.dict()
            )
            response.raise_for_status()
            data = response.json()
            return RagQuestionGenerationResponse(**data)

        except httpx.HTTPError as e:
            self.logger.error(f"RAG question generation failed: {e}")
            raise ParkhoError(f"Failed to generate questions: {e}")
        except Exception as e:
            self.logger.error(f"RAG question generation unexpected error: {e}")
            raise ParkhoError(f"Unexpected error generating questions: {e}")

    async def get_content_stats(self, request: ContentStatsRequest) -> ContentStatsResponse:
        try:
            params = {}
            if request.collection_ids:
                params["collection_ids"] = ",".join(request.collection_ids)

            response = await self.client.get(
                f"{self.base_url}/content-stats",
                headers=self._get_headers(),
                params=params
            )
            response.raise_for_status()
            data = response.json()
            return ContentStatsResponse(**data)

        except httpx.HTTPError as e:
            self.logger.error(f"RAG content stats failed: {e}")
            raise ParkhoError(f"Failed to get content stats: {e}")
        except Exception as e:
            self.logger.error(f"RAG content stats unexpected error: {e}")
            raise ParkhoError(f"Unexpected error getting content stats: {e}")

    async def get_supported_types(self) -> SupportedTypesResponse:
        try:
            response = await self.client.get(
                f"{self.base_url}/supported-types",
                headers=self._get_headers()
            )
            response.raise_for_status()
            data = response.json()
            return SupportedTypesResponse(**data)

        except httpx.HTTPError as e:
            self.logger.error(f"RAG supported types failed: {e}")
            raise ParkhoError(f"Failed to get supported types: {e}")
        except Exception as e:
            self.logger.error(f"RAG supported types unexpected error: {e}")
            raise ParkhoError(f"Unexpected error getting supported types: {e}")

    async def validate_content(self, request: ContentValidationRequest) -> ContentValidationResponse:
        try:
            response = await self.client.post(
                f"{self.base_url}/validate-content",
                headers=self._get_headers(),
                json=request.dict()
            )
            response.raise_for_status()
            data = response.json()
            return ContentValidationResponse(**data)

        except httpx.HTTPError as e:
            self.logger.error(f"RAG content validation failed: {e}")
            raise ParkhoError(f"Failed to validate content: {e}")
        except Exception as e:
            self.logger.error(f"RAG content validation unexpected error: {e}")
            raise ParkhoError(f"Unexpected error validating content: {e}")

    async def health_check(self) -> HealthCheckResponse:
        try:
            response = await self.client.get(
                f"{self.base_url}/health",
                headers=self._get_headers()
            )
            response.raise_for_status()
            data = response.json()
            return HealthCheckResponse(**data)

        except httpx.HTTPError as e:
            self.logger.error(f"RAG health check failed: {e}")
            raise ParkhoError(f"Failed to check health: {e}")
        except Exception as e:
            self.logger.error(f"RAG health check unexpected error: {e}")
            raise ParkhoError(f"Unexpected error checking health: {e}")

    async def close(self):
        await self.client.aclose()


rag_question_generator = RagQuestionGeneratorService.get_instance()