"""
Base Strategy Interface for Content Processing

Defines the contract that all content processing strategies must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from enum import Enum


class ProcessingStatus(Enum):
    """Status of content processing"""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL_SUCCESS = "partial_success"


@dataclass
class ProcessingResult:
    """Result of content processing strategy execution"""
    status: ProcessingStatus
    content_text: Optional[str] = None
    summary: Optional[str] = None
    questions: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    strategy_used: Optional[str] = None
    processing_time_seconds: Optional[float] = None

    @property
    def success(self) -> bool:
        return self.status == ProcessingStatus.SUCCESS

    @property
    def has_content(self) -> bool:
        return bool(self.content_text)

    @property
    def has_questions(self) -> bool:
        return bool(self.questions)


class ContentProcessingStrategy(ABC):
    """
    Abstract base class for all content processing strategies.

    Each strategy implements a different approach to processing content
    and generating summaries and questions.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize strategy with configuration.

        Args:
            config: Configuration dictionary containing strategy-specific settings
        """
        self.config = config
        self.strategy_name = self.get_strategy_name()

    @abstractmethod
    async def process_content(self, job_id: int) -> ProcessingResult:
        """
        Process content for the given job and return results.

        Args:
            job_id: ID of the content job to process

        Returns:
            ProcessingResult containing the processing outcome
        """
        pass

    @abstractmethod
    def supports_content_type(self, content_type: str) -> bool:
        """
        Check if this strategy supports the given content type.

        Args:
            content_type: Type of content (youtube, pdf, docx, web_url, etc.)

        Returns:
            True if this strategy can process the content type
        """
        pass

    @abstractmethod
    def get_strategy_name(self) -> str:
        """
        Get the name of this strategy.

        Returns:
            Human-readable strategy name
        """
        pass

    @abstractmethod
    def get_supported_content_types(self) -> List[str]:
        """
        Get list of content types supported by this strategy.

        Returns:
            List of supported content type strings
        """
        pass

    def can_process_job(self, input_config: List[Dict[str, Any]]) -> bool:
        """
        Check if this strategy can process all content sources in the job.

        Args:
            input_config: List of content source configurations

        Returns:
            True if all content sources are supported
        """
        for source in input_config:
            content_type = source.get("content_type")
            if not self.supports_content_type(content_type):
                return False
        return True

    def get_expected_processing_time(self, input_config: List[Dict[str, Any]]) -> float:
        """
        Estimate processing time for the given input configuration.

        Args:
            input_config: List of content source configurations

        Returns:
            Estimated processing time in seconds
        """
        # Default implementation - strategies should override for better estimates
        return 60.0 * len(input_config)  # 1 minute per content source

    def get_priority_score(self, input_config: List[Dict[str, Any]]) -> int:
        """
        Get priority score for this strategy given the input configuration.
        Higher scores indicate better suitability for the content.

        Args:
            input_config: List of content source configurations

        Returns:
            Priority score (0-100, higher is better)
        """
        # Default implementation - strategies should override
        if self.can_process_job(input_config):
            return 50  # Neutral priority
        return 0  # Cannot process