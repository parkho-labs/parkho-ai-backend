"""
Strategy Factory for Content Processing

Handles strategy selection and creation based on configuration and content type.
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from .base_strategy import ContentProcessingStrategy
from ..config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class StrategySelectionResult:
    """Result of strategy selection process"""
    strategy: ContentProcessingStrategy
    strategy_name: str
    selection_reason: str
    fallback_available: bool = False


class ContentProcessingStrategyFactory:
    """
    Factory for creating and selecting content processing strategies.

    Supports automatic strategy selection based on content type, configuration,
    and system capabilities.
    """

    def __init__(self):
        self._strategies = {}
        self._register_strategies()

    def _register_strategies(self):
        """Register all available strategies"""
        # Lazy import to avoid circular dependencies
        try:
            from .complex_pipeline_strategy import ComplexPipelineStrategy
            self._strategies["complex_pipeline"] = ComplexPipelineStrategy
        except ImportError:
            logger.warning("ComplexPipelineStrategy not available")

        try:
            from .direct_gemini_strategy import DirectGeminiStrategy
            self._strategies["direct_gemini"] = DirectGeminiStrategy
        except ImportError:
            logger.warning("DirectGeminiStrategy not available")

    def create_strategy(
        self,
        strategy_type: str,
        config: Optional[Dict[str, Any]] = None
    ) -> ContentProcessingStrategy:
        """
        Create a specific strategy instance.

        Args:
            strategy_type: Name of the strategy to create
            config: Optional configuration dictionary

        Returns:
            ContentProcessingStrategy instance

        Raises:
            ValueError: If strategy type is not available
        """
        if strategy_type not in self._strategies:
            available = list(self._strategies.keys())
            raise ValueError(
                f"Strategy '{strategy_type}' not available. "
                f"Available strategies: {available}"
            )

        strategy_class = self._strategies[strategy_type]
        return strategy_class(config or {})

    def select_strategy(
        self,
        input_config: List[Dict[str, Any]],
        job_config: Dict[str, Any]
    ) -> StrategySelectionResult:
        """
        Automatically select the best strategy for the given input.

        Args:
            input_config: List of content source configurations
            job_config: Job-level configuration (num_questions, difficulty, etc.)

        Returns:
            StrategySelectionResult with selected strategy and reasoning
        """
        settings = get_settings()
        config = {**job_config, "settings": settings}

        # Check if user specified a strategy
        preferred_strategy = job_config.get("processing_strategy") or settings.content_processing_strategy

        if preferred_strategy and preferred_strategy != "auto":
            try:
                strategy = self.create_strategy(preferred_strategy, config)
                if strategy.can_process_job(input_config):
                    return StrategySelectionResult(
                        strategy=strategy,
                        strategy_name=preferred_strategy,
                        selection_reason=f"User specified strategy: {preferred_strategy}",
                        fallback_available=self._has_fallback_strategy(preferred_strategy, input_config)
                    )
                else:
                    logger.warning(f"Preferred strategy '{preferred_strategy}' cannot process this job")
            except ValueError as e:
                logger.warning(f"Cannot create preferred strategy: {e}")

        # Auto-select strategy based on content analysis
        return self._auto_select_strategy(input_config, config)

    def _auto_select_strategy(
        self,
        input_config: List[Dict[str, Any]],
        config: Dict[str, Any]
    ) -> StrategySelectionResult:
        """
        Automatically select the best strategy based on content analysis.

        Selection logic:
        1. If only YouTube URLs and Gemini enabled → Direct Gemini (fast & reliable)
        2. If mixed content types → Complex Pipeline (full flexibility)
        3. If Gemini unavailable → Complex Pipeline (fallback)
        """
        settings = config["settings"]

        # Analyze content types
        content_types = [source.get("content_type") for source in input_config]
        unique_types = set(content_types)

        # Check for YouTube-only content
        is_youtube_only = unique_types == {"youtube"}
        has_youtube = "youtube" in unique_types

        # Strategy selection logic
        if (is_youtube_only and
            settings.gemini_video_api_enabled and
            "direct_gemini" in self._strategies):

            strategy = self.create_strategy("direct_gemini", config)
            return StrategySelectionResult(
                strategy=strategy,
                strategy_name="direct_gemini",
                selection_reason="YouTube-only content detected, Gemini API available",
                fallback_available=True
            )

        # Default to complex pipeline for all other cases
        if "complex_pipeline" in self._strategies:
            strategy = self.create_strategy("complex_pipeline", config)
            fallback_available = (has_youtube and
                                settings.gemini_video_api_enabled and
                                "direct_gemini" in self._strategies)

            return StrategySelectionResult(
                strategy=strategy,
                strategy_name="complex_pipeline",
                selection_reason="Mixed content types or Gemini unavailable",
                fallback_available=fallback_available
            )

        # No strategies available
        raise ValueError("No content processing strategies available")

    def _has_fallback_strategy(
        self,
        primary_strategy: str,
        input_config: List[Dict[str, Any]]
    ) -> bool:
        """Check if a fallback strategy is available for the given content"""
        settings = get_settings()

        if not settings.enable_strategy_fallback:
            return False

        # Determine potential fallback strategies
        if primary_strategy == "direct_gemini":
            # Can fallback to complex pipeline for any content
            return "complex_pipeline" in self._strategies

        elif primary_strategy == "complex_pipeline":
            # Can fallback to Gemini for YouTube-only content
            content_types = [source.get("content_type") for source in input_config]
            is_youtube_only = set(content_types) == {"youtube"}
            return (is_youtube_only and
                    settings.gemini_video_api_enabled and
                    "direct_gemini" in self._strategies)

        return False

    def get_fallback_strategy(
        self,
        failed_strategy: str,
        input_config: List[Dict[str, Any]],
        config: Dict[str, Any]
    ) -> Optional[ContentProcessingStrategy]:
        """
        Get a fallback strategy when the primary strategy fails.

        Args:
            failed_strategy: Name of the strategy that failed
            input_config: Content source configurations
            config: Job configuration

        Returns:
            Fallback strategy instance or None if no fallback available
        """
        settings = config.get("settings") or get_settings()

        if not settings.enable_strategy_fallback:
            return None

        logger.info(f"Selecting fallback strategy for failed '{failed_strategy}'")

        if failed_strategy == "direct_gemini":
            # Fallback from Gemini to Complex Pipeline
            if "complex_pipeline" in self._strategies:
                strategy = self.create_strategy("complex_pipeline", config)
                if strategy.can_process_job(input_config):
                    logger.info("Using complex pipeline as fallback for failed Gemini strategy")
                    return strategy

        elif failed_strategy == "complex_pipeline":
            # Fallback from Complex Pipeline to Gemini (YouTube only)
            content_types = [source.get("content_type") for source in input_config]
            is_youtube_only = set(content_types) == {"youtube"}

            if (is_youtube_only and
                settings.gemini_video_api_enabled and
                "direct_gemini" in self._strategies):

                strategy = self.create_strategy("direct_gemini", config)
                if strategy.can_process_job(input_config):
                    logger.info("Using direct Gemini as fallback for failed complex pipeline")
                    return strategy

        logger.warning(f"No fallback strategy available for '{failed_strategy}'")
        return None

    def get_available_strategies(self) -> List[str]:
        """Get list of available strategy names"""
        return list(self._strategies.keys())

    def get_strategy_info(self, strategy_name: str) -> Dict[str, Any]:
        """Get information about a specific strategy"""
        if strategy_name not in self._strategies:
            raise ValueError(f"Strategy '{strategy_name}' not available")

        # Create temporary instance to get info
        strategy = self.create_strategy(strategy_name, {})

        return {
            "name": strategy_name,
            "display_name": strategy.get_strategy_name(),
            "supported_content_types": strategy.get_supported_content_types(),
            "description": strategy.__class__.__doc__ or "No description available"
        }