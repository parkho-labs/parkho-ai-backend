"""Memory Service using Mem0 for Ask Assistant"""

import structlog
from typing import Optional, List, Dict, Any
from datetime import datetime
from mem0 import Memory, MemoryClient

from ..models.enums import AgentType, MemoryType
from ...config import get_settings

logger = structlog.get_logger(__name__)

# Singleton instance
_memory_instance: Optional["MemoryService"] = None


class MemoryService:
    """
    Memory service using Mem0 for conversation persistence.
    Stores and retrieves memories per user + agent combination.
    """
    
    def __init__(self):
        """Initialize Mem0 memory with MemoryClient (Platform API) or fallback to local Memory"""
        settings = get_settings()
        self.memory = None
        self.mode = "disabled"

        # Check if memory is enabled
        if not settings.mem0_enabled:
            logger.info("Mem0 memory tracking is disabled via configuration")
            return

        try:
            # Try to initialize with MemoryClient (Platform API) if API key is available
            if settings.mem0_api_key:
                try:
                    self.memory = MemoryClient(api_key=settings.mem0_api_key)
                    self.mode = "platform"
                    logger.info("Mem0 Platform API initialized successfully")
                    return
                except Exception as e:
                    logger.warning(
                        "Failed to initialize Mem0 Platform API",
                        error=str(e),
                        fallback_enabled=settings.mem0_fallback_to_local
                    )
                    # Continue to fallback if enabled

            # Fallback to local Memory if API key not available or API failed
            if settings.mem0_fallback_to_local:
                try:
                    # Configure local Memory to use Gemini instead of OpenAI
                    # Set environment variable for Google API key
                    import os
                    os.environ["GOOGLE_API_KEY"] = settings.google_api_key

                    from mem0 import MemoryConfig

                    local_config = MemoryConfig(
                        llm={
                            "provider": "google",
                            "config": {
                                "model": settings.google_model_name
                            }
                        }
                    )
                    self.memory = Memory(config=local_config)
                    self.mode = "local"
                    logger.info(
                        "Mem0 local memory initialized with Gemini (fallback mode)",
                        model=settings.google_model_name
                    )
                except Exception as e:
                    logger.error("Failed to initialize local Mem0 memory", error=str(e))
                    self.memory = None
                    self.mode = "disabled"
            else:
                logger.warning("Mem0 fallback to local is disabled, memory will not be available")
                self.mode = "disabled"

        except Exception as e:
            logger.error("Unexpected error during Mem0 initialization", error=str(e))
            self.memory = None
            self.mode = "disabled"
    
    def add_conversation(
        self,
        user_id: str,
        question: str,
        answer: str,
        agent_type: AgentType,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Store a conversation exchange in memory.
        
        Args:
            user_id: User identifier
            question: User's question
            answer: Agent's response
            agent_type: Type of agent that responded
            metadata: Additional metadata to store
        
        Returns:
            True if successful, False otherwise
        """
        if not self.memory:
            logger.warning("Memory not available, skipping storage")
            return False
        
        try:
            # Format the conversation for storage
            conversation_text = f"User asked: {question}\n\nAgent ({agent_type.value}) responded: {answer}"
            
            # Store with user_id and agent_id for scoped retrieval
            self.memory.add(
                conversation_text,
                user_id=user_id,
                agent_id=agent_type.value,
                metadata=metadata or {}
            )
            
            logger.debug(
                "Stored conversation in memory",
                user_id=user_id,
                agent_type=agent_type.value,
                question_length=len(question)
            )
            return True
            
        except Exception as e:
            logger.error("Failed to store conversation", error=str(e), user_id=user_id)
            return False
    
    def get_relevant_memories(
        self,
        user_id: str,
        query: str,
        agent_type: Optional[AgentType] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant memories for context.
        
        Args:
            user_id: User identifier
            query: Query to search for relevant memories
            agent_type: Optional - filter by agent type
            limit: Maximum number of memories to retrieve
        
        Returns:
            List of relevant memory entries
        """
        if not self.memory:
            logger.warning("Memory not available, returning empty")
            return []
        
        try:
            # Search for relevant memories
            # For Platform API v2, use filters parameter
            if self.mode == "platform":
                # Build v2 filters
                filters = {"user_id": user_id}
                if agent_type:
                    filters["agent_id"] = agent_type.value

                results = self.memory.search(
                    query=query,
                    version="v2",
                    filters=filters,
                    limit=limit
                )
            else:
                # Local Memory uses old format
                search_kwargs = {
                    "user_id": user_id,
                    "limit": limit
                }
                if agent_type:
                    search_kwargs["agent_id"] = agent_type.value

                results = self.memory.search(query, **search_kwargs)
            
            # Extract and format results
            memories = []
            if results:
                for result in results:
                    memories.append({
                        "text": result.get("memory", result.get("text", "")),
                        "score": result.get("score", 0.0),
                        "metadata": result.get("metadata", {})
                    })
            
            logger.debug(
                "Retrieved memories",
                user_id=user_id,
                query_length=len(query),
                memories_found=len(memories)
            )
            return memories
            
        except Exception as e:
            logger.error("Failed to retrieve memories", error=str(e), user_id=user_id)
            return []
    
    def get_all_memories(
        self,
        user_id: str,
        agent_type: Optional[AgentType] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all memories for a user (optionally filtered by agent).

        Args:
            user_id: User identifier
            agent_type: Optional - filter by agent type

        Returns:
            List of all memory entries
        """
        if not self.memory:
            return []

        try:
            # For Platform API (MemoryClient), use search with empty query
            # For local Memory, get_all works
            if self.mode == "platform":
                # Platform API v2 requires using search with filters
                filters = {"user_id": user_id}
                if agent_type:
                    filters["agent_id"] = agent_type.value

                results = self.memory.search(
                    query="",
                    version="v2",
                    filters=filters,
                    limit=100
                )
                return results if results else []
            else:
                # Local Memory supports get_all
                get_kwargs = {"user_id": user_id}
                if agent_type:
                    get_kwargs["agent_id"] = agent_type.value

                results = self.memory.get_all(**get_kwargs)
                return results if results else []

        except Exception as e:
            logger.error("Failed to get all memories", error=str(e), user_id=user_id)
            return []
    
    def clear_memories(
        self,
        user_id: str,
        agent_type: Optional[AgentType] = None
    ) -> bool:
        """
        Clear memories for a user (optionally filtered by agent).

        Args:
            user_id: User identifier
            agent_type: Optional - clear only for specific agent

        Returns:
            True if successful
        """
        if not self.memory:
            return False

        try:
            delete_kwargs = {"user_id": user_id}
            if agent_type:
                delete_kwargs["agent_id"] = agent_type.value

            self.memory.delete_all(**delete_kwargs)
            logger.info("Cleared memories", user_id=user_id, agent_type=agent_type)
            return True

        except Exception as e:
            logger.error("Failed to clear memories", error=str(e), user_id=user_id)
            return False

    def add_interaction_memory(
        self,
        user_id: str,
        interaction_type: MemoryType,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Store any user interaction in memory with rich metadata.
        Generic method for tracking all types of user interactions.

        Args:
            user_id: User identifier
            interaction_type: Type of interaction (from MemoryType enum)
            content: Content to store (formatted string describing the interaction)
            metadata: Additional metadata to store with the interaction

        Returns:
            True if successful, False otherwise
        """
        if not self.memory:
            logger.debug(
                "Memory not available, skipping interaction storage",
                interaction_type=interaction_type.value
            )
            return False

        try:
            # Build rich metadata with timestamp and interaction type
            full_metadata = {
                "interaction_type": interaction_type.value,
                "timestamp": datetime.utcnow().isoformat(),
                **(metadata or {})
            }

            # Store the interaction
            self.memory.add(
                content,
                user_id=user_id,
                metadata=full_metadata
            )

            logger.debug(
                "Stored interaction memory",
                user_id=user_id,
                interaction_type=interaction_type.value,
                content_length=len(content)
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to store interaction memory",
                error=str(e),
                user_id=user_id,
                interaction_type=interaction_type.value
            )
            return False
    
    def format_memory_context(self, memories: List[Dict[str, Any]]) -> str:
        """
        Format memories into context string for the agent.
        
        Args:
            memories: List of memory entries
        
        Returns:
            Formatted string for inclusion in prompt
        """
        if not memories:
            return ""
        
        context_parts = ["## Previous Conversations (for context):\n"]
        for i, mem in enumerate(memories, 1):
            text = mem.get("text", "")
            if text:
                # Truncate very long memories
                if len(text) > 500:
                    text = text[:500] + "..."
                context_parts.append(f"{i}. {text}\n")
        
        return "\n".join(context_parts)


def get_memory_service() -> MemoryService:
    """Get or create the MemoryService singleton"""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = MemoryService()
    return _memory_instance
