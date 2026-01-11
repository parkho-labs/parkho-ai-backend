"""Base Agent for Ask Assistant using Pydantic AI"""

import structlog
from typing import Optional, AsyncGenerator, Dict, Any
from abc import ABC, abstractmethod

from ..models.enums import AgentType, ResponseStyle, LLMModel
from ..prompts.agent_prompts import get_agent_prompt
from ..prompts.style_prompts import get_style_prompt, OUTPUT_FORMAT
from ..schemas.responses import StreamChunk, ChunkType

logger = structlog.get_logger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    Provides common functionality for prompt building and streaming.
    """
    
    agent_type: AgentType = AgentType.CIVILIAN
    
    def __init__(self):
        """Initialize the agent"""
        self.logger = structlog.get_logger(self.__class__.__name__)
    
    @property
    def system_prompt(self) -> str:
        """Get the base system prompt for this agent"""
        return get_agent_prompt(self.agent_type)
    
    def build_full_prompt(
        self,
        style: ResponseStyle,
        memory_context: Optional[str] = None,
        rag_context: Optional[str] = None
    ) -> str:
        """
        Build the complete system prompt with all components.
        
        Args:
            style: Response style to apply
            memory_context: Previous conversation context from memory
            rag_context: Relevant information from knowledge base
        
        Returns:
            Complete system prompt
        """
        parts = [self.system_prompt]
        
        # Add style instructions
        style_prompt = get_style_prompt(style)
        parts.append(style_prompt)
        
        # Add output format
        parts.append(OUTPUT_FORMAT)
        
        # Add memory context if available
        if memory_context:
            parts.append(memory_context)
        
        # Add RAG context if available
        if rag_context:
            parts.append(rag_context)
        
        # Add chain of thought instruction
        parts.append("""
## Chain of Thought
Before answering, briefly explain your reasoning process in 1-2 sentences. Start with "Let me analyze this..." or similar, then provide your answer.
""")
        
        return "\n\n".join(parts)
    
    async def generate_stream(
        self,
        question: str,
        system_prompt: str,
        model: LLMModel,
        llm_service: Any  # LLMService instance
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Generate streaming response with chain of thought.
        
        Args:
            question: User's question
            system_prompt: Complete system prompt
            model: LLM model to use
            llm_service: LLM service instance
        
        Yields:
            StreamChunk objects for SSE
        """
        try:
            # Yield thinking start
            yield StreamChunk(
                type=ChunkType.THINKING,
                content="Analyzing your question..."
            )
            
            # Generate response using LLM service
            full_response = await llm_service.generate_with_fallback(
                system_prompt=system_prompt,
                user_prompt=question,
                temperature=0.3,
                max_tokens=2000,
                preferred_provider=LLMModel.get_provider(model)
            )
            
            # Parse thinking vs answer from response
            thinking, answer = self._parse_response(full_response)
            
            # Yield thinking if present
            if thinking:
                yield StreamChunk(
                    type=ChunkType.THINKING,
                    content=thinking
                )
            
            # Yield answer in chunks for streaming effect
            # Split by paragraphs for natural chunking
            paragraphs = answer.split("\n\n")
            for paragraph in paragraphs:
                if paragraph.strip():
                    yield StreamChunk(
                        type=ChunkType.ANSWER,
                        content=paragraph + "\n\n"
                    )
            
        except Exception as e:
            self.logger.error("Agent generation failed", error=str(e))
            yield StreamChunk(
                type=ChunkType.ERROR,
                content=f"An error occurred: {str(e)}"
            )
    
    def _parse_response(self, response: str) -> tuple[str, str]:
        """
        Parse response into thinking and answer parts.
        
        Args:
            response: Full LLM response
        
        Returns:
            Tuple of (thinking, answer)
        """
        # Look for thinking indicators
        thinking_markers = [
            "Let me analyze",
            "Let me think",
            "Analyzing",
            "Considering",
            "First, I'll",
            "To answer this"
        ]
        
        thinking = ""
        answer = response
        
        # Try to extract thinking from the beginning
        lines = response.split("\n")
        thinking_lines = []
        answer_start = 0
        
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            
            # Check if line starts with thinking marker
            is_thinking = any(marker.lower() in line_lower for marker in thinking_markers)
            
            # If we find a heading or substantial content, stop looking for thinking
            if line.startswith("#") or (len(line) > 100 and not is_thinking):
                answer_start = i
                break
            
            if is_thinking or (i < 3 and len(line) < 200):
                thinking_lines.append(line)
                answer_start = i + 1
            else:
                break
        
        if thinking_lines:
            thinking = "\n".join(thinking_lines).strip()
            answer = "\n".join(lines[answer_start:]).strip()
        
        return thinking, answer
    
    @abstractmethod
    def get_name(self) -> str:
        """Get the display name of this agent"""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """Get a description of this agent's personality"""
        pass
