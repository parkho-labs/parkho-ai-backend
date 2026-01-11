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
        conversation_id: Optional[str] = None
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
            knowledge_base_enabled: Whether to query RAG
            collection_ids: Specific collections to query
            conversation_id: Existing conversation to continue
        
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
            kb_enabled=knowledge_base_enabled
        )
        
        try:
            # Get or create conversation
            conversation = self.get_or_create_conversation(user_id, conversation_id)
            conversation.current_agent = agent_type
            conversation.current_style = style
            conversation.current_model = model
            
            # Get the appropriate agent
            agent = self.get_agent(agent_type)
            
            # Gather context
            memory_context = None
            rag_context = None
            sources: List[SourceInfo] = []
            
            # Step 1: Get memory context
            if memory_enabled:
                yield StreamChunk(
                    type=ChunkType.THINKING,
                    content="Checking previous conversations..."
                )
                
                memories = self.memory_service.get_relevant_memories(
                    user_id=user_id,
                    query=question,
                    agent_type=agent_type,
                    limit=3
                )
                memory_context = self.memory_service.format_memory_context(memories)
            
            # Step 2: Get RAG context
            if knowledge_base_enabled:
                yield StreamChunk(
                    type=ChunkType.THINKING,
                    content="Searching knowledge base..."
                )
                
                rag_result = await self.rag_service.retrieve_context(
                    query=question,
                    user_id=user_id,
                    collection_ids=collection_ids,
                    top_k=5
                )
                
                if rag_result.get("success") and rag_result.get("results"):
                    rag_context = self.rag_service.format_context_for_prompt(
                        rag_result["results"]
                    )
                    
                    # Convert to SourceInfo
                    for result in rag_result["results"][:3]:  # Top 3 sources
                        sources.append(SourceInfo(
                            title=result.get("title", "Legal Document"),
                            text=result.get("text", "")[:200] + "...",
                            article=result.get("article"),
                            collection_id=result.get("collection_id"),
                            relevance_score=result.get("relevance_score")
                        ))
            
            # Step 3: Build full prompt
            system_prompt = agent.build_full_prompt(
                style=style,
                memory_context=memory_context,
                rag_context=rag_context
            )
            
            # Step 4: Generate response
            yield StreamChunk(
                type=ChunkType.THINKING,
                content=f"Formulating response as {agent.get_name()}..."
            )
            
            full_answer = ""
            thinking = ""
            
            async for chunk in agent.generate_stream(
                question=question,
                system_prompt=system_prompt,
                model=model,
                llm_service=self.llm_service
            ):
                yield chunk
                
                # Collect for memory storage
                if chunk.type == ChunkType.ANSWER:
                    full_answer += chunk.content
                elif chunk.type == ChunkType.THINKING:
                    thinking += chunk.content + " "
            
            # Step 5: Yield sources
            for source in sources:
                yield StreamChunk(
                    type=ChunkType.SOURCE,
                    content=source.model_dump_json(),
                    metadata={"title": source.title, "article": source.article}
                )
            
            # Step 6: Save to memory (if enabled)
            if memory_enabled and full_answer:
                self.memory_service.add_conversation(
                    user_id=user_id,
                    question=question,
                    answer=full_answer,
                    agent_type=agent_type,
                    metadata={
                        "style": style.value,
                        "model": model.value,
                        "conversation_id": conversation.id
                    }
                )
            
            # Step 7: Add to conversation history
            conversation.add_message("user", question)
            conversation.add_message(
                "assistant",
                full_answer,
                thinking=thinking.strip() if thinking else None,
                sources=[s.model_dump() for s in sources]
            )
            
            # Step 8: Yield done
            yield StreamChunk(
                type=ChunkType.DONE,
                content="",
                metadata={
                    "conversation_id": conversation.id,
                    "agent_type": agent_type.value,
                    "style": style.value,
                    "model": model.value,
                    "sources_count": len(sources)
                }
            )
            
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
        conversation_id: Optional[str] = None
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
            conversation_id=conversation_id
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


def get_agent_manager() -> AgentManager:
    """Get or create the AgentManager singleton"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = AgentManager()
    return _manager_instance
