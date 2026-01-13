"""Response schemas for Ask Assistant API"""

from typing import Optional, List, Any
from enum import Enum
from pydantic import BaseModel, Field

from ..models.enums import AgentType, ResponseStyle, LLMModel


class ChunkType(str, Enum):
    """Types of streaming chunks"""
    THINKING = "thinking"    # Chain of thought reasoning
    ANSWER = "answer"        # Main answer content
    SOURCE = "source"        # Source/citation information
    WARNING = "warning"      # Warning message (e.g., model fallback)
    ERROR = "error"          # Error message
    DONE = "done"            # Stream completion marker


class StreamChunk(BaseModel):
    """A single chunk in the streaming response"""
    type: ChunkType
    content: str = ""
    metadata: Optional[dict] = None
    
    def to_sse(self) -> str:
        """Convert to Server-Sent Events format"""
        return f"data: {self.model_dump_json()}\n\n"


class SourceInfo(BaseModel):
    """Source/citation information"""
    title: str
    text: str
    article: Optional[str] = None
    collection_id: Optional[str] = None
    relevance_score: Optional[float] = None


class AgentChatResponse(BaseModel):
    """Complete response (for non-streaming)"""
    answer: str
    thinking: Optional[str] = None
    sources: List[SourceInfo] = Field(default_factory=list)
    agent_type: AgentType
    style: ResponseStyle
    model: LLMModel
    conversation_id: str
    tokens_used: Optional[int] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "answer": "Article 21 of the Indian Constitution guarantees...",
                "thinking": "Let me analyze this from a judicial perspective...",
                "sources": [
                    {
                        "title": "Constitution of India",
                        "text": "No person shall be deprived of his life...",
                        "article": "Article 21"
                    }
                ],
                "agent_type": "judge",
                "style": "detailed",
                "model": "gemini-2.0-flash",
                "conversation_id": "conv_abc123",
                "tokens_used": 523
            }
        }


class AgentTypeInfo(BaseModel):
    """Information about an agent type"""
    id: str
    name: str
    description: str


class AgentTypesResponse(BaseModel):
    """Response for listing agent types"""
    agents: List[AgentTypeInfo]


class StyleInfo(BaseModel):
    """Information about a response style"""
    id: str
    name: str
    description: str


class StylesResponse(BaseModel):
    """Response for listing styles"""
    styles: List[StyleInfo]


class ModelInfo(BaseModel):
    """Information about an LLM model"""
    id: str
    name: str
    provider: str


class ModelsResponse(BaseModel):
    """Response for listing models"""
    models: List[ModelInfo]
