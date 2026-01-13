"""
Legal Agents API Endpoints

Provides SSE streaming chat with multiple agent personalities.
Endpoint: /api/v1/legal/agents/...
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from typing import List

from src.api.dependencies import get_legal_user_id_required
from src.ask_assistant.schemas.requests import AgentChatRequest
from src.ask_assistant.schemas.responses import (
    AgentTypesResponse,
    AgentTypeInfo,
    StylesResponse,
    StyleInfo,
    ModelsResponse,
    ModelInfo,
    AgentChatResponse
)
from src.ask_assistant.models.enums import AgentType, ResponseStyle, LLMModel
from src.ask_assistant.services.agent_manager import get_agent_manager
from src.ask_assistant.prompts.agent_prompts import AGENT_METADATA
from src.ask_assistant.prompts.style_prompts import STYLE_METADATA

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/agents/ask")
async def ask_agent_stream(
    request: AgentChatRequest,
    user_id: str = Depends(get_legal_user_id_required)
):
    """
    Chat with an AI agent using Server-Sent Events (SSE) streaming.
    
    **Endpoint:** POST /api/v1/legal/agents/ask
    
    **Headers Required:**
        - x-user-id: User identifier
    
    **Request Body:**
        - question: Your question (required)
        - agent_type: civilian, judge, or advocate (default: civilian)
        - style: concise, detailed, learning, or professional (default: detailed)
        - model: gemini-2.0-flash, gemini-1.5-pro, gpt-4o-mini, gpt-4o
        - memory_enabled: Save conversation history (default: true)
        - knowledge_base_enabled: Query legal documents (default: true)
        - collection_ids: User collections to add to system collections (null/[] = only system collections)
        - conversation_id: Continue existing conversation
        - temperature: LLM temperature 0.0-2.0 (default: 0.7)
        - max_tokens: Maximum response tokens 1-4096 (default: 2048)
        - file_contents: Extracted file contents for analysis
    
    **Response:**
        Server-Sent Events stream with chunks:
        - type: "thinking" - Agent's reasoning process
        - type: "answer" - Main response content
        - type: "source" - Citation/source information
        - type: "done" - Stream completion with metadata
        - type: "error" - Error message if something fails
    """
    logger.info(
        "Agent chat request",
        user_id=user_id,
        agent_type=request.agent_type.value,
        style=request.style.value
    )
    
    agent_manager = get_agent_manager()
    
    async def generate():
        """Generator for SSE stream"""
        async for chunk in agent_manager.chat_stream(
            user_id=user_id,
            question=request.question,
            agent_type=request.agent_type,
            style=request.style,
            model=request.model,
            memory_enabled=request.memory_enabled,
            knowledge_base_enabled=request.knowledge_base_enabled,
            collection_ids=request.collection_ids,
            conversation_id=request.conversation_id,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            file_contents=request.file_contents
        ):
            yield chunk.to_sse()
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.post("/agents/ask-sync", response_model=AgentChatResponse)
async def ask_agent_sync(
    request: AgentChatRequest,
    user_id: str = Depends(get_legal_user_id_required)
):
    """
    Chat with an AI agent (non-streaming).
    
    Returns complete response in a single JSON object.
    Use /agents/ask for streaming responses.
    """
    logger.info(
        "Agent chat request (sync)",
        user_id=user_id,
        agent_type=request.agent_type.value
    )
    
    agent_manager = get_agent_manager()
    
    result = await agent_manager.chat(
        user_id=user_id,
        question=request.question,
        agent_type=request.agent_type,
        style=request.style,
        model=request.model,
        memory_enabled=request.memory_enabled,
        knowledge_base_enabled=request.knowledge_base_enabled,
        collection_ids=request.collection_ids,
        conversation_id=request.conversation_id,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        file_contents=request.file_contents
    )
    
    return AgentChatResponse(
        answer=result["answer"],
        thinking=result.get("thinking"),
        sources=[],  # Simplified for sync response
        agent_type=request.agent_type,
        style=request.style,
        model=request.model,
        conversation_id=result.get("conversation_id", "")
    )


@router.get("/agents/types", response_model=AgentTypesResponse)
async def get_agent_types():
    """
    List available agent types/personalities.
    
    **Endpoint:** GET /api/v1/legal/agents/types
    
    Returns list of available agents with their descriptions.
    """
    agents = [
        AgentTypeInfo(
            id=agent_type.value,
            name=AGENT_METADATA[agent_type]["name"],
            description=AGENT_METADATA[agent_type]["description"]
        )
        for agent_type in AgentType
    ]
    return AgentTypesResponse(agents=agents)


@router.get("/agents/styles", response_model=StylesResponse)
async def get_response_styles():
    """
    List available response styles.
    
    **Endpoint:** GET /api/v1/legal/agents/styles
    
    Returns list of available styles with their descriptions.
    """
    styles = [
        StyleInfo(
            id=style.value,
            name=STYLE_METADATA[style]["name"],
            description=STYLE_METADATA[style]["description"]
        )
        for style in ResponseStyle
    ]
    return StylesResponse(styles=styles)


@router.get("/agents/models", response_model=ModelsResponse)
async def get_available_models():
    """
    List available LLM models.
    
    **Endpoint:** GET /api/v1/legal/agents/models
    
    Returns list of available models with their providers.
    """
    models = [
        ModelInfo(
            id=model.value,
            name=model.value,
            provider=LLMModel.get_provider(model)
        )
        for model in LLMModel
    ]
    return ModelsResponse(models=models)


@router.get("/agents/conversation/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    user_id: str = Depends(get_legal_user_id_required)
):
    """
    Get conversation history.
    
    **Endpoint:** GET /api/v1/legal/agents/conversation/{conversation_id}
    """
    agent_manager = get_agent_manager()
    history = agent_manager.get_conversation_history(conversation_id)
    
    if history is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {"conversation_id": conversation_id, "messages": history}


@router.delete("/agents/conversation/{conversation_id}")
async def clear_conversation(
    conversation_id: str,
    user_id: str = Depends(get_legal_user_id_required)
):
    """
    Clear a conversation from memory.
    
    **Endpoint:** DELETE /api/v1/legal/agents/conversation/{conversation_id}
    """
    agent_manager = get_agent_manager()
    success = agent_manager.clear_conversation(conversation_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {"message": "Conversation cleared", "conversation_id": conversation_id}
