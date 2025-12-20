from fastapi import APIRouter

from .endpoints import auth, content, quiz, health, analytics, analytics_dashboard, files, collection, rag, rag_questions
# Legal RAG Engine endpoints
from .endpoints import law, questions, retrieve

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(content.router, prefix="/content", tags=["content"])
api_router.include_router(quiz.router, prefix="/content", tags=["quiz"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(analytics_dashboard.router, prefix="/analytics-dashboard", tags=["analytics-dashboard"])

# New Collection Router (Native Postgres) - Mounts at /collections
api_router.include_router(collection.router, prefix="/collections", tags=["collections"])

# Files Router (Formerly RAG) - Mounts at /files
# Handles Upload, List, Delete
api_router.include_router(files.router, prefix="/files", tags=["files"])

# RAG Router - Mounts at /rag prefix for consistency (e.g. /rag/query, /rag/link-content)
api_router.include_router(rag.router, prefix="/rag", tags=["rag"])

# RAG Questions Router - Mounts at /rag/questions prefix for Neo4j question generation
api_router.include_router(rag_questions.router, prefix="/rag/questions", tags=["rag-questions"])

# =============================================================================
# LEGAL FRONTEND API ROUTERS (Business-focused endpoints)
# =============================================================================

# Legal Assistant Chatbot - Mounts at /legal prefix (e.g. /legal/ask-question)
api_router.include_router(law.router, prefix="/legal", tags=["legal-assistant"])

# Legal Question Generation - Mounts at /legal prefix (e.g. /legal/generate-quiz)
api_router.include_router(questions.router, prefix="/legal", tags=["legal-questions"])

# Legal Content Retrieval - Mounts at /legal prefix (e.g. /legal/search-content)
api_router.include_router(retrieve.router, prefix="/legal", tags=["legal-retrieval"])