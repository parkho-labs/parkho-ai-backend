import structlog
from typing import List
from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_current_user_conditional, get_rag_client, get_file_repository, get_collection_service
from src.services.rag import (
    CoreRagClient as RagClient,
    RagLinkRequest,
    RagQueryRequest,
    RagLinkResponse,
    RagQueryResponse,
    RagRetrieveResponse,
    RagStatusResponse,
    RagDeleteResponse
)
from src.services.collection_service import CollectionService
from src.repositories.file_repository import FileRepository
from src.models.user import User
from src.api.v1.constants import RAGIndexingStatus
from pydantic import BaseModel
from typing import Dict, Any, Optional

# Simplified API request/response schemas
class BatchLinkRequest(BaseModel):
    items: List[RagLinkRequest]

class StatusCheckRequest(BaseModel):
    file_ids: List[str]

class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    include_sources: bool = True
    filters: Optional[Dict[str, Any]] = None

class RetrieveRequest(BaseModel):
    query: str
    top_k: int = 5
    filters: Optional[Dict[str, Any]] = None

class DeleteFileRequest(BaseModel):
    file_ids: List[str]

class DeleteCollectionRequest(BaseModel):
    collection_id: str

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/link-content", response_model=RagLinkResponse, status_code=207)
async def batch_link_content(
    request: BatchLinkRequest,
    current_user: User = Depends(get_current_user_conditional),
    rag_client: RagClient = Depends(get_rag_client),
    file_repo: FileRepository = Depends(get_file_repository),
    collection_service: CollectionService = Depends(get_collection_service)
) -> RagLinkResponse:
    try:
        # Validate request items and ensure UploadedFile exists for non-file types
        for item in request.items:
            if item.type == "file" and not item.gcs_url:
                raise HTTPException(status_code=422, detail=f"Item {item.file_id}: 'file' type requires 'gcs_url'")
            if item.type in ["youtube", "web"] and not item.url:
                raise HTTPException(status_code=422, detail=f"Item {item.file_id}: '{item.type}' type requires 'url'")
            
            # For YouTube and Web, create local UploadedFile record if it doesn't exist
            if item.type in ["youtube", "web"]:
                existing = file_repo.get(item.file_id)
                if not existing:
                    file_repo.create_file(
                        file_id=item.file_id,
                        filename=item.url if item.type == "web" else f"YouTube: {item.file_id}",
                        file_path=item.url,
                        file_size=0,
                        content_type=item.type.upper(),
                        indexing_status="INDEXING_PENDING"
                    )

        # Call RAG Engine directly
        response = await rag_client.link_content(current_user.user_id, request.items)

        # Update indexing status in DB based on response
        for result in response.results:
            file_record = file_repo.get(result.file_id)
            if file_record:
                file_record.indexing_status = result.status
        file_repo.session.commit()

        # Link to collections in local DB (if collection_id specified)
        grouped_files = {}
        for item in request.items:
            cid = item.collection_id or "default"
            if cid not in grouped_files:
                grouped_files[cid] = []
            grouped_files[cid].append(item.file_id)

        for collection_id, file_ids in grouped_files.items():
            try:
                await collection_service.link_files(current_user.user_id, collection_id, file_ids)
            except Exception as e:
                logger.warning("Failed to link files to collection in DB", collection_id=collection_id, error=str(e))

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to batch link content", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collection/status", response_model=RagStatusResponse)
async def check_indexing_status(
    request: StatusCheckRequest,
    current_user: User = Depends(get_current_user_conditional),
    rag_client: RagClient = Depends(get_rag_client)
) -> RagStatusResponse:
    try:
        return await rag_client.check_indexing_status(current_user.user_id, request.file_ids)
    except Exception as e:
        logger.error("Failed to check status", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=RagQueryResponse)
async def query_content(
    request: QueryRequest,
    current_user: User = Depends(get_current_user_conditional),
    rag_client: RagClient = Depends(get_rag_client)
) -> RagQueryResponse:
    try:
        rag_request = RagQueryRequest(
            query=request.query,
            top_k=request.top_k,
            include_sources=request.include_sources,
            filters=request.filters
        )
        return await rag_client.query_content(current_user.user_id, rag_request)
    except Exception as e:
        logger.error("Failed to query content", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retrieve", response_model=RagRetrieveResponse)
async def retrieve_content(
    request: RetrieveRequest,
    current_user: User = Depends(get_current_user_conditional),
    rag_client: RagClient = Depends(get_rag_client)
) -> RagRetrieveResponse:
    try:
        rag_request = RagQueryRequest(
            query=request.query,
            top_k=request.top_k,
            filters=request.filters
        )
        return await rag_client.retrieve_content(current_user.user_id, rag_request)
    except Exception as e:
        logger.error("Failed to retrieve content", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/file", response_model=RagDeleteResponse)
async def delete_files(
    request: DeleteFileRequest,
    current_user: User = Depends(get_current_user_conditional),
    rag_client: RagClient = Depends(get_rag_client)
) -> RagDeleteResponse:
    if "undefined" in request.file_ids:
        raise HTTPException(status_code=400, detail="Invalid file_id: 'undefined' found in request.")
    try:
        return await rag_client.delete_files(current_user.user_id, request.file_ids)
    except Exception as e:
        logger.error("Failed to delete files", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/collection", response_model=RagDeleteResponse)
async def delete_collection_data(
    request: DeleteCollectionRequest,
    current_user: User = Depends(get_current_user_conditional),
    rag_client: RagClient = Depends(get_rag_client)
) -> RagDeleteResponse:
    try:
        return await rag_client.delete_collection(current_user.user_id, request.collection_id)
    except Exception as e:
        logger.error("Failed to delete collection data", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


