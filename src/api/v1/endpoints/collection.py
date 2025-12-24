import structlog
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
import uuid

from src.api.dependencies import get_current_user_conditional, get_collection_service, get_gcp_service, get_file_storage, get_db
from src.services.collection_service import CollectionService
from src.services.gcp_service import GCPService
from src.services.file_storage import FileStorageService
from src.models.user import User
from src.models.uploaded_file import UploadedFile
from src.api.v1.schemas import (
    RAGCollectionCreateRequest,
    RAGCollectionResponse,
    RAGCollectionInfo,
    RAGQueryRequest,
    RAGQueryResponse,
    RAGCollectionFilesResponse,
    RAGFileDetail,
    RAGLinkContentRequest,
    FileUploadUrlRequest,
    PresignedUrlResponse,
    FileConfirmRequest,
    RAGFileUploadResponse,
    CollectionChatRequest,
    CollectionSummaryResponse,
    QueryResponse,
    QuestionGenerationResponse,
    CollectionStatusResponse
)
from src.api.v1.constants import RAGStatus, RAGIndexingStatus, StorageConfig
import datetime

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

@router.post("/{collection_id}/upload-url", response_model=PresignedUrlResponse)
async def generate_collection_upload_url(
    collection_id: str,
    request: FileUploadUrlRequest,
    current_user: User = Depends(get_current_user_conditional),
    service: CollectionService = Depends(get_collection_service),
    gcp_service: GCPService = Depends(get_gcp_service),
    file_storage: FileStorageService = Depends(get_file_storage)
):
    """Generate presigned upload URL for file that will be auto-linked to collection"""
    try:
        # Verify collection exists and user has access
        try:
            collections = await service.list_collections(current_user.user_id)
            collection_exists = any(c.id == collection_id for c in collections)
            if not collection_exists:
                raise HTTPException(status_code=404, detail="Collection not found")
        except Exception as e:
            logger.error("Failed to verify collection access", collection_id=collection_id, error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to verify collection: {str(e)}")

        # Generate file ID and presigned URL (same as /files/upload-url)
        file_id = str(uuid.uuid4())
        filename = request.filename
        blob_name = f"uploads/{current_user.user_id}/{file_id}/{filename}"

        try:
            url = gcp_service.generate_upload_signed_url(
                blob_name=blob_name,
                content_type=request.content_type
            )
        except Exception as e:
            logger.error("GCP URL generation raised exception", error=str(e))
            url = None

        if not url:
            # Check if GCP credentials or bucket might be the issue
            if not gcp_service.client:
                detail = "GCP Client not initialized. Check server configuration."
            else:
                detail = "Failed to generate upload URL. Check GCS bucket access."
            raise HTTPException(status_code=500, detail=detail)

        public_url = gcp_service.get_public_url(blob_name)

        # Create file record (same as /files/upload-url)
        try:
            file_storage.file_repo.create_file(
                file_id=file_id,
                filename=request.filename,
                file_path=public_url,
                file_size=request.file_size,
                content_type="FILE",
                file_type=request.content_type,
                indexing_status=RAGIndexingStatus.INDEXING_PENDING.value
            )
        except Exception as e:
            logger.error("Failed to create file record in DB", error=str(e))
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

        return PresignedUrlResponse(
            upload_url=url,
            file_id=file_id,
            gcs_path=blob_name,
            cleanup_after=datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate collection upload URL", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{collection_id}/confirm", response_model=RAGFileUploadResponse)
async def confirm_collection_upload(
    collection_id: str,
    request: FileConfirmRequest,
    current_user: User = Depends(get_current_user_conditional),
    service: CollectionService = Depends(get_collection_service),
    gcp_service: GCPService = Depends(get_gcp_service),
    db: Session = Depends(get_db)
):
    """Confirm file upload and automatically link to collection"""
    try:
        # Verify collection exists and user has access
        collections = await service.list_collections(current_user.user_id)
        collection_exists = any(c.id == collection_id for c in collections)
        if not collection_exists:
            raise HTTPException(status_code=404, detail="Collection not found")

        # Get file record
        file_record = db.query(UploadedFile).filter(UploadedFile.id == request.file_id).first()
        if not file_record:
            raise HTTPException(status_code=404, detail="File not found")

        # Verify file in GCS (same validation as /files/confirm)
        if file_record.file_path and StorageConfig.GCS_DOMAIN in file_record.file_path:
            from urllib.parse import urlparse
            parsed = urlparse(file_record.file_path)
            path_parts = parsed.path.lstrip("/").split("/", 1)
            blob_name = path_parts[1] if len(path_parts) >= 2 else None

            if blob_name and not gcp_service.check_file_exists(blob_name):
                logger.error("File confirmation failed: Not found in GCS", file_id=file_record.id, blob_name=blob_name)
                raise HTTPException(status_code=400, detail="File verification failed: Not found in GCS bucket.")

            # Trigger RAG Indexing via Service (centralized logic with retries)
            gcs_uri = gcp_service.get_gcs_uri(blob_name)
            rag_status = await service.trigger_indexing(
                user_id=current_user.user_id,
                file_id=request.file_id,
                gcs_uri=gcs_uri,
                collection_id=collection_id
            )
        else:
            rag_status = "confirmed"

        # Auto-link to collection in local DB
        try:
            linked = await service.link_files(current_user.user_id, collection_id, [request.file_id])
            logger.info("Auto-linked file to collection", file_id=request.file_id, collection_id=collection_id)
        except Exception as e:
            logger.warning("Failed to auto-link file to collection", file_id=request.file_id, collection_id=collection_id, error=str(e))

        return RAGFileUploadResponse(
            file_id=request.file_id,
            filename=file_record.filename,
            status=RAGStatus.SUCCESS,
            message=f"File uploaded successfully. Linking status: {rag_status}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to confirm collection upload", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{collection_id}/status", response_model=CollectionStatusResponse)
async def get_collection_status(
    collection_id: str,
    current_user: User = Depends(get_current_user_conditional),
    service: CollectionService = Depends(get_collection_service)
):
    """Get indexing status for all files in a collection"""
    try:
        collections = await service.list_collections(current_user.user_id)
        collection = next((c for c in collections if c.id == collection_id), None)
        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found")
        
        files = await service.get_collection_files(current_user.user_id, collection_id)
        
        return CollectionStatusResponse(
            collection_id=collection_id,
            name=collection.name,
            files=[RAGFileDetail(**f) for f in files]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get collection status", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{collection_id}/files/{file_id}/index")
async def manual_trigger_indexing(
    collection_id: str,
    file_id: str,
    current_user: User = Depends(get_current_user_conditional),
    service: CollectionService = Depends(get_collection_service),
    gcp_service: GCPService = Depends(get_gcp_service),
    db: Session = Depends(get_db)
):
    """Manually trigger RAG indexing for a file (useful for retries)"""
    try:
        # Verify collection ownership
        collections = await service.list_collections(current_user.user_id)
        if not any(c.id == collection_id for c in collections):
             raise HTTPException(status_code=404, detail="Collection not found")

        file_record = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
        if not file_record:
            raise HTTPException(status_code=404, detail="File not found")

        # Extract blob name for GCS URI
        from urllib.parse import urlparse
        parsed = urlparse(file_record.file_path)
        path_parts = parsed.path.lstrip("/").split("/", 1)
        blob_name = path_parts[1] if len(path_parts) >= 2 else None
        
        if not blob_name:
             raise HTTPException(status_code=400, detail="File is not stored in GCS, cannot index.")

        gcs_uri = gcp_service.get_gcs_uri(blob_name)
        status = await service.trigger_indexing(current_user.user_id, file_id, gcs_uri, collection_id)
        
        return {"status": "success", "indexing_status": status, "message": f"Indexing re-triggered. New status: {status}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Manual indexing trigger failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{collection_id}/files/{file_id}")
async def delete_file_from_collection(
    collection_id: str,
    file_id: str,
    current_user: User = Depends(get_current_user_conditional),
    service: CollectionService = Depends(get_collection_service),
    db: Session = Depends(get_db)
):
    """Delete file from collection (auto-unlink) and optionally delete file entirely if not used elsewhere"""
    try:
        # Verify collection exists and user has access
        collections = await service.list_collections(current_user.user_id)
        collection_exists = any(c.id == collection_id for c in collections)
        if not collection_exists:
            raise HTTPException(status_code=404, detail="Collection not found")

        # Verify file exists
        file_record = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
        if not file_record:
            raise HTTPException(status_code=404, detail="File not found")

        # Unlink from collection
        try:
            unlinked = await service.unlink_files(current_user.user_id, collection_id, [file_id])
            if not unlinked:
                raise HTTPException(status_code=404, detail="File not found in collection")
        except Exception as e:
            logger.error("Failed to unlink file from collection", file_id=file_id, collection_id=collection_id, error=str(e))
            raise HTTPException(status_code=500, detail="Failed to remove file from collection")

        # Check if file is used in other collections
        remaining_collections = len(file_record.collections)

        return {
            "status": RAGStatus.SUCCESS,
            "message": f"File removed from collection successfully",
            "file_id": file_id,
            "collection_id": collection_id,
            "file_deleted_entirely": False,
            "remaining_collections": remaining_collections
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete file from collection", error=str(e))
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

@router.post("/{collection_id}/chat", response_model=QueryResponse)
async def chat_with_collection(
    collection_id: str,
    request: CollectionChatRequest,
    current_user: User = Depends(get_current_user_conditional),
    service: CollectionService = Depends(get_collection_service)
):
    """Restricted-context chat with collection"""
    try:
        result = await service.chat_collection(
            current_user.user_id, 
            collection_id, 
            request.query,
            request.answer_style,
            request.max_chunks
        )
        return QueryResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Collection chat failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{collection_id}/summary", response_model=CollectionSummaryResponse)
async def summarize_collection(
    collection_id: str,
    current_user: User = Depends(get_current_user_conditional),
    service: CollectionService = Depends(get_collection_service)
):
    """Professional & Educational summary of collection content"""
    try:
        result = await service.summary_collection(current_user.user_id, collection_id)
        return CollectionSummaryResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Collection summary failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{collection_id}/quiz")
async def generate_collection_quiz(
    collection_id: str,
    num_questions: int = 10,
    difficulty: str = "moderate",
    current_user: User = Depends(get_current_user_conditional),
    service: CollectionService = Depends(get_collection_service)
):
    """Generate quiz from collection content with mixed question types"""
    try:
        result = await service.quiz_collection(current_user.user_id, collection_id, num_questions, difficulty)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Collection quiz generation failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{collection_id}/files/{file_id}/chunks")
async def get_file_chunks(
    collection_id: str,
    file_id: str,
    current_user: User = Depends(get_current_user_conditional),
    service: CollectionService = Depends(get_collection_service)
):
    """Inspect raw RAG chunks for a file (Debug)"""
    try:
        # Verify collection ownership
        collections = await service.list_collections(current_user.user_id)
        if not any(c.id == collection_id for c in collections):
             raise HTTPException(status_code=404, detail="Collection not found")
             
        chunks = await service.get_file_chunks(current_user.user_id, file_id)
        return {"file_id": file_id, "chunk_count": len(chunks), "chunks": chunks}
    except Exception as e:
        logger.error("Failed to fetch file chunks", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
