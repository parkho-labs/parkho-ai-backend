import structlog
from typing import List, Optional, Dict, Any
from src.services.rag_integration_service import RAGIntegrationService
from src.api.v1.schemas import (
    RAGFileUploadResponse,
    RAGCollectionResponse,
    RAGCollectionInfo,
    RAGFileItem,
    RAGLinkContentResponse,
    RAGCollectionFilesResponse,
    RAGFileDetail,
    RAGFilesListResponse,
    RAGQueryResponse,
    RAGEmbeddingsResponse,
    RAGEmbedding
)
from src.api.v1.constants import RAGStatus, RAGResponseKey

logger = structlog.get_logger(__name__)


class RAGProxyClient:
    def __init__(self, rag_service: RAGIntegrationService):
        self.rag_service = rag_service

    async def upload_file(
        self,
        file_content: bytes,
        filename: str,
        user_id: str
    ) -> Optional[RAGFileUploadResponse]:
        try:
            result = await self.rag_service.upload_file(file_content, filename, user_id)

            if not result:
                return None

            return RAGFileUploadResponse(
                file_id=result.get(RAGResponseKey.FILE_ID, ""),
                filename=result.get(RAGResponseKey.FILENAME, filename),
                status=result.get(RAGResponseKey.STATUS, RAGStatus.SUCCESS),
                message=result.get(RAGResponseKey.MESSAGE, "File uploaded successfully")
            )
        except Exception as e:
            logger.error("RAG proxy: Failed to upload file", error=str(e), filename=filename)
            return None

    async def create_collection(
        self,
        name: str,
        user_id: str
    ) -> RAGCollectionResponse:
        try:
            result = await self.rag_service.create_collection(name, user_id)

            return RAGCollectionResponse(
                status=result.get(RAGResponseKey.STATUS, RAGStatus.SUCCESS),
                message=result.get(RAGResponseKey.MESSAGE, "Collection created successfully"),
                body=result.get(RAGResponseKey.BODY)
            )
        except Exception as e:
            logger.error("RAG proxy: Failed to create collection", error=str(e), collection_name=name)
            return RAGCollectionResponse(
                status=RAGStatus.FAILED,
                message=f"Failed to create collection: {str(e)}",
                body=None
            )

    async def list_collections(
        self,
        user_id: str
    ) -> RAGCollectionResponse:
        try:
            result = await self.rag_service.list_collections(user_id)

            if result.get(RAGResponseKey.STATUS) == RAGStatus.FAILED:
                return RAGCollectionResponse(
                    status=RAGStatus.FAILED,
                    message=result.get(RAGResponseKey.MESSAGE, "Failed to list collections"),
                    body={RAGResponseKey.COLLECTIONS: []}
                )

            body = result.get(RAGResponseKey.BODY, {})
            if not isinstance(body, dict):
                body = {}

            collections_data = body.get(RAGResponseKey.COLLECTIONS, [])
            if not isinstance(collections_data, list):
                collections_data = []

            collections = []
            for c in collections_data:
                if isinstance(c, str):
                    collections.append(RAGCollectionInfo(name=c, created_at="", file_count=0))
                else:
                    collections.append(RAGCollectionInfo(
                        name=c.get("name", ""),
                        created_at=c.get("created_at", ""),
                        file_count=c.get("file_count", 0)
                    ))

            return RAGCollectionResponse(
                status=result.get(RAGResponseKey.STATUS, RAGStatus.SUCCESS),
                message=result.get(RAGResponseKey.MESSAGE, "Collections retrieved successfully"),
                body={RAGResponseKey.COLLECTIONS: collections}
            )
        except Exception as e:
            logger.error("RAG proxy: Failed to list collections", error=str(e))
            return RAGCollectionResponse(
                status=RAGStatus.FAILED,
                message=f"Failed to list collections: {str(e)}",
                body={RAGResponseKey.COLLECTIONS: []}
            )

    async def link_content(
        self,
        collection_name: str,
        content_items: List[RAGFileItem],
        user_id: str
    ) -> List[RAGLinkContentResponse]:
        try:
            items_dict = [
                {
                    RAGResponseKey.FILE_ID: item.file_id,
                    "type": item.type,
                    "name": item.name
                }
                for item in content_items
            ]

            results = await self.rag_service.link_content_to_collection(
                collection_name,
                items_dict,
                user_id
            )

            responses = []
            for result in results:
                responses.append(RAGLinkContentResponse(
                    name=result.get("name", ""),
                    file_id=result.get(RAGResponseKey.FILE_ID, ""),
                    type=result.get("type", "file"),
                    created_at=result.get("created_at"),
                    indexing_status=result.get(RAGResponseKey.INDEXING_STATUS, ""),
                    status_code=result.get(RAGResponseKey.STATUS_CODE, 200),
                    message=result.get(RAGResponseKey.MESSAGE, "")
                ))

            return responses
        except Exception as e:
            logger.error("RAG proxy: Failed to link content", error=str(e), collection=collection_name)
            return []

    async def get_collection_files(
        self,
        collection_name: str,
        user_id: str
    ) -> RAGCollectionFilesResponse:
        try:
            result = await self.rag_service.get_collection_files(collection_name, user_id)

            body = result.get(RAGResponseKey.BODY, {})
            files_data = body.get(RAGResponseKey.FILES, [])

            files = [
                RAGFileDetail(
                    file_id=f.get(RAGResponseKey.FILE_ID, ""),
                    filename=f.get(RAGResponseKey.FILENAME, ""),
                    file_type=f.get("file_type", ""),
                    file_size=f.get("file_size", 0),
                    upload_date=f.get("upload_date", "")
                )
                for f in files_data
            ]

            return RAGCollectionFilesResponse(
                status=result.get(RAGResponseKey.STATUS, RAGStatus.SUCCESS),
                message=result.get(RAGResponseKey.MESSAGE, "Files retrieved successfully"),
                body={RAGResponseKey.FILES: files}
            )
        except Exception as e:
            logger.error("RAG proxy: Failed to get collection files", error=str(e), collection=collection_name)
            return RAGCollectionFilesResponse(
                status=RAGStatus.FAILED,
                message=f"Failed to get collection files: {str(e)}",
                body={RAGResponseKey.FILES: []}
            )

    async def unlink_content(
        self,
        collection_name: str,
        file_ids: List[str],
        user_id: str
    ) -> List[RAGLinkContentResponse]:
        try:
            results = await self.rag_service.unlink_content(collection_name, file_ids, user_id)

            responses = []
            for result in results:
                responses.append(RAGLinkContentResponse(
                    name="",
                    file_id=result.get(RAGResponseKey.FILE_ID, ""),
                    type="file",
                    created_at=None,
                    indexing_status="",
                    status_code=result.get(RAGResponseKey.STATUS_CODE, 200),
                    message=result.get(RAGResponseKey.MESSAGE, "")
                ))

            return responses
        except Exception as e:
            logger.error("RAG proxy: Failed to unlink content", error=str(e), collection=collection_name)
            return []

    async def delete_file(
        self,
        file_id: str,
        user_id: str
    ) -> Dict[str, str]:
        try:
            result = await self.rag_service.delete_file(file_id, user_id)

            return {
                RAGResponseKey.STATUS: result.get(RAGResponseKey.STATUS, RAGStatus.SUCCESS),
                RAGResponseKey.MESSAGE: result.get(RAGResponseKey.MESSAGE, "File deleted successfully")
            }
        except Exception as e:
            logger.error("RAG proxy: Failed to delete file", error=str(e), file_id=file_id)
            return {
                RAGResponseKey.STATUS: RAGStatus.FAILED,
                RAGResponseKey.MESSAGE: f"Failed to delete file: {str(e)}"
            }

    async def list_files(
        self,
        user_id: str
    ) -> RAGFilesListResponse:
        try:
            result = await self.rag_service.list_files(user_id)

            body = result.get(RAGResponseKey.BODY, {})
            files_data = body.get(RAGResponseKey.FILES, [])

            files = [
                RAGFileDetail(
                    file_id=f.get(RAGResponseKey.FILE_ID, ""),
                    filename=f.get(RAGResponseKey.FILENAME, ""),
                    file_type=f.get("file_type", ""),
                    file_size=f.get("file_size", 0),
                    upload_date=f.get("upload_date", "")
                )
                for f in files_data
            ]

            return RAGFilesListResponse(
                status=result.get(RAGResponseKey.STATUS, RAGStatus.SUCCESS),
                message=result.get(RAGResponseKey.MESSAGE, "Files retrieved successfully"),
                body={RAGResponseKey.FILES: files}
            )
        except Exception as e:
            logger.error("RAG proxy: Failed to list files", error=str(e))
            return RAGFilesListResponse(
                status=RAGStatus.FAILED,
                message=f"Failed to list files: {str(e)}",
                body={RAGResponseKey.FILES: []}
            )

    async def query_collection(
        self,
        collection_name: str,
        query: str,
        user_id: str,
        enable_critic: bool = True
    ) -> RAGQueryResponse:
        try:
            result = await self.rag_service.query_collection(
                collection_name=collection_name,
                query=query,
                user_id=user_id,
                enable_critic=enable_critic
            )

            return RAGQueryResponse(
                status=result.get(RAGResponseKey.STATUS, RAGStatus.SUCCESS),
                message=result.get(RAGResponseKey.MESSAGE, "Query executed successfully"),
                body=result
            )
        except Exception as e:
            logger.error("RAG proxy: Failed to query collection", error=str(e), collection=collection_name)
            return RAGQueryResponse(
                status=RAGStatus.FAILED,
                message=f"Failed to query collection: {str(e)}",
                body=None
            )

    async def get_embeddings(
        self,
        collection_name: str,
        user_id: str,
        limit: int = 100
    ) -> RAGEmbeddingsResponse:
        try:
            result = await self.rag_service.get_embeddings(
                collection_name=collection_name,
                user_id=user_id,
                limit=limit
            )

            if not isinstance(result, list):
                result = []

            embeddings = [
                RAGEmbedding(
                    text=e.get("text", ""),
                    source=e.get("source")
                )
                for e in result
                if isinstance(e, dict)
            ]

            return RAGEmbeddingsResponse(
                status=RAGStatus.SUCCESS,
                message="Embeddings retrieved successfully",
                body={"embeddings": embeddings}
            )
        except Exception as e:
            logger.error("RAG proxy: Failed to get embeddings", error=str(e), collection=collection_name)
            return RAGEmbeddingsResponse(
                status=RAGStatus.FAILED,
                message=f"Failed to get embeddings: {str(e)}",
                body={"embeddings": []}
            )
