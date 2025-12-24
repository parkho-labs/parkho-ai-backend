import os
import uuid
import datetime
import structlog
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response, Query, Request
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user_conditional, get_db, get_file_storage, get_gcp_service
from src.services.file_storage import FileStorageService
from src.services.rag import core_rag_client as rag_client, CoreRagClient as RagClient
from src.models.user import User
from src.models.uploaded_file import UploadedFile
from src.api.v1.schemas import (
    RAGFileUploadResponse,
    RAGFilesListResponse,
    FileUploadUrlRequest,
    PresignedUrlResponse,
    FileConfirmRequest,
    FileViewResponse
)
from src.api.v1.constants import RAGStatus, RAGIndexingStatus, StorageConfig, ErrorConstants
from src.services.gcp_service import GCPService

logger = structlog.get_logger(__name__)

router = APIRouter()

@router.post("/upload-url", response_model=PresignedUrlResponse)
async def generate_upload_url(
    request: FileUploadUrlRequest,
    current_user: User = Depends(get_current_user_conditional),
    gcp_service: GCPService = Depends(get_gcp_service),
    file_storage: FileStorageService = Depends(get_file_storage)
):
    try:
        file_id = str(uuid.uuid4())
        filename = os.path.basename(request.filename) 
        blob_name = f"uploads/{current_user.user_id}/{file_id}/{filename}"
        
        url = gcp_service.generate_upload_signed_url(
            blob_name=blob_name,
            content_type=request.content_type
        )
        
        if not url:
             raise HTTPException(status_code=500, detail="Failed to generate upload URL")

        public_url = gcp_service.get_public_url(blob_name)
        
        file_storage.file_repo.create_file(
            file_id=file_id,
            filename=request.filename,
            file_path=public_url,
            file_size=request.file_size,
            content_type="FILE",
            file_type=request.content_type,
            indexing_status=RAGIndexingStatus.INDEXING_PENDING
        )

        return PresignedUrlResponse(
            upload_url=url,
            file_id=file_id,
            gcs_path=blob_name,
            cleanup_after=datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        )

    except Exception as e:
        logger.error("Failed to generate upload URL", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/confirm", response_model=RAGFileUploadResponse)
async def confirm_upload(
    request: FileConfirmRequest,
    current_user: User = Depends(get_current_user_conditional),
    gcp_service: GCPService = Depends(get_gcp_service),
    db: Session = Depends(get_db)
):
    try:
        file_record = db.query(UploadedFile).filter(UploadedFile.id == request.file_id).first()
        if not file_record:
            raise HTTPException(status_code=404, detail="File not found")
            
        if file_record.file_path and StorageConfig.GCS_DOMAIN in file_record.file_path:
            from urllib.parse import urlparse
            parsed = urlparse(file_record.file_path)
            path_parts = parsed.path.lstrip("/").split("/", 1)
            blob_name = path_parts[1] if len(path_parts) >= 2 else None
            
            if blob_name and not gcp_service.check_file_exists(blob_name):
                logger.error("File confirmation failed: Not found in GCS", file_id=file_record.id, blob_name=blob_name)
                raise HTTPException(status_code=400, detail="File verification failed: Not found in GCS bucket.")

        rag_status = "skipped"
        file_record.indexing_status = rag_status
        db.commit()

        return RAGFileUploadResponse(
            file_id=request.file_id,
            filename=file_record.filename,
            status=RAGStatus.SUCCESS,
            message=rag_message
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to confirm upload", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=RAGFileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    indexing: bool = Query(True),
    current_user: User = Depends(get_current_user_conditional),
    # RAG operations disabled for file uploads
    file_storage: FileStorageService = Depends(get_file_storage),
    db: Session = Depends(get_db)
) -> RAGFileUploadResponse:
    try:
        initial_status = RAGIndexingStatus.INDEXING_PENDING if indexing else "skipped"
        file_id = await file_storage.store_file(file, ttl_hours=24*365, indexing_status=initial_status)
        
        rag_status = "skipped"
        rag_message = "Indexing logic disabled"

        file_record = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
        if file_record:
            file_record.indexing_status = rag_status
            db.commit()

        return RAGFileUploadResponse(
            file_id=file_id,
            filename=file.filename,
            status=RAGStatus.SUCCESS,
            message=rag_message
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to upload file", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@router.get("/", response_model=RAGFilesListResponse)
async def list_all_files(
    current_user: User = Depends(get_current_user_conditional),
    # RAG operations disabled for file uploads
    db: Session = Depends(get_db),
    gcp_service: GCPService = Depends(get_gcp_service),
    file_storage: FileStorageService = Depends(get_file_storage)
) -> RAGFilesListResponse:
    try:
        files = db.query(UploadedFile).order_by(UploadedFile.upload_timestamp.desc()).all()
        
        valid_files = []

        for f in files:
            valid_files.append({
                "file_id": f.id,
                "filename": f.filename,
                "file_type": f.file_type or "unknown",
                "file_size": f.file_size,
                "upload_date": f.upload_timestamp.isoformat() if f.upload_timestamp else ""
            })
            
        return RAGFilesListResponse(
            status=RAGStatus.SUCCESS, 
            message="Files retrieved successfully", 
            body={"files": valid_files}
        )
    except Exception as e:
        logger.error("Failed to list files", error=str(e))
        return RAGFilesListResponse(status="ERROR", message=f"Failed to list files: {str(e)}", body={"files": []})


async def _process_delete_file(
    file_id: str,
    user_id: str,
    # RAG operations removed
    db: Session,
    file_storage: FileStorageService,
    gcp_service: GCPService
):
    """Helper to delete a single file."""
    try:
        # 1. Delete from RAG (Vector DB)
        # RAG delete operation disabled - use RAG endpoints directly
        
        # 2. Handle Storage Deletion (Local vs GCP)
        file_record = file_storage.get_file_metadata(file_id)
        
        if file_record:
            if file_record.file_path and StorageConfig.GCS_DOMAIN in file_record.file_path:
                from urllib.parse import urlparse
                parsed = urlparse(file_record.file_path)
                path_parts = parsed.path.lstrip("/").split("/", 1)
                blob_name = path_parts[1] if len(path_parts) >= 2 else None
                
                if blob_name:
                     gcp_service.delete_file(blob_name)

            # 3. Final cleanup (Local file from disk + DB record)
            file_storage.delete_file(file_id)
            
        return True
    except Exception as e:
        logger.error("Error deleting file during processing", file_id=file_id, error=str(e))
        return False


@router.delete("/{file_id}")
async def delete_file_from_rag(
    file_id: str,
    current_user: User = Depends(get_current_user_conditional),
    # RAG operations disabled for file uploads
    db: Session = Depends(get_db),
    file_storage: FileStorageService = Depends(get_file_storage),
    gcp_service: GCPService = Depends(get_gcp_service)
):
    if file_id == ErrorConstants.UNDEFINED_ID:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid file_id: {ErrorConstants.UNDEFINED_ID}."
        )

    try:
        success = await _process_delete_file(file_id, current_user.user_id, db, file_storage, gcp_service)
        if not success:
             raise HTTPException(status_code=500, detail="Failed to delete file")

        logger.info("File deleted from RAG, Storage and DB", file_id=file_id)
        # Construct response manually or use schema
        return {"status": "SUCCESS", "message": "File deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete file", error=str(e), file_id=file_id, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")


from src.api.v1.schemas import DeleteFileRequest, DeleteFileResponse

@router.post("/batch-delete", response_model=DeleteFileResponse)
async def batch_delete_files(
    request: DeleteFileRequest,
    current_user: User = Depends(get_current_user_conditional),
    # RAG operations disabled for file uploads
    db: Session = Depends(get_db),
    file_storage: FileStorageService = Depends(get_file_storage),
    gcp_service: GCPService = Depends(get_gcp_service)
):
    success_count = 0
    fail_count = 0
    
    for file_id in request.file_ids:
        if await _process_delete_file(file_id, current_user.user_id, db, file_storage, gcp_service):
            success_count += 1
        else:
            fail_count += 1
            
    return DeleteFileResponse(message=f"Deleted {success_count} files, failed {fail_count}")


@router.get("/{file_id}/view", response_model=FileViewResponse)
async def view_file(
    file_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_conditional),
    file_storage: FileStorageService = Depends(get_file_storage),
    gcp_service: GCPService = Depends(get_gcp_service)
):
    if file_id == ErrorConstants.UNDEFINED_ID:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid file_id: {ErrorConstants.UNDEFINED_ID}. This usually indicates a frontend state issue."
        )
    try:
        uploaded_file = file_storage.get_file_metadata(file_id)
        if not uploaded_file:
             logger.warning("View file request for non-existent file", file_id=file_id)
             raise HTTPException(status_code=404, detail="File not found")
        
        # 1. GCS Files (Private)
        blob_name = None
        if uploaded_file.file_path and StorageConfig.GCS_DOMAIN in uploaded_file.file_path:
             from urllib.parse import urlparse
             parsed = urlparse(uploaded_file.file_path)
             path_parts = parsed.path.lstrip("/").split("/", 1)
             if len(path_parts) >= 2:
                 blob_name = path_parts[1]
        
        # Fallback for relative paths in GCS
        if not blob_name and uploaded_file.file_path and not uploaded_file.file_path.startswith("http") and "uploads/" in uploaded_file.file_path:
             blob_name = uploaded_file.file_path
             
        if blob_name:
             logger.info("Attempting to generate signed URL for GCS file", file_id=file_id, blob_name=blob_name)
             signed_url = gcp_service.generate_download_signed_url(blob_name, expiration_minutes=60)
             if signed_url:
                 return FileViewResponse(
                     url=signed_url,
                     type="file",
                     content_type=uploaded_file.file_type or "application/octet-stream",
                     filename=uploaded_file.filename
                 )
             else:
                logger.error("GCS signed URL generation failed", file_id=file_id, blob_name=blob_name)
                # If it's a GCS file and we can't sign it, it's effectively a server error for the view operation
                raise HTTPException(status_code=500, detail="Failed to generate secure access to GCS file")


        # 2. External Links (YouTube, Web)
        if uploaded_file.content_type in ["YOUTUBE", "WEB"] or (uploaded_file.file_path and uploaded_file.file_path.startswith("http")):
             return FileViewResponse(
                 url=uploaded_file.file_path,
                 type="external",
                 content_type=uploaded_file.content_type,
                 filename=uploaded_file.filename
             )

        
        # 3. Local storage files
        if uploaded_file.file_path and StorageConfig.UPLOADS_DIR in uploaded_file.file_path:
             filename = os.path.basename(uploaded_file.file_path)
             base_url = str(request.base_url).rstrip("/")
             
             full_url = f"{base_url}/{StorageConfig.UPLOADS_DIR}/{filename}"
             logger.info("Serving local file via dynamic URL", file_id=file_id, url=full_url)
             
             return FileViewResponse(
                 url=full_url,
                 type="file",
                 content_type=uploaded_file.file_type or "application/pdf",
                 filename=uploaded_file.filename
             )

        # Final Fallback
        logger.warning("Unrecognized file path structure for view", file_id=file_id, path=uploaded_file.file_path)
        return FileViewResponse(
             url=uploaded_file.file_path,
             type="file",
             content_type=uploaded_file.file_type,
             filename=uploaded_file.filename
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate view URL", file_id=file_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to generate view URL")

