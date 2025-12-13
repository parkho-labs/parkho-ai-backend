import structlog
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session

from src.api.dependencies import get_db, get_current_user_conditional
from src.models.user import User
from src.services.collection_service import CollectionService
from src.api.v1.schemas import (
    RAGCollectionResponse, RAGCollectionCreateRequest, RAGLinkContentResponse, RAGQueryResponse,
    RAGCollectionFilesResponse, RAGFileDetail
)
from src.api.v1.constants import RAGStatus

logger = structlog.get_logger(__name__)

router = APIRouter()

def get_collection_service(db: Session = Depends(get_db)):
    return CollectionService(db)

@router.post("", response_model=RAGCollectionResponse)
async def create_collection(
    request: RAGCollectionCreateRequest,
    current_user: User = Depends(get_current_user_conditional),
    service: CollectionService = Depends(get_collection_service)
):
    try:
        collection = await service.create_collection(current_user.user_id, request.name)
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
        # Transform to schema
        cols_data = [
            {"id": c.id, "name": c.name, "file_count": len(c.files), "created_at": str(c.created_at)} 
            for c in collections
        ]
        return RAGCollectionResponse(
            status=RAGStatus.SUCCESS,
            body={"collections": cols_data}
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
    await service.delete_collection(current_user.user_id, collection_id)
    return {"status": "SUCCESS", "message": "Collection deleted"}

@router.post("/{collection_id}/link")
async def link_files(
    collection_id: str,
    file_ids: List[str] = Body(..., embed=True),
    current_user: User = Depends(get_current_user_conditional),
    service: CollectionService = Depends(get_collection_service)
):
    linked = await service.link_files(current_user.user_id, collection_id, file_ids)
    return {"status": "SUCCESS", "linked_files": linked}

@router.post("/{collection_id}/unlink")
async def unlink_files(
    collection_id: str,
    file_ids: List[str] = Body(..., embed=True),
    current_user: User = Depends(get_current_user_conditional),
    service: CollectionService = Depends(get_collection_service)
):
    unlinked = await service.unlink_files(current_user.user_id, collection_id, file_ids)
    return {"status": "SUCCESS", "unlinked_files": unlinked}

@router.get("/{collection_id}/files", response_model=RAGCollectionFilesResponse)
async def get_collection_files(
    collection_id: str,
    current_user: User = Depends(get_current_user_conditional),
    service: CollectionService = Depends(get_collection_service)
):
    collection = await service.get_collection(collection_id)
    if not collection or collection.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    files = [
        RAGFileDetail(
            file_id=f.id,
            filename=f.filename,
            file_size=f.file_size,
            upload_date=str(f.upload_timestamp)
        ) for f in collection.files
    ]
    return RAGCollectionFilesResponse(
        status=RAGStatus.SUCCESS,
        body={"files": files}
    )

@router.post("/{collection_id}/query", response_model=RAGQueryResponse)
async def query_collection(
    collection_id: str,
    query: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user_conditional),
    service: CollectionService = Depends(get_collection_service)
):
    result = await service.query_collection(current_user.user_id, collection_id, query)
    return RAGQueryResponse(
        status=RAGStatus.SUCCESS,
        body=result
    )
