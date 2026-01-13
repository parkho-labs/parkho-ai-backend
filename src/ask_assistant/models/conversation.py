"""Conversation models for Ask Assistant"""

from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field
import uuid

from .enums import AgentType, ResponseStyle, LLMModel


def utc_now() -> datetime:
    """Get current UTC time (timezone-aware)"""
    return datetime.now(timezone.utc)


class Message(BaseModel):
    """A single message in a conversation"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: str  # "user" or "assistant"
    content: str
    agent_type: Optional[AgentType] = None
    style: Optional[ResponseStyle] = None
    model: Optional[LLMModel] = None
    timestamp: datetime = Field(default_factory=utc_now)
    sources: List[dict] = Field(default_factory=list)
    thinking: Optional[str] = None  # Chain of thought
    tokens_used: Optional[int] = None


class Conversation(BaseModel):
    """A conversation session"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    messages: List[Message] = Field(default_factory=list)
    current_agent: AgentType = AgentType.CIVILIAN
    current_style: ResponseStyle = ResponseStyle.DETAILED
    current_model: LLMModel = LLMModel.GEMINI_FLASH
    memory_enabled: bool = True
    knowledge_base_enabled: bool = True
    collection_ids: Optional[List[str]] = None  # None = all collections
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    
    def add_message(self, role: str, content: str, **kwargs) -> Message:
        """Add a message to the conversation"""
        message = Message(
            role=role,
            content=content,
            agent_type=self.current_agent if role == "assistant" else None,
            style=self.current_style if role == "assistant" else None,
            model=self.current_model if role == "assistant" else None,
            **kwargs
        )
        self.messages.append(message)
        self.updated_at = utc_now()
        return message
    
    def get_history(self, limit: int = 10) -> List[dict]:
        """Get recent message history for context"""
        recent = self.messages[-limit:] if len(self.messages) > limit else self.messages
        return [
            {"role": m.role, "content": m.content}
            for m in recent
        ]
