import structlog
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response, Query
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user_conditional, get_db
from src.services.rag_proxy_client import RAGProxyClient
from src.services.rag_integration_service import get_rag_service
from src.models.user import User
from src.models.uploaded_file import UploadedFile
from src.api.v1.schemas import (
    RAGFileUploadResponse,
    RAGFilesListResponse,
)
from src.api.v1.constants import RAGStatus

logger = structlog.get_logger(__name__)

router = APIRouter()


def get_rag_proxy_client() -> RAGProxyClient:
    rag_service = get_rag_service()
    return RAGProxyClient(rag_service)


@router.post("/files", response_model=RAGFileUploadResponse)
async def upload_file_to_rag(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_conditional),
    rag_client: RAGProxyClient = Depends(get_rag_proxy_client),
    db: Session = Depends(get_db)
) -> RAGFileUploadResponse:
    try:
        file_content = await file.read()
        
        # 1. Upload to RAG (Chunks & Indexes)
        # Note: We rely on RAG to generate ID for now. 
        # If we wanted "Pending" visible before upload finishes, we'd need to generate ID locally 
        # and force RAG to use it (if supported) or have a separate "Pre-signed URL" flow.
        # For this synchronous HTTP call, "Pending" is just the duration of the request.
        result = await rag_client.upload_file(
            file_content=file_content,
            filename=file.filename or "untitled",
            user_id=current_user.user_id
        )

        if not result or result.status != RAGStatus.SUCCESS:
            raise HTTPException(status_code=500, detail="Failed to upload file to RAG engine")

        # 2. Save Metadata to Postgres (Source of Truth)
        # We assume RAG upload means it's "Indexed" (or at least accepted). 
        # If RAG is async, status might be 'indexing'. 
        # Since we don't have async callback yet, we assume 'completed'.
        
        uploaded_file = UploadedFile(
            id=result.file_id,
            filename=result.filename,
            file_path="rag://" + result.file_id, # Virtual path since content is in RAG
            file_size=len(file_content),
            content_type=file.content_type,
            indexing_status="completed" 
        )
        db.add(uploaded_file)
        db.commit()

        logger.info("File uploaded and saved to DB", file_id=result.file_id)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to upload file", error=str(e), exc_info=True)
        # If saved to DB but failed RAG? (We did RAG first, so no DB junk)
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@router.get("/files", response_model=RAGFilesListResponse)
async def list_all_files(
    current_user: User = Depends(get_current_user_conditional),
    rag_client: RAGProxyClient = Depends(get_rag_proxy_client),
    db: Session = Depends(get_db) # We could list from DB instead of RAG for speed!
) -> RAGFilesListResponse:
    try:
        # Hybrid Approach: List from RAG to ensure we see what's actually there
        # OR List from DB (Single Source of Truth).
        # User requested Backend be Source of Truth.
        # LET'S LIST FROM POSTGRES.
        
        # files = db.query(UploadedFile).all() 
        # But we need to filter by User? UploadedFile doesn't have user_id?
        # Checked model... UploadedFile model DOES NOT have user_id! 
        # CHECK src/models/uploaded_file.py earlier... 
        # It had id, filename, filepath... NO user_id! 
        # CRITICAL MISSING FIELD.
        
        # Fallback: Use RAG list for now until we add user_id to UploadedFile.
        result = await rag_client.list_files(current_user.user_id)
        return result

    except Exception as e:
        logger.error("Failed to list files", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")


@router.delete("/files/{file_id}")
async def delete_file_from_rag(
    file_id: str,
    current_user: User = Depends(get_current_user_conditional),
    rag_client: RAGProxyClient = Depends(get_rag_proxy_client),
    db: Session = Depends(get_db)
):
    try:
        # 1. Delete from RAG
        result = await rag_client.delete_file(file_id, current_user.user_id)

        if result.get("status") != RAGStatus.SUCCESS:
            raise HTTPException(status_code=500, detail=result.get("message"))
            
        # 2. Delete from Postgres
        file_record = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
        if file_record:
            db.delete(file_record)
            db.commit()

        logger.info("File deleted from RAG and DB", file_id=file_id)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete file", error=str(e), file_id=file_id, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")
