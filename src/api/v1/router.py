from fastapi import APIRouter

from .endpoints import auth, health, analytics, files, collection
# Legal RAG Engine endpoints
from .endpoints import law, questions, retrieve
# PYQ endpoints
from .endpoints import pyq
# News endpoints
from .endpoints import news

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
# Content and quiz routers removed as part of API cleanup
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
# Analytics dashboard router removed as part of API cleanup

# New Collection Router (Native Postgres) - Mounts at /collections
api_router.include_router(collection.router, prefix="/collections", tags=["collections"])

# Files Router (Formerly RAG) - Mounts at /files
# Handles Upload, List, Delete
api_router.include_router(files.router, prefix="/files", tags=["files"])

# RAG router removed as part of API cleanup - internal RAG services preserved for legal/collection use

# RAG Questions router removed as part of API cleanup - service kept for internal legal use

# =============================================================================
# LEGAL FRONTEND API ROUTERS (Business-focused endpoints)
# =============================================================================

# Legal Assistant - Consolidated endpoints under single header
# Includes: Chatbot, Question Generation, Content Retrieval
api_router.include_router(law.router, prefix="/legal", tags=["legal-assistant"])
api_router.include_router(questions.router, prefix="/legal", tags=["legal-assistant"])
api_router.include_router(retrieve.router, prefix="/legal", tags=["legal-assistant"])

# =============================================================================
# PYQ (Previous Year Questions) API ROUTER
# =============================================================================

# PYQ System - Mounts at /pyq prefix (e.g. /pyq/papers, /pyq/attempts)
api_router.include_router(pyq.router, prefix="/pyq", tags=["pyq"])

# =============================================================================
# NEWS API ROUTER
# =============================================================================

# News System - Mounts at /news prefix (e.g. /news/, /news/{id})
api_router.include_router(news.router, prefix="/news", tags=["news"])
