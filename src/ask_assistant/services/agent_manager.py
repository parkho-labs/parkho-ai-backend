"""Agent Manager - Main Orchestrator for Ask Assistant"""

import structlog
import uuid
from typing import Optional, List, Dict, Any, AsyncGenerator

from ..models.enums import AgentType, ResponseStyle, LLMModel
from ..models.conversation import Conversation, Message
from ..schemas.responses import StreamChunk, ChunkType, SourceInfo
from ..agents.base_agent import BaseAgent
from ..agents.civilian_agent import CivilianAgent
from ..agents.judge_agent import JudgeAgent
from ..agents.advocate_agent import AdvocateAgent
from .memory_service import MemoryService, get_memory_service
from .rag_service import RAGService, get_rag_service
from src.services.llm_service import LLMService
from src.config import get_settings

logger = structlog.get_logger(__name__)

# Singleton instance
_manager_instance: Optional["AgentManager"] = None


class AgentManager:
    """
    Main orchestrator for the Ask Assistant agent system.
    Coordinates agents, memory, RAG, and LLM services.
    """
    
    def __init__(self):
        """Initialize the agent manager"""
        self.settings = get_settings()

        # Initialize services
        self.memory_service = get_memory_service()
        self.rag_service = get_rag_service()
        self.llm_service = LLMService(
            openai_api_key=self.settings.openai_api_key,
            anthropic_api_key=self.settings.anthropic_api_key,
            google_api_key=self.settings.google_api_key
        )
        
        # Initialize agents
        self.agents: Dict[AgentType, BaseAgent] = {
            AgentType.CIVILIAN: CivilianAgent(),
            AgentType.JUDGE: JudgeAgent(),
            AgentType.ADVOCATE: AdvocateAgent()
        }
        
        # In-memory conversation cache (for session)
        self._conversations: Dict[str, Conversation] = {}
        
        logger.info("AgentManager initialized", agents=list(self.agents.keys()))
    
    def get_agent(self, agent_type: AgentType) -> BaseAgent:
        """Get an agent by type"""
        return self.agents.get(agent_type, self.agents[AgentType.CIVILIAN])
    
    def get_or_create_conversation(
        self,
        user_id: str,
        conversation_id: Optional[str] = None
    ) -> Conversation:
        """Get existing conversation or create a new one"""
        if conversation_id and conversation_id in self._conversations:
            return self._conversations[conversation_id]
        
        # Create new conversation
        conv = Conversation(
            id=conversation_id or str(uuid.uuid4()),
            user_id=user_id
        )
        self._conversations[conv.id] = conv
        return conv
    
    async def chat_stream(
        self,
        user_id: str,
        question: str,
        agent_type: AgentType = AgentType.CIVILIAN,
        style: ResponseStyle = ResponseStyle.DETAILED,
        model: LLMModel = LLMModel.GEMINI_FLASH,
        memory_enabled: bool = True,
        knowledge_base_enabled: bool = True,
        collection_ids: Optional[List[str]] = None,
        conversation_id: Optional[str] = None,
        temperature: Optional[float] = 0.7,
        max_tokens: Optional[int] = 2048,
        file_contents: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Main streaming chat method.

        Args:
            user_id: User identifier
            question: User's question
            agent_type: Agent personality to use
            style: Response style
            model: LLM model to use
            memory_enabled: Whether to use/save memory
            knowledge_base_enabled: Whether to query RAG (includes system collections)
            collection_ids: User's specific collections (null = no user collections)
            conversation_id: Existing conversation to continue
            temperature: LLM temperature (0.0-2.0)
            max_tokens: Maximum tokens for response
            file_contents: Extracted file contents from frontend

        Yields:
            StreamChunk objects for SSE streaming
        """
        logger.info(
            "Starting chat stream",
            user_id=user_id,
            agent_type=agent_type.value,
            style=style.value,
            model=model.value,
            memory_enabled=memory_enabled,
            kb_enabled=knowledge_base_enabled,
            user_collections=len(collection_ids) if collection_ids else 0
        )

        try:
            # Setup conversation and agent
            conversation = self._setup_conversation(user_id, conversation_id, agent_type, style, model)
            agent = self.get_agent(agent_type)

            # Gather all contexts
            contexts = None
            async for chunk_or_contexts in self._gather_contexts(
                user_id=user_id,
                question=question,
                agent_type=agent_type,
                memory_enabled=memory_enabled,
                knowledge_base_enabled=knowledge_base_enabled,
                collection_ids=collection_ids,
                file_contents=file_contents
            ):
                if chunk_or_contexts[0] is not None:  # It's a thinking chunk
                    yield chunk_or_contexts[0]
                else:  # It's the final contexts
                    contexts = chunk_or_contexts[1]

            # Generate response
            full_answer, thinking = None, None
            async for chunk_or_response in self._generate_agent_response(
                agent=agent,
                question=question,
                style=style,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                contexts=contexts
            ):
                if chunk_or_response[0] is not None:  # It's a chunk
                    yield chunk_or_response[0]
                else:  # It's the final response data
                    full_answer, thinking = chunk_or_response[1]

            # Send sources
            async for source_chunk in self._yield_sources(contexts["sources"]):
                yield source_chunk

            # Save conversation
            self._save_conversation_data(
                conversation=conversation,
                user_id=user_id,
                question=question,
                full_answer=full_answer,
                thinking=thinking,
                agent_type=agent_type,
                style=style,
                model=model,
                memory_enabled=memory_enabled,
                sources=contexts["sources"]
            )

            # Send completion
            yield self._create_completion_chunk(conversation, agent_type, style, model, len(contexts["sources"]))

            logger.info(
                "Chat stream completed",
                user_id=user_id,
                conversation_id=conversation.id,
                answer_length=len(full_answer)
            )

        except Exception as e:
            logger.error("Chat stream failed", error=str(e), user_id=user_id)
            yield StreamChunk(
                type=ChunkType.ERROR,
                content=f"An error occurred: {str(e)}"
            )
    
    async def chat(
        self,
        user_id: str,
        question: str,
        agent_type: AgentType = AgentType.CIVILIAN,
        style: ResponseStyle = ResponseStyle.DETAILED,
        model: LLMModel = LLMModel.GEMINI_FLASH,
        memory_enabled: bool = True,
        knowledge_base_enabled: bool = True,
        collection_ids: Optional[List[str]] = None,
        conversation_id: Optional[str] = None,
        temperature: Optional[float] = 0.7,
        max_tokens: Optional[int] = 2048,
        file_contents: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Non-streaming chat method.
        
        Returns complete response as a dict.
        """
        answer_parts = []
        thinking_parts = []
        sources = []
        final_metadata = {}
        
        async for chunk in self.chat_stream(
            user_id=user_id,
            question=question,
            agent_type=agent_type,
            style=style,
            model=model,
            memory_enabled=memory_enabled,
            knowledge_base_enabled=knowledge_base_enabled,
            collection_ids=collection_ids,
            conversation_id=conversation_id,
            temperature=temperature,
            max_tokens=max_tokens,
            file_contents=file_contents
        ):
            if chunk.type == ChunkType.ANSWER:
                answer_parts.append(chunk.content)
            elif chunk.type == ChunkType.THINKING:
                thinking_parts.append(chunk.content)
            elif chunk.type == ChunkType.SOURCE:
                sources.append(chunk.metadata)
            elif chunk.type == ChunkType.DONE:
                final_metadata = chunk.metadata or {}
        
        return {
            "answer": "".join(answer_parts),
            "thinking": " ".join(thinking_parts) if thinking_parts else None,
            "sources": sources,
            "agent_type": agent_type.value,
            "style": style.value,
            "model": model.value,
            "conversation_id": final_metadata.get("conversation_id")
        }
    
    def get_conversation_history(
        self,
        conversation_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Get history for a conversation"""
        if conversation_id in self._conversations:
            return self._conversations[conversation_id].get_history()
        return None
    
    def clear_conversation(self, conversation_id: str) -> bool:
        """Clear a conversation from memory"""
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]
            return True
        return False

    def _format_file_contents(self, file_contents: List[Dict[str, Any]]) -> str:
        """
        Format file contents for inclusion in agent prompt

        Args:
            file_contents: List of file content dictionaries with filename, content, type

        Returns:
            Formatted string for prompt inclusion
        """
        if not file_contents:
            return ""

        formatted_parts = ["## Uploaded Files Analysis\n"]

        for file_data in file_contents:
            filename = file_data.get('filename', 'Unknown File')
            content = file_data.get('content', '')
            file_type = file_data.get('type', 'unknown')

            # Truncate very long content to avoid context limits
            if len(content) > 3000:
                content = content[:3000] + "\n\n[Content truncated - file continues...]"

            formatted_parts.append(f"### 📄 {filename} ({file_type.upper()})")
            formatted_parts.append(f"```\n{content}\n```\n")

        return "\n".join(formatted_parts)

    def _setup_conversation(
        self,
        user_id: str,
        conversation_id: Optional[str],
        agent_type: AgentType,
        style: ResponseStyle,
        model: LLMModel
    ) -> Conversation:
        """Setup conversation with current settings"""
        conversation = self.get_or_create_conversation(user_id, conversation_id)
        conversation.current_agent = agent_type
        conversation.current_style = style
        conversation.current_model = model
        return conversation

    async def _gather_contexts(
        self,
        user_id: str,
        question: str,
        agent_type: AgentType,
        memory_enabled: bool,
        knowledge_base_enabled: bool,
        collection_ids: Optional[List[str]],
        file_contents: Optional[List[Dict[str, Any]]]
    ) -> AsyncGenerator[tuple[StreamChunk, Dict[str, Any]], None]:
        """Gather all context data (memory, RAG, files) with progress updates"""
        contexts = {
            "memory": None,
            "rag": None,
            "file": None,
            "sources": []
        }

        # Get memory context
        if memory_enabled:
            yield StreamChunk(
                type=ChunkType.THINKING,
                content="Checking previous conversations..."
            ), None
            contexts["memory"] = self._get_memory_context(user_id, question, agent_type)

        # Get RAG context with proper collections logic
        if knowledge_base_enabled:
            yield StreamChunk(
                type=ChunkType.THINKING,
                content="Searching knowledge base..."
            ), None
            contexts["rag"], contexts["sources"] = await self._get_rag_context(
                user_id, question, collection_ids
            )

        # Process file contents
        if file_contents:
            yield StreamChunk(
                type=ChunkType.THINKING,
                content="Processing uploaded files..."
            ), None
            contexts["file"] = self._get_file_context(file_contents)

        yield None, contexts

    def _get_memory_context(self, user_id: str, question: str, agent_type: AgentType) -> Optional[str]:
        """Retrieve memory context"""
        memories = self.memory_service.get_relevant_memories(
            user_id=user_id,
            query=question,
            agent_type=agent_type,
            limit=3
        )
        return self.memory_service.format_memory_context(memories)

    async def _get_rag_context(
        self,
        user_id: str,
        question: str,
        collection_ids: Optional[List[str]]
    ) -> tuple[Optional[str], List[SourceInfo]]:
        """
        Retrieve RAG context with proper collections logic:
        - Always include system collections (constitution, bns, etc.)
        - Additionally include user collections if collection_ids is provided
        - If collection_ids is null/empty, only system collections are used
        """
        # Prepare collections for RAG query
        query_collections = self._prepare_collections_for_rag(collection_ids)

        rag_result = await self.rag_service.retrieve_context(
            query=question,
            user_id=user_id,
            collection_ids=query_collections,
            top_k=5
        )

        sources = []
        rag_context = None

        if rag_result.get("success") and rag_result.get("results"):
            rag_context = self.rag_service.format_context_for_prompt(rag_result["results"])

            # Convert to SourceInfo (top 3 sources)
            for result in rag_result["results"][:3]:
                sources.append(SourceInfo(
                    title=result.get("title", "Legal Document"),
                    text=result.get("text", "")[:200] + "...",
                    article=result.get("article"),
                    collection_id=result.get("collection_id"),
                    relevance_score=result.get("relevance_score")
                ))

        return rag_context, sources

    def _prepare_collections_for_rag(self, user_collection_ids: Optional[List[str]]) -> Optional[List[str]]:
        """
        Prepare collections list for RAG query based on the new logic:

        Knowledge Base Enabled + Collections Logic:
        - knowledge_base_enabled=True: Always query system collections (constitution, bns, etc.)
        - collection_ids=null: Only system collections
        - collection_ids=[user_collection_ids]: System collections + user's selected collections

        This means:
        - System collections are ALWAYS included when knowledge_base_enabled=True
        - User collections are ADDITIONAL to system collections when provided
        - null collection_ids ≠ 0 collections (it means use system collections)
        """
        # System collections that are always included when knowledge_base_enabled=True
        SYSTEM_COLLECTIONS = ["constitution", "bns", "ipc", "crpc"]  # Update with your actual system collections

        if user_collection_ids is None or len(user_collection_ids) == 0:
            # Only system collections - return system collections explicitly
            return SYSTEM_COLLECTIONS

        # Include both system and user collections
        all_collections = SYSTEM_COLLECTIONS + user_collection_ids
        return all_collections

    def _get_file_context(self, file_contents: List[Dict[str, Any]]) -> str:
        """Process file contents"""
        return self._format_file_contents(file_contents)

    async def _generate_agent_response(
        self,
        agent: BaseAgent,
        question: str,
        style: ResponseStyle,
        model: LLMModel,
        temperature: float,
        max_tokens: int,
        contexts: Dict[str, Any]
    ) -> AsyncGenerator[tuple[StreamChunk, Optional[tuple[str, str]]], None]:
        """Generate agent response and collect answer/thinking"""
        # Build full prompt
        system_prompt = agent.build_full_prompt(
            style=style,
            memory_context=contexts["memory"],
            rag_context=contexts["rag"],
            file_context=contexts["file"]
        )

        yield StreamChunk(
            type=ChunkType.THINKING,
            content=f"Formulating response as {agent.get_name()}..."
        ), None

        full_answer = ""
        thinking = ""

        async for chunk in agent.generate_stream(
            question=question,
            system_prompt=system_prompt,
            model=model,
            llm_service=self.llm_service,
            temperature=temperature,
            max_tokens=max_tokens
        ):
            yield chunk, None

            # Collect for memory storage
            if chunk.type == ChunkType.ANSWER:
                full_answer += chunk.content
            elif chunk.type == ChunkType.THINKING:
                thinking += chunk.content + " "

        # Return the collected response
        yield None, (full_answer, thinking)

    async def _yield_sources(self, sources: List[SourceInfo]) -> AsyncGenerator[StreamChunk, None]:
        """Yield source information"""
        for source in sources:
            yield StreamChunk(
                type=ChunkType.SOURCE,
                content=source.model_dump_json(),
                metadata={"title": source.title, "article": source.article}
            )

    def _save_conversation_data(
        self,
        conversation: Conversation,
        user_id: str,
        question: str,
        full_answer: str,
        thinking: str,
        agent_type: AgentType,
        style: ResponseStyle,
        model: LLMModel,
        memory_enabled: bool,
        sources: List[SourceInfo]
    ) -> None:
        """Save conversation to memory and history"""
        # Save to memory service with enhanced metadata
        if memory_enabled and full_answer:
            from datetime import datetime

            # Create thinking summary (first 200 chars if exists)
            thinking_summary = None
            if thinking and thinking.strip():
                thinking_summary = thinking.strip()[:200]
                if len(thinking.strip()) > 200:
                    thinking_summary += "..."

            self.memory_service.add_conversation(
                user_id=user_id,
                question=question,
                answer=full_answer,
                agent_type=agent_type,
                metadata={
                    "style": style.value,
                    "model": model.value,
                    "conversation_id": conversation.id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "source_count": len(sources),
                    "thinking_summary": thinking_summary,
                    "has_thinking": bool(thinking and thinking.strip())
                }
            )

        # Add to conversation history
        conversation.add_message("user", question)
        conversation.add_message(
            "assistant",
            full_answer,
            thinking=thinking.strip() if thinking else None,
            sources=[s.model_dump() for s in sources]
        )

    def _create_completion_chunk(
        self,
        conversation: Conversation,
        agent_type: AgentType,
        style: ResponseStyle,
        model: LLMModel,
        sources_count: int
    ) -> StreamChunk:
        """Create completion chunk"""
        return StreamChunk(
            type=ChunkType.DONE,
            content="",
            metadata={
                "conversation_id": conversation.id,
                "agent_type": agent_type.value,
                "style": style.value,
                "model": model.value,
                "sources_count": sources_count
            }
        )


def get_agent_manager() -> AgentManager:
    """Get or create the AgentManager singleton"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = AgentManager()
    return _manager_instance
