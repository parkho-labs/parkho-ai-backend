import structlog
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response, Query

from src.api.dependencies import get_current_user_conditional
from src.services.rag_proxy_client import RAGProxyClient
from src.services.rag_integration_service import get_rag_service
from src.models.user import User
from src.api.v1.schemas import (
    RAGFileUploadResponse,
    RAGCollectionCreateRequest,
    RAGCollectionResponse,
    RAGLinkContentRequest,
    RAGLinkContentResponse,
    RAGUnlinkContentRequest,
    RAGCollectionFilesResponse,
    RAGFilesListResponse,
    RAGQueryRequest,
    RAGQueryResponse,
    RAGEmbeddingsResponse
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
    rag_client: RAGProxyClient = Depends(get_rag_proxy_client)
) -> RAGFileUploadResponse:
    try:
        file_content = await file.read()

        result = await rag_client.upload_file(
            file_content=file_content,
            filename=file.filename or "untitled",
            user_id=current_user.user_id
        )

        if not result:
            raise HTTPException(status_code=500, detail="Failed to upload file to RAG engine")

        logger.info("File uploaded to RAG", file_id=result.file_id, filename=result.filename)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to upload file to RAG", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@router.get("/files", response_model=RAGFilesListResponse)
async def list_all_files(
    current_user: User = Depends(get_current_user_conditional),
    rag_client: RAGProxyClient = Depends(get_rag_proxy_client)
) -> RAGFilesListResponse:
    try:
        result = await rag_client.list_files(current_user.user_id)

        logger.info("Files listed from RAG", user_id=current_user.user_id)
        return result

    except Exception as e:
        logger.error("Failed to list files from RAG", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")


@router.delete("/files/{file_id}")
async def delete_file_from_rag(
    file_id: str,
    current_user: User = Depends(get_current_user_conditional),
    rag_client: RAGProxyClient = Depends(get_rag_proxy_client)
):
    try:
        result = await rag_client.delete_file(file_id, current_user.user_id)

        if result.get("status") != RAGStatus.SUCCESS:
            raise HTTPException(status_code=500, detail=result.get("message"))

        logger.info("File deleted from RAG", file_id=file_id)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete file from RAG", error=str(e), file_id=file_id, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")


@router.post("/collections", response_model=RAGCollectionResponse)
async def create_collection(
    request: RAGCollectionCreateRequest,
    current_user: User = Depends(get_current_user_conditional),
    rag_client: RAGProxyClient = Depends(get_rag_proxy_client)
) -> RAGCollectionResponse:
    try:
        result = await rag_client.create_collection(
            name=request.name,
            user_id=current_user.user_id
        )

        if result.status != RAGStatus.SUCCESS:
            raise HTTPException(status_code=500, detail=result.message)

        logger.info("Collection created in RAG", collection_name=request.name)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create collection in RAG", error=str(e), collection_name=request.name, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create collection: {str(e)}")


@router.get("/collections", response_model=RAGCollectionResponse)
async def list_collections(
    current_user: User = Depends(get_current_user_conditional),
    rag_client: RAGProxyClient = Depends(get_rag_proxy_client)
) -> RAGCollectionResponse:
    try:
        result = await rag_client.list_collections(current_user.user_id)

        logger.info("Collections listed from RAG", user_id=current_user.user_id)
        return result

    except Exception as e:
        logger.error("Failed to list collections from RAG", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list collections: {str(e)}")


@router.post("/collections/{collection_name}/link", response_model=List[RAGLinkContentResponse])
async def link_content_to_collection(
    collection_name: str,
    request: RAGLinkContentRequest,
    response: Response,
    current_user: User = Depends(get_current_user_conditional),
    rag_client: RAGProxyClient = Depends(get_rag_proxy_client)
) -> List[RAGLinkContentResponse]:
    try:
        results = await rag_client.link_content(
            collection_name=collection_name,
            content_items=request.content_items,
            user_id=current_user.user_id
        )

        if any(r.status_code != 200 for r in results):
            response.status_code = 207

        logger.info("Content linked to collection", collection=collection_name, items_count=len(results))
        return results

    except Exception as e:
        logger.error("Failed to link content to collection", error=str(e), collection=collection_name, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to link content: {str(e)}")


@router.post("/collections/{collection_name}/unlink", response_model=List[RAGLinkContentResponse])
async def unlink_content_from_collection(
    collection_name: str,
    request: RAGUnlinkContentRequest,
    response: Response,
    current_user: User = Depends(get_current_user_conditional),
    rag_client: RAGProxyClient = Depends(get_rag_proxy_client)
) -> List[RAGLinkContentResponse]:
    try:
        results = await rag_client.unlink_content(
            collection_name=collection_name,
            file_ids=request.file_ids,
            user_id=current_user.user_id
        )

        if any(r.status_code != 200 for r in results):
            response.status_code = 207

        logger.info("Content unlinked from collection", collection=collection_name, items_count=len(results))
        return results

    except Exception as e:
        logger.error("Failed to unlink content from collection", error=str(e), collection=collection_name, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to unlink content: {str(e)}")


@router.get("/collections/{collection_name}/files", response_model=RAGCollectionFilesResponse)
async def get_collection_files(
    collection_name: str,
    current_user: User = Depends(get_current_user_conditional),
    rag_client: RAGProxyClient = Depends(get_rag_proxy_client)
) -> RAGCollectionFilesResponse:
    try:
        result = await rag_client.get_collection_files(
            collection_name=collection_name,
            user_id=current_user.user_id
        )

        logger.info("Collection files retrieved", collection=collection_name)
        return result

    except Exception as e:
        logger.error("Failed to get collection files", error=str(e), collection=collection_name, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get collection files: {str(e)}")


@router.post("/collections/{collection_name}/query", response_model=RAGQueryResponse)
async def query_collection(
    collection_name: str,
    request: RAGQueryRequest,
    current_user: User = Depends(get_current_user_conditional),
    rag_client: RAGProxyClient = Depends(get_rag_proxy_client)
) -> RAGQueryResponse:
    try:
        result = await rag_client.query_collection(
            collection_name=collection_name,
            query=request.query,
            user_id=current_user.user_id,
            enable_critic=request.enable_critic
        )

        logger.info("Collection queried", collection=collection_name, user_id=current_user.user_id)
        return result

    except Exception as e:
        logger.error("Failed to query collection", error=str(e), collection=collection_name, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to query collection: {str(e)}")


@router.get("/collections/{collection_name}/embeddings", response_model=RAGEmbeddingsResponse)
async def get_embeddings(
    collection_name: str,
    limit: int = Query(default=100, le=500),
    current_user: User = Depends(get_current_user_conditional),
    rag_client: RAGProxyClient = Depends(get_rag_proxy_client)
) -> RAGEmbeddingsResponse:
    try:
        result = await rag_client.get_embeddings(
            collection_name=collection_name,
            user_id=current_user.user_id,
            limit=limit
        )

        logger.info("Embeddings retrieved", collection=collection_name, user_id=current_user.user_id, limit=limit)
        return result

    except Exception as e:
        logger.error("Failed to get embeddings", error=str(e), collection=collection_name, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get embeddings: {str(e)}")
