import structlog
from datetime import datetime
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..schemas import ChatSessionResponse, ChatMessage, MessageSender, AgentType, Agent
from ...dependencies import get_current_user_conditional
from ....models.user import User
from ....services.agent_service import agent_service

logger = structlog.get_logger(__name__)

router = APIRouter()


AVAILABLE_AGENTS = {
    "physics": {
        "id": "physics",
        "name": "Physics Tutor Agent",
        "description": "Specialized physics tutor for JEE preparation and advanced concepts",
        "capabilities": ["physics_tutoring", "jee_preparation", "problem_solving", "conceptual_explanations"],
        "status": "active",
        "created_at": "2025-12-01T00:00:00Z"
    },
    "general": {
        "id": "general",
        "name": "General Tutor Agent",
        "description": "Versatile academic tutor for multiple subjects and general learning assistance",
        "capabilities": ["multi_subject", "study_skills", "homework_help", "exam_prep"],
        "status": "active",
        "created_at": "2025-12-01T00:00:00Z"
    }
}


class AgentChatRequest(BaseModel):
    session_id: str
    message: str


@router.get("", response_model=List[Agent])
async def list_agents() -> List[Agent]:
    agents = []
    for agent_data in AVAILABLE_AGENTS.values():
        agents.append(Agent(
            id=agent_data["id"],
            name=agent_data["name"],
            description=agent_data["description"],
            capabilities=agent_data["capabilities"],
            status=agent_data["status"],
            created_at=agent_data["created_at"]
        ))
    return agents


@router.get("/{agent_id}", response_model=Agent)
async def get_agent(agent_id: str) -> Agent:
    if agent_id not in AVAILABLE_AGENTS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found"
        )

    agent_data = AVAILABLE_AGENTS[agent_id]
    return Agent(
        id=agent_data["id"],
        name=agent_data["name"],
        description=agent_data["description"],
        capabilities=agent_data["capabilities"],
        status=agent_data["status"],
        created_at=agent_data["created_at"]
    )


@router.post("/{agent_id}/session", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_agent_session(
    agent_id: str,
    current_user: User = Depends(get_current_user_conditional)
) -> ChatSessionResponse:
    try:
        if agent_id not in AVAILABLE_AGENTS:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{agent_id}' not found"
            )

        user_id = current_user.user_id
        session_id = await agent_service.create_chat_session(
            user_id=user_id,
            agent_type=agent_id
        )

        current_time = datetime.now()

        return ChatSessionResponse(
            session_id=session_id,
            agent_type=AgentType(agent_id),
            created_at=current_time,
            last_message_at=None,
            message_count=0,
            is_active=True
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create agent session", error=str(e), user_id=current_user.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create agent session"
        )


@router.post("/{agent_id}/chat", response_model=ChatMessage)
async def agent_chat(
    agent_id: str,
    request: AgentChatRequest,
    current_user: User = Depends(get_current_user_conditional)
) -> ChatMessage:
    try:
        if agent_id not in AVAILABLE_AGENTS:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{agent_id}' not found"
            )

        user_id = current_user.user_id
        session_id = request.session_id

        session_history = await agent_service.get_session_history(session_id)
        if not session_history:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )

        if session_history.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this session"
            )

        if session_history.get("agent_type") != agent_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Session belongs to different agent type"
            )

        agent_response = await agent_service.send_message_async(
            session_id=session_id,
            message=request.message
        )

        return ChatMessage(
            content=agent_response["content"],
            timestamp=datetime.now(),
            sender=MessageSender.AGENT,
            message_type="text",
            metadata={
                "agent_type": agent_response.get("agent_type"),
                "session_id": session_id
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to chat with agent", error=str(e), session_id=request.session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to chat with agent"
        )


@router.get("/sessions", response_model=List[ChatSessionResponse])
async def list_agent_sessions(
    current_user: User = Depends(get_current_user_conditional)
) -> List[ChatSessionResponse]:
    try:
        user_id = current_user.user_id
        sessions_data = agent_service.list_user_sessions(user_id)

        sessions = []
        for session_data in sessions_data:
            sessions.append(ChatSessionResponse(
                session_id=session_data["session_id"],
                agent_type=AgentType(session_data["agent_type"]),
                created_at=session_data["created_at"],
                last_message_at=session_data.get("last_message_at"),
                message_count=session_data["message_count"],
                is_active=session_data.get("is_active", True)
            ))

        return sessions

    except Exception as e:
        logger.error("Failed to list agent sessions", error=str(e), user_id=current_user.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve agent sessions"
        )


@router.get("/session/{session_id}/history", response_model=List[ChatMessage])
async def get_agent_session_history(
    session_id: str,
    current_user: User = Depends(get_current_user_conditional)
) -> List[ChatMessage]:
    try:
        user_id = current_user.user_id
        session_history = await agent_service.get_session_history(session_id)

        if not session_history:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )

        if session_history.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this session"
            )

        messages = []
        for msg in session_history.get("messages", []):
            messages.append(ChatMessage(
                content=msg["content"],
                timestamp=msg["timestamp"],
                sender=MessageSender(msg["sender"]),
                message_type=msg.get("message_type", "text"),
                metadata=msg.get("metadata")
            ))

        return messages

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get session history", error=str(e), session_id=session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session history"
        )


@router.delete("/session/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent_session(
    session_id: str,
    current_user: User = Depends(get_current_user_conditional)
):
    try:
        user_id = current_user.user_id

        session_history = await agent_service.get_session_history(session_id)
        if not session_history:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )

        if session_history.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this session"
            )

        success = await agent_service.delete_session(session_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete session"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete session", error=str(e), session_id=session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete session"
        )