"""Base Agent for Ask Assistant using Pydantic AI"""

import structlog
from typing import Optional, AsyncGenerator, Dict, Any
from abc import ABC, abstractmethod

from ..models.enums import AgentType, ResponseStyle, LLMModel
from ..prompts.agent_prompts import get_agent_prompt
from ..prompts.style_prompts import get_style_prompt, OUTPUT_FORMAT
from ..schemas.responses import StreamChunk, ChunkType
from src.services.llm_service import LLMProvider

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
        rag_context: Optional[str] = None,
        file_context: Optional[str] = None
    ) -> str:
        """
        Build the complete system prompt with all components.

        Args:
            style: Response style to apply
            memory_context: Previous conversation context from memory
            rag_context: Relevant information from knowledge base
            file_context: Content from uploaded files for analysis

        Returns:
            Complete system prompt
        """
        return self._assemble_prompt_components(
            style, memory_context, rag_context, file_context
        )

    def _assemble_prompt_components(
        self,
        style: ResponseStyle,
        memory_context: Optional[str],
        rag_context: Optional[str],
        file_context: Optional[str]
    ) -> str:
        """Assemble all prompt components in the correct order"""
        parts = [
            self.system_prompt,
            get_style_prompt(style),
            OUTPUT_FORMAT
        ]

        # Add context sections
        parts.extend(self._get_context_sections(memory_context, rag_context, file_context))

        # Add chain of thought instruction
        parts.append(self._get_chain_of_thought_instruction())

        return "\n\n".join(parts)

    def _get_context_sections(
        self,
        memory_context: Optional[str],
        rag_context: Optional[str],
        file_context: Optional[str]
    ) -> list[str]:
        """Get all non-empty context sections"""
        contexts = []

        if memory_context:
            contexts.append(memory_context)

        if rag_context:
            contexts.append(rag_context)

        if file_context:
            contexts.append(file_context)

        return contexts

    def _get_chain_of_thought_instruction(self) -> str:
        """Get the chain of thought instruction"""
        return """## Chain of Thought
Before answering, briefly explain your reasoning process in 1-2 sentences. Start with "Let me analyze this..." or similar, then provide your answer."""
    
    async def generate_stream(
        self,
        question: str,
        system_prompt: str,
        model: LLMModel,
        llm_service: Any,  # LLMService instance
        temperature: Optional[float] = 0.7,
        max_tokens: Optional[int] = 2048
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Generate streaming response with chain of thought.

        Args:
            question: User's question
            system_prompt: Complete system prompt
            model: LLM model to use
            llm_service: LLM service instance
            temperature: LLM temperature (0.0-2.0, default 0.7)
            max_tokens: Maximum tokens for response (default 2048)

        Yields:
            StreamChunk objects for SSE
        """
        from src.services.llm_service import LLMError

        try:
            yield StreamChunk(
                type=ChunkType.THINKING,
                content="Analyzing your question..."
            )

            # Generate LLM response
            result = await self._generate_llm_response(
                question, system_prompt, model, llm_service, temperature, max_tokens
            )

            # Handle fallback warnings
            async for warning_chunk in self._handle_fallback_warnings(result):
                yield warning_chunk

            # Process and stream the response
            async for response_chunk in self._stream_response_content(result["response"]):
                yield response_chunk

        except LLMError as e:
            async for error_chunk in self._handle_llm_error(e):
                yield error_chunk
        except Exception as e:
            async for error_chunk in self._handle_general_error(e):
                yield error_chunk

    async def _generate_llm_response(
        self,
        question: str,
        system_prompt: str,
        model: LLMModel,
        llm_service: Any,
        temperature: float,
        max_tokens: int
    ) -> Dict[str, Any]:
        """Generate response from LLM service"""
        # Convert string provider to LLMProvider enum
        provider_str = LLMModel.get_provider(model)
        provider_enum = LLMProvider(provider_str) if provider_str else None

        return await llm_service.generate_with_metadata(
            system_prompt=system_prompt,
            user_prompt=question,
            temperature=temperature,
            max_tokens=max_tokens,
            preferred_provider=provider_enum
        )

    async def _handle_fallback_warnings(self, result: Dict[str, Any]) -> AsyncGenerator[StreamChunk, None]:
        """Handle and yield fallback warnings if LLM provider switched"""
        if not result.get("fallback_occurred"):
            return

        requested = result.get("requested_provider", "requested model")
        used = result.get("provider_used", "alternative")
        model_used = result.get("model_used", "")

        # Build warning message based on error type
        warning_msg = self._build_fallback_warning_message(
            result.get("errors", []), requested, used, model_used
        )

        yield StreamChunk(
            type=ChunkType.WARNING,
            content=warning_msg,
            metadata={
                "requested_provider": result.get("requested_provider"),
                "actual_provider": result.get("provider_used"),
                "model_used": result.get("model_used"),
                "errors": result.get("errors", [])
            }
        )

    def _build_fallback_warning_message(
        self,
        errors: list,
        requested: str,
        used: str,
        model_used: str
    ) -> str:
        """Build appropriate warning message based on error type"""
        if not errors:
            return f"Note: {requested.title()} model unavailable. Using {used.title()} ({model_used}) instead."

        error_type = errors[0].get("error_type", "")
        if error_type == "model_not_found":
            return f"The requested model is not available. Switched to {model_used}."
        elif error_type == "rate_limit":
            return f"Rate limit reached on primary model. Using {model_used}."
        elif error_type == "quota_exceeded":
            return f"Quota exceeded on primary model. Using {model_used}."
        else:
            return f"Note: {requested.title()} model unavailable. Using {used.title()} ({model_used}) instead."

    async def _stream_response_content(self, response: str) -> AsyncGenerator[StreamChunk, None]:
        """Parse and stream response content"""
        # Parse thinking vs answer from response
        thinking, answer = self._parse_response(response)

        # Yield thinking if present
        if thinking:
            yield StreamChunk(
                type=ChunkType.THINKING,
                content=thinking
            )

        # Stream answer in natural chunks
        async for answer_chunk in self._stream_answer_paragraphs(answer):
            yield answer_chunk

    async def _stream_answer_paragraphs(self, answer: str) -> AsyncGenerator[StreamChunk, None]:
        """Stream answer content in paragraph chunks"""
        paragraphs = answer.split("\n\n")
        for paragraph in paragraphs:
            if paragraph.strip():
                yield StreamChunk(
                    type=ChunkType.ANSWER,
                    content=paragraph + "\n\n"
                )

    async def _handle_llm_error(self, error) -> AsyncGenerator[StreamChunk, None]:
        """Handle LLM service errors"""
        self.logger.error("All LLM providers failed", error=str(error), errors=error.errors)
        error_msg = error.get_user_friendly_message()
        yield StreamChunk(
            type=ChunkType.ERROR,
            content=error_msg,
            metadata={
                "error_details": error.errors,
                "recoverable": False
            }
        )

    async def _handle_general_error(self, error: Exception) -> AsyncGenerator[StreamChunk, None]:
        """Handle general errors with user-friendly messages"""
        self.logger.error("Agent generation failed", error=str(error))

        # Provide user-friendly error message
        user_msg = self._get_user_friendly_error_message(str(error))

        yield StreamChunk(
            type=ChunkType.ERROR,
            content=user_msg,
            metadata={
                "technical_error": str(error),
                "recoverable": True
            }
        )

    def _get_user_friendly_error_message(self, error_str: str) -> str:
        """Convert technical errors to user-friendly messages"""
        error_lower = error_str.lower()

        if "api key" in error_lower or "authentication" in error_lower:
            return "AI service configuration issue. Please contact support."
        elif "timeout" in error_lower:
            return "Request timed out. Please try again."
        elif "rate limit" in error_lower:
            return "Too many requests. Please wait a moment and try again."
        else:
            return "An unexpected error occurred. Please try again."
    
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
