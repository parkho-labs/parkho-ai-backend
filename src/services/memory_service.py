from typing import List, Dict, Any, Optional
import structlog
import urllib.parse
from mem0 import Memory
from ..config import get_settings

logger = structlog.get_logger(__name__)

class MemoryService:
    _instance = None

    def __init__(self):
        self.settings = get_settings()
        self.config = {
            "vector_store": {
                "provider": "pgvector",
                "config": {
                    "dbname": self.settings.db_name,
                    "user": self.settings.db_user,
                    "password": urllib.parse.quote_plus(self.settings.db_password),
                    "host": self.settings.db_host,
                    "port": self.settings.db_port,
                    "collection_name": self.settings.mem0_collection_name,
                    "embedding_model_dims": 1536,
                }
            },
            # We can change llm provider if needed, default is openai usually
             "llm": {
                "provider": "openai",
                "config": {
                    "model": self.settings.openai_model_name,
                    "api_key": self.settings.openai_api_key,
                }
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": "text-embedding-3-small",
                    "api_key": self.settings.openai_api_key,
                }
            }
        }
        
        try:
            self.memory = Memory.from_config(self.config)
            logger.info("MemoryService initialized successfully", collection=self.settings.mem0_collection_name)
        except Exception as e:
            logger.error("Failed to initialize MemoryService", error=str(e))
            self.memory = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def add_memory(self, user_id: str, text: str, metadata: Dict[str, Any] = None):
        """
        Add a new memory for a user.
        Args:
            user_id: The unique identifier for the user.
            text: The memory text to add.
            metadata: Optional metadata (e.g., source, timestamp).
        """
        if not self.memory:
            logger.warning("MemoryService not initialized, skipping add_memory")
            return

        try:
            self.memory.add(text, user_id=user_id, metadata=metadata or {})
            logger.info("Memory added", user_id=user_id, text_snippet=text[:50])
        except Exception as e:
            logger.error("Failed to add memory", user_id=user_id, error=str(e))

    def get_user_profile(self, user_id: str, query: str = None) -> str:
        """
        Retrieve relevant memories for a user to construct a profile/context.
        If query is provided, it searches formatted memories.
        Otherwise, it retrieves all/recent memories.
        """
        if not self.memory:
            return ""

        try:
            # If query provided, search. usage: memory.search(query, user_id=...)
            # If no query, maybe mem0.get_all(user_id) if supported or search generic
            
            if query:
                results = self.memory.search(query, user_id=user_id)
            else:
                 # Fallback: get all or search with empty/generic query if get_all not directly exposed in simple interface
                 # For now, let's search for "learning preferences and history"
                 results = self.memory.search("learning preferences and history", user_id=user_id, limit=10)
            
            if not results:
                return "No prior learning history."

            if isinstance(results, dict):
                results = results.get("results", [])
            
            formatted_memories = []
            for r in results:
                if isinstance(r, dict):
                    if r.get('memory'):
                        formatted_memories.append(r.get('memory'))
                elif isinstance(r, str):
                    formatted_memories.append(r)
            
            return "\n".join(formatted_memories)

        except Exception as e:
            logger.error("Failed to get user profile", user_id=user_id, error=str(e))
            return ""

    def search_memories(self, user_id: str, query: str, limit: int = 5) -> List[str]:
        if not self.memory:
            return []
        try:
            results = self.memory.search(query, user_id=user_id, limit=limit)
            
            if isinstance(results, dict):
                results = results.get("results", [])

            memories = []
            for r in results:
                if isinstance(r, dict):
                    if r.get('memory'):
                        memories.append(r.get('memory'))
                elif isinstance(r, str):
                    memories.append(r)
            return memories
        except Exception as e:
            logger.error("Failed to search memories", user_id=user_id, error=str(e))
            return []

memory_service = MemoryService.get_instance()
