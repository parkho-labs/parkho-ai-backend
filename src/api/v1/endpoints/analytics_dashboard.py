from typing import Optional, Dict, Any, List
import json
import structlog
from fastapi import APIRouter, HTTPException, Query, Depends

from ....services.analytics_dashboard_service import AnalyticsDashboardService
from ....services.analytics.base_provider import DashboardType
from ...dependencies import get_current_user_optional, get_current_user_optional_conditional, get_analytics_dashboard_service_dep
from ....models.user import User

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/dashboard-url")
async def get_dashboard_url(
    dashboard_type: str = Query(..., description="Dashboard type (learning, quiz-performance, content-effectiveness, user-insights)"),
    user_id: Optional[int] = Query(None, description="User ID for user-specific dashboards"),
    filters: Optional[str] = Query(None, description="Additional filters as JSON string"),
    service: AnalyticsDashboardService = Depends(get_analytics_dashboard_service_dep),
    current_user: Optional[User] = Depends(get_current_user_optional_conditional)
) -> Dict[str, Any]:
    try:
        parsed_filters = {}
        if filters:
            try:
                parsed_filters = json.loads(filters)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON in filters parameter")

        effective_user_id = user_id
        if not effective_user_id and current_user:
            effective_user_id = current_user.user_id

        result = service.get_dashboard_url(
            dashboard_type=dashboard_type,
            user_id=effective_user_id,
            filters=parsed_filters
        )

        logger.info("Dashboard URL generated", dashboard_type=dashboard_type, user_id=effective_user_id, provider=result["provider"])
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to generate dashboard URL", dashboard_type=dashboard_type, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to generate dashboard URL")


@router.get("/available-dashboards")
async def get_available_dashboards(
    service: AnalyticsDashboardService = Depends(get_analytics_dashboard_service_dep)
) -> List[Dict[str, Any]]:
    
    try:
        dashboards = service.get_available_dashboards()
        logger.info("Available dashboards retrieved", count=len(dashboards))
        return dashboards

    except Exception as e:
        logger.error("Failed to get available dashboards", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve available dashboards")


@router.get("/provider-info")
async def get_provider_info(
    service: AnalyticsDashboardService = Depends(get_analytics_dashboard_service_dep)
) -> Dict[str, Any]:

    try:
        provider_info = service.get_provider_info()
        logger.info("Provider info retrieved", provider=provider_info["provider"])
        return provider_info

    except Exception as e:
        logger.error("Failed to get provider info", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve provider information")


@router.get("/dashboard-types")
async def get_dashboard_types() -> Dict[str, Any]:
   
    dashboard_types = {
        DashboardType.LEARNING: {
            "name": "Learning Progress",
            "description": "Track learning velocity, concept mastery, and progress over time",
            "typical_filters": ["user_id", "time_range", "topic"]
        },
        DashboardType.QUIZ_PERFORMANCE: {
            "name": "Quiz Performance",
            "description": "Analyze quiz scores, completion rates, and difficulty patterns",
            "typical_filters": ["user_id", "quiz_id", "time_range", "difficulty"]
        },
        DashboardType.CONTENT_EFFECTIVENESS: {
            "name": "Content Analytics",
            "description": "Evaluate content types, engagement, and processing metrics",
            "typical_filters": ["content_type", "time_range", "processing_status"]
        },
        DashboardType.USER_INSIGHTS: {
            "name": "User Insights",
            "description": "Individual user behavior, recommendations, and learning patterns",
            "typical_filters": ["user_id", "time_range", "activity_type"]
        }
    }

    return {
        "dashboard_types": dashboard_types,
        "all_types": DashboardType.all()
    }


@router.post("/validate-config")
async def validate_provider_config(
    service: AnalyticsDashboardService = Depends(get_analytics_dashboard_service_dep)
) -> Dict[str, Any]:

    try:
        provider_info = service.get_provider_info()
        is_configured = service.is_provider_configured()

        validation_result = {
            "provider": provider_info["provider"],
            "is_configured": is_configured,
            "supported_dashboards": provider_info["supported_dashboards"],
            "validation_status": "success" if is_configured else "configuration_missing"
        }

        if not is_configured:
            validation_result["message"] = f"Provider {provider_info['provider']} is not properly configured. Check environment variables."

        return validation_result

    except Exception as e:
        logger.error("Failed to validate provider config", error=str(e))
        return {
            "validation_status": "error",
            "message": f"Configuration validation failed: {str(e)}"
        }



@router.get("/health")
async def analytics_health_check(
    service: AnalyticsDashboardService = Depends(get_analytics_dashboard_service_dep)
) -> Dict[str, Any]:
    try:
        provider_info = service.get_provider_info()
        is_configured = service.is_provider_configured()

        return {
            "status": "healthy" if is_configured else "degraded",
            "provider": provider_info["provider"],
            "configured": is_configured,
            "supported_dashboards": len(provider_info["supported_dashboards"]),
            "timestamp": "2024-11-06T00:00:00Z"  # This would normally be current timestamp
        }

    except Exception as e:
        logger.error("Analytics health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": "2024-11-06T00:00:00Z"
        }