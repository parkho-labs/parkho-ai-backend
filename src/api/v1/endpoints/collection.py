import structlog
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Body

from src.api.dependencies import get_current_user_conditional, get_collection_service
from src.services.collection_service import CollectionService
from src.models.user import User
from src.api.v1.schemas import (
    RAGCollectionCreateRequest,
    RAGCollectionResponse,
    RAGCollectionInfo,
    RAGQueryRequest,
    RAGQueryResponse,
    RAGCollectionFilesResponse,
    RAGFileDetail,
    RAGLinkContentRequest # We might just use Body directly but let's see
)
from src.api.v1.constants import RAGStatus

logger = structlog.get_logger(__name__)

router = APIRouter()

@router.post("", response_model=RAGCollectionResponse)
async def create_collection(
    request: RAGCollectionCreateRequest,
    current_user: User = Depends(get_current_user_conditional),
    service: CollectionService = Depends(get_collection_service)
):
    try:
        collection = await service.create_collection(current_user.user_id, request.name)
        
        # Use simple dict for body as allowed by flexible schema now
        # Or construct proper RAGCollectionInfo if it was a list
        return RAGCollectionResponse(
            status=RAGStatus.SUCCESS,
            message="Collection created successfully",
            body={"id": collection.id, "name": collection.name}
        )
    except Exception as e:
        logger.error("Failed to create collection", error=str(e))
        raise HTTPException(status_code=500, detail="An unexpected error occurred while creating the collection.")

@router.get("", response_model=RAGCollectionResponse)
async def list_collections(
    current_user: User = Depends(get_current_user_conditional),
    service: CollectionService = Depends(get_collection_service)
):
    try:
        collections = await service.list_collections(current_user.user_id)
        
        collections_data = [
            RAGCollectionInfo(
                id=c.id,
                name=c.name,
                created_at=c.created_at.isoformat() if c.created_at else "",
                file_count=len(c.files)
            ) for c in collections
        ]
        
        return RAGCollectionResponse(
            status=RAGStatus.SUCCESS,
            message="Collections listed successfully",
            body={"collections": collections_data}
        )
    except Exception as e:
        logger.error("Failed to list collections", error=str(e))
        raise HTTPException(status_code=500, detail="An unexpected error occurred while listing collections.")

@router.delete("/{collection_id}")
async def delete_collection(
    collection_id: str,
    current_user: User = Depends(get_current_user_conditional),
    service: CollectionService = Depends(get_collection_service)
):
    try:
        success = await service.delete_collection(current_user.user_id, collection_id)
        if success:
            return {"status": "SUCCESS", "message": "Collection deleted"}
        else:
             raise HTTPException(status_code=404, detail="Collection not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete collection", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete collection.")

@router.post("/{collection_id}/link", response_model=RAGCollectionResponse)
async def link_files(
    collection_id: str,
    # Accept standard Body request, mapping file_ids
    file_ids: List[str] = Body(..., embed=True), 
    current_user: User = Depends(get_current_user_conditional),
    service: CollectionService = Depends(get_collection_service)
):
    try:
        linked = await service.link_files(current_user.user_id, collection_id, file_ids)
        
        return RAGCollectionResponse(
            status=RAGStatus.SUCCESS, 
            message=f"{len(linked)} files linked successfully.",
            body={"linked_files": linked}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to link files", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{collection_id}/unlink", response_model=RAGCollectionResponse)
async def unlink_files(
    collection_id: str,
    file_ids: List[str] = Body(..., embed=True),
    current_user: User = Depends(get_current_user_conditional),
    service: CollectionService = Depends(get_collection_service)
):
    try:
        unlinked = await service.unlink_files(current_user.user_id, collection_id, file_ids)
        
        return RAGCollectionResponse(
            status=RAGStatus.SUCCESS, 
            message=f"{len(unlinked)} files unlinked successfully.",
            body={"unlinked_files": unlinked}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to unlink files", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{collection_id}/files", response_model=RAGCollectionFilesResponse)
async def get_collection_files(
    collection_id: str,
    current_user: User = Depends(get_current_user_conditional),
    service: CollectionService = Depends(get_collection_service)
):
    try:
        files = await service.get_collection_files(current_user.user_id, collection_id)
        
        # files is list of dicts from service
        mapped_files = [RAGFileDetail(**f) for f in files]
        
        return RAGCollectionFilesResponse(
            status=RAGStatus.SUCCESS,
            message="Files retrieved successfully",
            body={"files": mapped_files}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get collection files", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{collection_id}/query", response_model=RAGQueryResponse)
async def query_collection(
    collection_id: str,
    request: RAGQueryRequest,
    current_user: User = Depends(get_current_user_conditional),
    service: CollectionService = Depends(get_collection_service)
):
    try:
        result = await service.query_collection(current_user.user_id, collection_id, request.query)
        
        return RAGQueryResponse(
            status=RAGStatus.SUCCESS,
            message="Query processed successfully",
            body=result
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to query collection", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
