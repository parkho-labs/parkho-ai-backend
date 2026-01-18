"""Enums for Ask Assistant"""

from enum import Enum


class AgentType(str, Enum):
    """Available agent personalities"""
    CIVILIAN = "civilian"      # Normal person perspective - simple explanations
    JUDGE = "judge"            # Supreme Court Judge - constitutional interpretation
    ADVOCATE = "advocate"      # Lawyer/Advocate - legal strategy and rights


class ResponseStyle(str, Enum):
    """Response style preferences"""
    CONCISE = "concise"            # Brief, to the point (2-3 paragraphs)
    DETAILED = "detailed"          # Comprehensive with examples
    LEARNING = "learning"          # Educational, step-by-step tutorial style
    PROFESSIONAL = "professional"  # Technical legal terminology


class LLMModel(str, Enum):
    """Supported LLM models"""
    GEMINI_FLASH = "gemini-2.0-flash"
    GEMINI_PRO = "gemini-1.5-pro"
    GPT4O_MINI = "gpt-4o-mini"
    GPT4O = "gpt-4o"

    @classmethod
    def get_provider(cls, model: "LLMModel") -> str:
        """Get the provider for a model"""
        if model in [cls.GEMINI_FLASH, cls.GEMINI_PRO]:
            return "google"
        elif model in [cls.GPT4O_MINI, cls.GPT4O]:
            return "openai"
        return "google"  # default


class MemoryType(str, Enum):
    """Types of user interactions tracked in memory"""
    AGENT_CHAT = "agent_chat"              # Agent conversations (already tracked)
    GENERAL_CHAT = "general_chat"          # /ask-question endpoint
    SEARCH = "search"                       # /search-content endpoint
    QUIZ_GENERATION = "quiz_generation"     # Quiz creation
    FILE_UPLOAD = "file_upload"            # File analysis
    NEWS_INTERACTION = "news_interaction"  # News-related queries
