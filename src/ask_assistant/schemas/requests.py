"""Request schemas for Ask Assistant API"""

from typing import Optional, List, Dict, Any
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
        description="User's specific collections to include (null = only system collections, [] = only system collections, [ids] = system + user collections)"
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Existing conversation ID to continue"
    )
    temperature: Optional[float] = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="LLM temperature for response randomness (0.0-2.0)"
    )
    max_tokens: Optional[int] = Field(
        default=2048,
        ge=1,
        le=4096,
        description="Maximum tokens for LLM response (1-4096)"
    )
    file_contents: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Extracted file contents for analysis. Each item should have 'filename', 'content', and 'type' fields."
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
                "conversation_id": None,
                "temperature": 0.7,
                "max_tokens": 2048,
                "file_contents": [
                    {
                        "filename": "document.pdf",
                        "content": "This is the extracted text content from the PDF...",
                        "type": "pdf"
                    }
                ]
            }
        }
