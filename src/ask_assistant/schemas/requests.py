"""Request schemas for Ask Assistant API"""

from typing import Optional, List
from pydantic import BaseModel, Field

from ..models.enums import AgentType, ResponseStyle, LLMModel


class AgentChatRequest(BaseModel):
    """Request schema for agent chat endpoint"""
    question: str = Field(..., max_length=5000, description="User's question")
    agent_type: AgentType = Field(
        default=AgentType.CIVILIAN,
        description="Agent personality to use"
    )
    style: ResponseStyle = Field(
        default=ResponseStyle.DETAILED,
        description="Response style preference"
    )
    model: LLMModel = Field(
        default=LLMModel.GEMINI_FLASH,
        description="LLM model to use"
    )
    memory_enabled: bool = Field(
        default=True,
        description="Enable conversation memory"
    )
    knowledge_base_enabled: bool = Field(
        default=True,
        description="Enable RAG knowledge base"
    )
    collection_ids: Optional[List[str]] = Field(
        default=None,
        description="Specific collections to query (None = all)"
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Existing conversation ID to continue"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "What is Article 21 of the Indian Constitution?",
                "agent_type": "judge",
                "style": "detailed",
                "model": "gemini-2.0-flash",
                "memory_enabled": True,
                "knowledge_base_enabled": True,
                "collection_ids": None,
                "conversation_id": None
            }
        }
