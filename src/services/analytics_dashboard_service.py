from typing import Dict, Any, List, Optional
import structlog

from .analytics.base_provider import AnalyticsDashboardProvider, DashboardType
from .analytics.google_studio_provider import GoogleStudioProvider
from ..config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class AnalyticsDashboardService:
    """Service for managing analytics dashboard providers."""

    def __init__(self):
        self.provider = self._create_provider()

    def _create_provider(self) -> AnalyticsDashboardProvider:
        """Create Google Data Studio provider."""
        provider = GoogleStudioProvider()

        if not provider.is_configured():
            logger.warning("Google Data Studio is not properly configured")

        logger.info("Analytics provider initialized", provider="google_studio", configured=provider.is_configured())
        return provider

    def get_dashboard_url(self, dashboard_type: str, user_id: Optional[int] = None, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get dashboard URL with metadata.

        Args:
            dashboard_type: Type of dashboard (learning, quiz-performance, content-effectiveness, user-insights)
            user_id: Optional user ID for user-specific dashboards
            filters: Optional additional filters

        Returns:
            Dictionary with URL, provider info, and metadata
        """
        if dashboard_type not in DashboardType.all():
            raise ValueError(f"Invalid dashboard type: {dashboard_type}. Supported types: {DashboardType.all()}")

        # Merge user_id into filters
        all_filters = filters or {}
        if user_id:
            all_filters["user_id"] = user_id

        try:
            url = self.provider.get_dashboard_url(dashboard_type, all_filters)

            return {
                "url": url,
                "provider": self.provider.get_provider_name(),
                "dashboard_type": dashboard_type,
                "filters_applied": all_filters,
                "is_configured": self.provider.is_configured()
            }

        except Exception as e:
            logger.error(f"Failed to generate dashboard URL", dashboard_type=dashboard_type, provider=self.provider.get_provider_name(), error=str(e))
            raise

    def get_available_dashboards(self) -> List[Dict[str, Any]]:
        """
        Get list of available dashboard types and their configuration status.

        Returns:
            List of dashboard information
        """
        all_dashboards = []
        supported_types = self.provider.get_supported_dashboard_types()

        for dashboard_type in DashboardType.all():
            dashboard_info = {
                "type": dashboard_type,
                "name": self._get_dashboard_display_name(dashboard_type),
                "description": self._get_dashboard_description(dashboard_type),
                "is_configured": dashboard_type in supported_types,
                "provider": self.provider.get_provider_name()
            }
            all_dashboards.append(dashboard_info)

        return all_dashboards

    def get_provider_info(self) -> Dict[str, Any]:
        """
        Get current provider information.

        Returns:
            Provider metadata
        """
        return {
            "provider": self.provider.get_provider_name(),
            "is_configured": self.provider.is_configured(),
            "supported_dashboards": self.provider.get_supported_dashboard_types(),
            "all_dashboard_types": DashboardType.all()
        }

    def is_provider_configured(self) -> bool:
        """Check if current provider is properly configured."""
        return self.provider.is_configured()


    def _get_dashboard_display_name(self, dashboard_type: str) -> str:
        """Get human-readable name for dashboard type."""
        names = {
            DashboardType.LEARNING: "Learning Progress",
            DashboardType.QUIZ_PERFORMANCE: "Quiz Performance",
            DashboardType.CONTENT_EFFECTIVENESS: "Content Analytics",
            DashboardType.USER_INSIGHTS: "User Insights"
        }
        return names.get(dashboard_type, dashboard_type.replace("-", " ").title())

    def _get_dashboard_description(self, dashboard_type: str) -> str:
        """Get description for dashboard type."""
        descriptions = {
            DashboardType.LEARNING: "Track learning velocity, concept mastery, and progress over time",
            DashboardType.QUIZ_PERFORMANCE: "Analyze quiz scores, completion rates, and difficulty patterns",
            DashboardType.CONTENT_EFFECTIVENESS: "Evaluate content types, engagement, and processing metrics",
            DashboardType.USER_INSIGHTS: "Individual user behavior, recommendations, and learning patterns"
        }
        return descriptions.get(dashboard_type, f"Analytics dashboard for {dashboard_type}")


# Singleton instance
_analytics_service = None


def get_analytics_dashboard_service() -> AnalyticsDashboardService:
    """Get singleton instance of analytics dashboard service."""
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = AnalyticsDashboardService()
    return _analytics_service