import structlog
from typing import List, Dict, Any, Optional
from fastapi import HTTPException

from src.services.rag_integration_service import RAGIntegrationService
from src.api.v1.schemas import (
    RAGCollectionResponse,
    RAGLinkContentResponse,
    RAGQueryResponse,
    RAGEmbeddingsResponse,
    RAGFilesListResponse,
    RAGFileUploadResponse,
    BatchLinkResponse,
    BatchItemResult,
    IndexingStatusResponse,
    RetrieveResponse,
    SourceChunk,
    QueryFilters,
    DeleteCollectionResponse
    )
from src.api.v1.constants import RAGStatus, RAGResponseKey

logger = structlog.get_logger(__name__)

class RAGProxyClient:
    def __init__(self, rag_service: RAGIntegrationService):
        self.rag_service = rag_service

    async def register_user(self, user_id: str, email: str = None, name: str = None) -> bool:
        try:
            return await self.rag_service.register_user(user_id, email, name)
        except Exception as e:
            logger.error("Failed to register user", user_id=user_id, error=str(e))
            return False

    async def upload_file(self, file_content: bytes, filename: str, user_id: str, file_id: str = None) -> Optional[RAGFileUploadResponse]:
        try:
             result = await self.rag_service.upload_file(file_content, filename, user_id, file_id)
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

    async def upload_file_from_url(
        self,
        file_url: str,
        filename: str,
        user_id: str,
        file_id: str,
        content_type: str = "application/pdf"
    ) -> Optional[RAGFileUploadResponse]:
        try:
             result = await self.rag_service.upload_file_from_url(file_url, filename, user_id, file_id, content_type)

             if not result:
                return None

             return RAGFileUploadResponse(
                file_id=result.get(RAGResponseKey.FILE_ID, ""),
                filename=result.get(RAGResponseKey.FILENAME, filename),
                status=result.get(RAGResponseKey.STATUS, RAGStatus.SUCCESS),
                message=result.get(RAGResponseKey.MESSAGE, "File uploaded successfully")
             )
        except Exception as e:
            logger.error("RAG proxy: Failed to upload file from URL", error=str(e), filename=filename)
            return None

    async def create_collection(
        self,
        name: str,
        user_id: str,
    ) -> RAGCollectionResponse:
        try:
            result = await self.rag_service.create_collection(name, user_id)
            
            return RAGCollectionResponse(
                status=result.get("status", RAGStatus.FAILED),
                message=result.get("message", "Unknown status"),
                body=result.get("body")
            )
        except Exception as e:
            logger.error("RAG proxy: Failed to create collection", error=str(e))
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

            return RAGCollectionResponse(
                status=result.get(RAGResponseKey.STATUS, RAGStatus.SUCCESS),
                message=result.get(RAGResponseKey.MESSAGE, "Collections retrieved successfully"),
                body=result.get(RAGResponseKey.BODY)
            )
        except Exception as e:
            logger.error("RAG proxy: Failed to list collections", error=str(e))
            return RAGCollectionResponse(
                status=RAGStatus.FAILED,
                message=f"Failed to list collections: {str(e)}",
                body={"collections": []}
            )

    async def link_files(
        self,
        collection_name: str,
        file_ids: List[str],
        user_id: str
    ) -> List[RAGLinkContentResponse]:
        try:
             content_items = [{"file_id": fid} for fid in file_ids]
             results = await self.rag_service.link_content_to_collection(collection_name, content_items, user_id)
             
             response_list = []
             for res in results:
                 response_list.append(RAGLinkContentResponse(
                     file_id=res.get("file_id", ""),
                     status_code=res.get("status_code", 200),
                     message=res.get("message", "Success")
                 ))
             return response_list

        except Exception as e:
            logger.error("RAG proxy: Failed to link files", error=str(e))
            return [RAGLinkContentResponse(
                file_id="", 
                status_code=500, 
                message=f"Internal Error: {str(e)}"
            )]

    async def unlink_files(
        self,
        collection_name: str,
        file_ids: List[str],
        user_id: str
    ) -> RAGCollectionResponse:
        try:
            results = await self.rag_service.unlink_content(collection_name, file_ids, user_id)
            return []
        except Exception as e:
            logger.error("RAG proxy: Failed to unlink files", error=str(e))
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

    async def batch_link_content(
        self,
        items: List[Dict[str, Any]],
        user_id: str
    ) -> BatchLinkResponse:
        try:
            result = await self.rag_service.batch_link_content(items, user_id)

            results = [
                BatchItemResult(
                    file_id=r.get("file_id", ""),
                    status=r.get("status", "failed"),
                    error=r.get("error")
                )
                for r in result.get("results", [])
            ]

            return BatchLinkResponse(
                message=result.get("message", "Batch processing complete"),
                batch_id=result.get("batch_id", "sync_job"),
                results=results
            )
        except Exception as e:
            logger.error("RAG proxy: Failed to batch link content", error=str(e))
            return BatchLinkResponse(
                message="Batch processing failed",
                batch_id="sync_job",
                results=[BatchItemResult(file_id=item.get("file_id", ""), status="failed", error=str(e)) for item in items]
            )

    async def get_indexing_status(
        self,
        file_id: str,
        user_id: str
    ) -> IndexingStatusResponse:
        try:
            result = await self.rag_service.get_indexing_status(file_id, user_id)

            return IndexingStatusResponse(
                file_id=result.get("file_id", file_id),
                status=result.get("status", "INDEXING_FAILED"),
                error=result.get("error")
            )
        except Exception as e:
            logger.error("RAG proxy: Failed to get indexing status", error=str(e), file_id=file_id)
            return IndexingStatusResponse(
                file_id=file_id,
                status="INDEXING_FAILED",
                error=str(e)
            )

    async def retrieve_content(
        self,
        query: str,
        user_id: str,
        filters: Optional[QueryFilters] = None,
        top_k: int = 5,
        include_graph_context: bool = True
    ) -> RetrieveResponse:
        try:
            filters_dict = None
            if filters:
                filters_dict = {}
                if filters.collection_ids:
                    filters_dict["collection_ids"] = filters.collection_ids
                if filters.file_ids:
                    filters_dict["file_ids"] = filters.file_ids

            result = await self.rag_service.retrieve_content(
                query=query,
                user_id=user_id,
                filters=filters_dict,
                top_k=top_k,
                include_graph_context=include_graph_context
            )

            chunks = [
                SourceChunk(
                    chunk_id=c.get("chunk_id", "unknown"),
                    chunk_text=c.get("chunk_text", ""),
                    relevance_score=c.get("relevance_score", 0.0),
                    file_id=c.get("file_id", ""),
                    page_number=c.get("page_number"),
                    timestamp=c.get("timestamp"),
                    concepts=c.get("concepts", [])
                )
                for c in result.get("results", [])
            ]

            return RetrieveResponse(
                success=result.get("success", False),
                results=chunks
            )
        except Exception as e:
            logger.error("RAG proxy: Failed to retrieve content", error=str(e))
            return RetrieveResponse(success=False, results=[])



    async def delete_collection_data(
        self,
        collection_id: str,
        user_id: str
    ) -> DeleteCollectionResponse:
        try:
            result = await self.rag_service.delete_collection_data(collection_id, user_id)

            return DeleteCollectionResponse(
                message=result.get("message", "Deleted")
            )
        except Exception as e:
            logger.error("RAG proxy: Failed to delete collection data", error=str(e))
            return DeleteCollectionResponse(
                message=f"Failed to delete collection: {str(e)}"
            )
