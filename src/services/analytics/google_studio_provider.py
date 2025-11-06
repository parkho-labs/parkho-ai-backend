from typing import Dict, Any, List
from urllib.parse import urlencode
import structlog

from .base_provider import AnalyticsDashboardProvider, DashboardType
from ...config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class GoogleStudioProvider(AnalyticsDashboardProvider):
    """Google Data Studio dashboard provider."""

    def __init__(self):
        self.report_ids = {
            DashboardType.LEARNING: settings.google_studio_learning_report_id,
            DashboardType.QUIZ_PERFORMANCE: settings.google_studio_quiz_report_id,
            DashboardType.CONTENT_EFFECTIVENESS: settings.google_studio_content_report_id,
            DashboardType.USER_INSIGHTS: settings.google_studio_user_report_id,
        }

    def get_dashboard_url(self, dashboard_type: str, filters: Dict[str, Any] = None) -> str:
        """Generate Google Data Studio embed URL."""
        if dashboard_type not in self.report_ids:
            raise ValueError(f"Unsupported dashboard type: {dashboard_type}")

        report_id = self.report_ids[dashboard_type]
        if not report_id:
            raise ValueError(f"No report ID configured for dashboard type: {dashboard_type}")

        # Base embed URL
        base_url = f"https://datastudio.google.com/embed/reporting/{report_id}"

        # Build URL parameters
        params = {
            "theme": "light",
            "config": self._build_config_params(filters or {})
        }

        # Add user filter if provided
        if filters and "user_id" in filters:
            params["params"] = f"user_id:{filters['user_id']}"

        # Add time range filter if provided
        if filters and "time_range" in filters:
            params["_g"] = f"(time:(from:{filters['time_range'].get('from', 'now-30d')},to:{filters['time_range'].get('to', 'now')}))"

        url_params = urlencode(params)
        full_url = f"{base_url}?{url_params}" if url_params else base_url

        logger.info("Generated Google Data Studio URL", dashboard_type=dashboard_type, has_filters=bool(filters))
        return full_url

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "google_studio"

    def is_configured(self) -> bool:
        """Check if provider is configured."""
        return any(report_id for report_id in self.report_ids.values())

    def get_supported_dashboard_types(self) -> List[str]:
        """Get supported dashboard types."""
        return [dashboard_type for dashboard_type, report_id in self.report_ids.items() if report_id]

    def _build_config_params(self, filters: Dict[str, Any]) -> str:
        """Build configuration parameters for Google Data Studio."""
        config_parts = []

        # Add refresh interval
        config_parts.append("refresh:300")  # 5 minutes

        # Add any custom config based on filters
        if filters.get("auto_refresh"):
            config_parts.append("autoRefresh:true")

        return ",".join(config_parts) if config_parts else ""

    def get_direct_link_url(self, dashboard_type: str, filters: Dict[str, Any] = None) -> str:
        """Get direct link (non-embed) URL for opening in new tab."""
        if dashboard_type not in self.report_ids:
            raise ValueError(f"Unsupported dashboard type: {dashboard_type}")

        report_id = self.report_ids[dashboard_type]
        if not report_id:
            raise ValueError(f"No report ID configured for dashboard type: {dashboard_type}")

        base_url = f"https://datastudio.google.com/reporting/{report_id}"

        # Add filters as URL parameters
        if filters:
            params = {}
            if "user_id" in filters:
                params["params"] = f"user_id:{filters['user_id']}"
            if "time_range" in filters:
                params["_g"] = f"(time:(from:{filters['time_range'].get('from', 'now-30d')},to:{filters['time_range'].get('to', 'now')}))"

            if params:
                url_params = urlencode(params)
                return f"{base_url}?{url_params}"

        return base_url