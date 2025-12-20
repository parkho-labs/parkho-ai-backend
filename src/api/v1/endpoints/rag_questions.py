from typing import Optional, List
from fastapi import APIRouter, HTTPException
from ..schemas import (
    RagQuestionGenerationRequest,
    RagQuestionGenerationResponse,
    ContentStatsRequest,
    ContentStatsResponse,
    SupportedTypesResponse,
    ContentValidationRequest,
    ContentValidationResponse,
    HealthCheckResponse
)
from typing import Dict, Any
from ....services.rag_question_generator_service import rag_question_generator
from ....exceptions import ParkhoError

router = APIRouter()


@router.post("/generate", response_model=RagQuestionGenerationResponse)
async def generate_questions(request: RagQuestionGenerationRequest):
    try:
        return await rag_question_generator.generate_questions(request)
    except ParkhoError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.get("/content-stats", response_model=ContentStatsResponse)
async def get_content_stats(collection_ids: Optional[str] = None):
    try:
        collection_list = collection_ids.split(",") if collection_ids else None
        request = ContentStatsRequest(collection_ids=collection_list)
        return await rag_question_generator.get_content_stats(request)
    except ParkhoError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.get("/supported-types", response_model=SupportedTypesResponse)
async def get_supported_types():
    try:
        return await rag_question_generator.get_supported_types()
    except ParkhoError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.post("/validate-content", response_model=ContentValidationResponse)
async def validate_content(request: ContentValidationRequest):
    try:
        return await rag_question_generator.validate_content(request)
    except ParkhoError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    try:
        return await rag_question_generator.health_check()
    except ParkhoError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")