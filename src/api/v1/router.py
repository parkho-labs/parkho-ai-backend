from fastapi import APIRouter

from .endpoints import auth, content, quiz, health, analytics, analytics_dashboard, rag, collection

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(content.router, prefix="/content", tags=["content"])
api_router.include_router(quiz.router, prefix="/content", tags=["quiz"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(analytics_dashboard.router, prefix="/analytics-dashboard", tags=["analytics-dashboard"])

# New Collection Router (Native Postgres) - Mounts at /rag/collections by default inside router or here
# The endpoints inside collection.py are like "/", so mounting at "/rag/collections" makes them "/rag/collections"
api_router.include_router(collection.router, prefix="/rag/collections", tags=["collections"])

# Legacy RAG Router (for file upload etc)
# Be careful: RAG router also had /collections endpoints. We should comment them out in rag.py or ensure order matters.
# Since we mounted collection first above? No, fastapi routes are first-match.
# BUT endpoints in rag.py are likely `@router.get("/collections")`.
# If we keep rag router, we have duplicate paths. 
# Better strategy: Move file upload endpoints to a new files.py or keep rag for now but remove collection endpoints from it.
api_router.include_router(rag.router, prefix="/rag", tags=["rag"])