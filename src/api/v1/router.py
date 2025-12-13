from fastapi import APIRouter

from .endpoints import auth, content, quiz, health, analytics, analytics_dashboard, rag

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(content.router, prefix="/content", tags=["content"])
api_router.include_router(quiz.router, prefix="/content", tags=["quiz"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(analytics_dashboard.router, prefix="/analytics-dashboard", tags=["analytics-dashboard"])
api_router.include_router(rag.router, prefix="/rag", tags=["rag"])