from typing import Optional
import structlog

from ...services.rag_integration_service import get_rag_service
from ...exceptions import ExternalServiceError

logger = structlog.get_logger(__name__)


class RAGIntegrationService:
    def __init__(self):
        try:
            self.rag_service = get_rag_service()
            self.enabled = True
        except Exception as e:
            logger.warning("rag_service_initialization_failed", error=str(e))
            self.rag_service = None
            self.enabled = False

    async def retrieve_context_if_needed(self, job, combined_title: str, combined_content: str) -> Optional[str]:
        if not self._should_retrieve_context(job):
            return None

        try:
            return await self._retrieve_rag_context(job.collection_name, combined_title, combined_content)
        except Exception as e:
            logger.warning("rag_context_retrieval_failed", error=str(e), job_id=job.id)
            return None

    def _should_retrieve_context(self, job) -> bool:
        if not self.enabled:
            return False

        if not hasattr(job, 'collection_name') or not job.collection_name:
            return False

        return True

    async def _retrieve_rag_context(self, collection_name: str, title: str, content: str) -> str:
        if not self.rag_service:
            raise ExternalServiceError("RAG service not available")

        try:
            query = f"{title}\n\n{content[:500]}"

            context_result = await self.rag_service.query_collection(
                collection_name=collection_name,
                query=query,
                max_results=5
            )

            if context_result.get("success") and context_result.get("results"):
                contexts = [result.get("content", "") for result in context_result["results"]]
                combined_context = "\n\n".join(filter(None, contexts))

                logger.info("rag_context_retrieved",
                           collection_name=collection_name,
                           context_length=len(combined_context),
                           result_count=len(contexts))

                return combined_context

            return ""

        except Exception as e:
            raise ExternalServiceError(f"RAG context retrieval failed: {str(e)}")

    async def add_to_collection_if_needed(self, job, content: str, title: str) -> None:
        if not self._should_add_to_collection(job):
            return

        try:
            await self._add_content_to_collection(job.collection_name, content, title, job.id)
        except Exception as e:
            logger.warning("rag_add_content_failed", error=str(e), job_id=job.id)

    def _should_add_to_collection(self, job) -> bool:
        if not self.enabled:
            return False

        if not hasattr(job, 'should_add_to_collection') or not job.should_add_to_collection:
            return False

        if not hasattr(job, 'collection_name') or not job.collection_name:
            return False

        return True

    async def _add_content_to_collection(self, collection_name: str, content: str, title: str, job_id: int) -> None:
        if not self.rag_service:
            raise ExternalServiceError("RAG service not available")

        try:
            add_result = await self.rag_service.add_to_collection(
                collection_name=collection_name,
                content=content,
                metadata={"title": title, "job_id": job_id}
            )

            if add_result.get("success"):
                logger.info("content_added_to_rag_collection",
                           collection_name=collection_name,
                           job_id=job_id,
                           title=title[:100])
            else:
                logger.warning("rag_add_content_unsuccessful", result=add_result)

        except Exception as e:
            raise ExternalServiceError(f"Failed to add content to RAG collection: {str(e)}")