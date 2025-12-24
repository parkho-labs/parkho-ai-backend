from datetime import datetime
from typing import Dict, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from ...dependencies import get_db
from ....config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

router = APIRouter()


#REVISIT - Halth check shouldn't be this complex
@router.get("/health")
async def health_check(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    try:
        db.execute(text("SELECT 1"))
        db_status = "healthy"
        
        status = "healthy" if db_status == "healthy" else "unhealthy"
        
        logger.info(
            "Health check passed", 
            database_status=db_status
        )
        
        return {
            "status": status,
            "service": "Parkho AI API",
            "version": "0.1.0",
            "environment": "development" if settings.debug else "production",
            "database": db_status,
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_check": "OK"
        }
        
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "database": "unhealthy",
                "error": "Database connectivity failed",
                "timestamp": datetime.utcnow().isoformat()
            }
        )