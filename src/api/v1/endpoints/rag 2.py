import structlog
from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_current_user_conditional, get_rag_service, get_file_repository, get_collection_service
from src.services.rag_service import RagService
from src.services.collection_service import CollectionService
from src.repositories.file_repository import FileRepository
from src.models.user import User
from src.api.v1.constants import RAGIndexingStatus
from src.api.v1.schemas import (
    BatchLinkRequest,
    BatchLinkResponse,
    StatusCheckRequest,
    StatusCheckResponse,
    QueryRequest,
    QueryResponse,
    RetrieveRequest,
    RetrieveResponse,
    DeleteFileRequest,
    DeleteFileResponse,
    DeleteCollectionRequest,
    DeleteCollectionResponse
)

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/link-content", response_model=BatchLinkResponse, status_code=207)
async def batch_link_content(
    request: BatchLinkRequest,
    current_user: User = Depends(get_current_user_conditional),
    rag_service: RagService = Depends(get_rag_service),
    file_repo: FileRepository = Depends(get_file_repository),
    collection_service: CollectionService = Depends(get_collection_service)
) -> BatchLinkResponse:
    try:
        grouped_files = {} # collection_id -> [file_ids]

        # 1. Validate and Persist Metadata
        for item in request.items:
            if item.type == "file" and not item.gcs_url:
                raise HTTPException(status_code=422, detail=f"Item {item.file_id}: 'file' type requires 'gcs_url'")
            if item.type in ["youtube", "web"] and not item.url:
                raise HTTPException(status_code=422, detail=f"Item {item.file_id}: '{item.type}' type requires 'url'")

            # Determine Content Type and Path
            mapped_content_type = "FILE"
            file_path = item.gcs_url
            
            if item.type == "youtube":
                mapped_content_type = "YOUTUBE"
                file_path = item.url
            elif item.type == "web":
                mapped_content_type = "WEB"
                file_path = item.url
            elif item.type == "file":
                 # For 'file', it might already exist if uploaded via /files
                 # But if linked via GCS URL directly, we might need to ensure record exists
                 mapped_content_type = "FILE"

            # Check if exists, else create
            existing_file = file_repo.get(item.file_id)
            if not existing_file:
                # Create metadata record
                # We don't have file size for external links, set to 0
                file_repo.create_file(
                    file_id=item.file_id,
                    filename=item.url if item.url else (item.gcs_url.split('/')[-1] if item.gcs_url else item.file_id),
                    file_path=file_path,
                    file_size=0,
                    content_type=mapped_content_type,
                    file_type=None, # Explicitly None for non-files, or could derive from URL
                    indexing_status=RAGIndexingStatus.INDEXING_PENDING
                )
            
            # Group for Collection Linking
            if item.collection_id:
                if item.collection_id not in grouped_files:
                    grouped_files[item.collection_id] = []
                grouped_files[item.collection_id].append(item.file_id)

        # 2. Call RAG Service (The Source of Truth for Indexing)
        items_dict = [item.model_dump() for item in request.items]
        rag_response = await rag_service.batch_link_content(items_dict, current_user.user_id)

        # 3. Link to Collections in Postgres (if RAG didn't fail completely)
        # We do this optimistically or if batch succcessful. 
        # Even if RAG fails individual items, we might want to keep the link?
        # Using RAG response to filter? No, rag_response returns results. 
        # Let's link all requested.
        for collection_id, file_ids in grouped_files.items():
            try:
                await collection_service.link_files(current_user.user_id, collection_id, file_ids)
            except Exception as e:
                logger.error("Failed to link files to collection in DB", collection_id=collection_id, error=str(e))
                # Don't fail the whole request, as RAG might have succeeded

        return rag_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to batch link content", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collection/status", response_model=StatusCheckResponse)
async def check_indexing_status(
    request: StatusCheckRequest,
    current_user: User = Depends(get_current_user_conditional),
    rag_service: RagService = Depends(get_rag_service)
) -> StatusCheckResponse:
    try:
        return await rag_service.check_indexing_status(request.file_ids, current_user.user_id)
    except Exception as e:
        logger.error("Failed to check status", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=QueryResponse)
async def query_content(
    request: QueryRequest,
    current_user: User = Depends(get_current_user_conditional),
    rag_service: RagService = Depends(get_rag_service)
) -> QueryResponse:
    try:
        filters_dict = None
        if request.filters:
            filters_dict = request.filters.model_dump(exclude_none=True)

        return await rag_service.query_content(
            query=request.query,
            user_id=current_user.user_id,
            filters=filters_dict,
            top_k=request.top_k,
            include_sources=request.include_sources
        )
    except Exception as e:
        logger.error("Failed to query content", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve_content(
    request: RetrieveRequest,
    current_user: User = Depends(get_current_user_conditional),
    rag_service: RagService = Depends(get_rag_service)
) -> RetrieveResponse:
    try:
        filters_dict = None
        if request.filters:
            filters_dict = request.filters.model_dump(exclude_none=True)

        return await rag_service.retrieve_content(
            query=request.query,
            user_id=current_user.user_id,
            filters=filters_dict,
            top_k=request.top_k,
            include_graph_context=request.include_graph_context
        )

    except Exception as e:
        logger.error("Failed to retrieve content", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/file", response_model=DeleteFileResponse)
async def delete_files(
    request: DeleteFileRequest,
    current_user: User = Depends(get_current_user_conditional),
    rag_service: RagService = Depends(get_rag_service)
) -> DeleteFileResponse:
    if "undefined" in request.file_ids:
        raise HTTPException(status_code=400, detail="Invalid file_id: 'undefined' found in request.")
    try:
        return await rag_service.delete_files(request.file_ids, current_user.user_id)
    except Exception as e:
        logger.error("Failed to delete files", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/collection", response_model=DeleteCollectionResponse)
async def delete_collection_data(
    request: DeleteCollectionRequest,
    current_user: User = Depends(get_current_user_conditional),
    rag_service: RagService = Depends(get_rag_service)
) -> DeleteCollectionResponse:
    try:
        return await rag_service.delete_collection(request.collection_id, current_user.user_id)

    except Exception as e:
        logger.error("Failed to delete collection data", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


