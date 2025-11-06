from abc import ABC, abstractmethod
from typing import Dict, Any, List


class AnalyticsDashboardProvider(ABC):
    """Abstract base class for analytics dashboard providers."""

    @abstractmethod
    def get_dashboard_url(self, dashboard_type: str, filters: Dict[str, Any] = None) -> str:
        """
        Get the embeddable dashboard URL for the specified type.

        Args:
            dashboard_type: Type of dashboard (learning, quiz-performance, content-effectiveness, user-insights)
            filters: Optional filters to apply to the dashboard

        Returns:
            Embeddable dashboard URL
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Get the name of the provider.

        Returns:
            Provider name (e.g., 'google_studio', 'kibana')
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """
        Check if the provider is properly configured.

        Returns:
            True if provider is configured and ready to use
        """
        pass

    @abstractmethod
    def get_supported_dashboard_types(self) -> List[str]:
        """
        Get list of supported dashboard types.

        Returns:
            List of supported dashboard type names
        """
        pass


class DashboardType:
    """Constants for dashboard types."""
    LEARNING = "learning"
    QUIZ_PERFORMANCE = "quiz-performance"
    CONTENT_EFFECTIVENESS = "content-effectiveness"
    USER_INSIGHTS = "user-insights"

    @classmethod
    def all(cls) -> List[str]:
        return [cls.LEARNING, cls.QUIZ_PERFORMANCE, cls.CONTENT_EFFECTIVENESS, cls.USER_INSIGHTS]