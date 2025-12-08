"""
Audio Cache Service for YouTube video audio files.

Manages caching of downloaded audio files with TTL-based expiration,
integrity validation, and automatic cleanup.
"""

import asyncio
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional
import structlog

logger = structlog.get_logger(__name__)


class AudioCacheService:
    """
    Service for caching YouTube audio files with TTL management.

    Features:
    - Video ID-based cache keys
    - Configurable TTL (default: 7 days)
    - Integrity validation (file size checks)
    - Automatic cleanup of expired files
    - Thread-safe operations
    - Cache statistics tracking
    """

    def __init__(self, cache_dir: Path, default_ttl_days: int = 7):
        """
        Initialize the audio cache service.

        Args:
            cache_dir: Directory path for storing cached audio files
            default_ttl_days: Default time-to-live for cached files in days
        """
        self.cache_dir = Path(cache_dir)
        self.default_ttl_days = default_ttl_days
        self.cache_stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "total_files": 0,
            "total_size_mb": 0.0
        }

    @property
    def is_enabled(self) -> bool:
        """Check if audio caching is enabled."""
        return True

        # Create cache directory if it doesn't exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "audio_cache_service_initialized",
            cache_dir=str(self.cache_dir),
            ttl_days=self.default_ttl_days
        )

    def _get_cache_path(self, video_id: str) -> Path:
        """
        Get the cache file path for a video ID.

        Args:
            video_id: YouTube video ID

        Returns:
            Path object for the cached audio file
        """
        # Sanitize video_id to ensure it's filesystem-safe
        safe_video_id = "".join(c for c in video_id if c.isalnum() or c in ['-', '_'])
        return self.cache_dir / f"{safe_video_id}.mp3"

    def _is_file_expired(self, file_path: Path) -> bool:
        """
        Check if a cached file has expired based on TTL.

        Args:
            file_path: Path to the cached file

        Returns:
            True if file is expired, False otherwise
        """
        if not file_path.exists():
            return True

        # Get file modification time
        file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        expiration_time = file_mtime + timedelta(days=self.default_ttl_days)

        is_expired = datetime.now() > expiration_time

        if is_expired:
            logger.debug(
                "cache_file_expired",
                file_path=str(file_path),
                age_days=(datetime.now() - file_mtime).days
            )

        return is_expired

    def _validate_file_integrity(self, file_path: Path) -> bool:
        """
        Validate the integrity of a cached audio file.

        Args:
            file_path: Path to the cached file

        Returns:
            True if file is valid, False otherwise
        """
        if not file_path.exists():
            return False

        # Check file size (must be > 1KB to be valid)
        file_size = file_path.stat().st_size

        if file_size < 1024:  # Less than 1KB
            logger.warning(
                "cache_file_too_small",
                file_path=str(file_path),
                size_bytes=file_size
            )
            return False

        return True

    async def get_cached_audio(self, video_id: str) -> Optional[Path]:
        """
        Retrieve cached audio file for a video ID.

        Args:
            video_id: YouTube video ID

        Returns:
            Path to cached audio file if valid, None otherwise
        """
        cache_path = self._get_cache_path(video_id)

        # Check if file exists
        if not cache_path.exists():
            self.cache_stats["cache_misses"] += 1
            logger.debug("cache_miss", video_id=video_id)
            return None

        # Check if file is expired
        if self._is_file_expired(cache_path):
            self.cache_stats["cache_misses"] += 1
            logger.info("cache_expired", video_id=video_id)
            # Delete expired file
            await self._delete_file(cache_path)
            return None

        # Validate file integrity
        if not self._validate_file_integrity(cache_path):
            self.cache_stats["cache_misses"] += 1
            logger.warning("cache_invalid", video_id=video_id)
            # Delete corrupted file
            await self._delete_file(cache_path)
            return None

        # Cache hit!
        self.cache_stats["cache_hits"] += 1
        logger.info(
            "cache_hit",
            video_id=video_id,
            file_size_mb=cache_path.stat().st_size / (1024 * 1024)
        )

        return cache_path

    async def cache_audio(self, video_id: str, audio_path: Path) -> Path:
        """
        Cache an audio file for a video ID.

        Args:
            video_id: YouTube video ID
            audio_path: Path to the audio file to cache

        Returns:
            Path to the cached file

        Raises:
            ValueError: If source audio file doesn't exist or is invalid
        """
        if not audio_path.exists():
            raise ValueError(f"Source audio file does not exist: {audio_path}")

        # Validate source file
        source_size = audio_path.stat().st_size
        if source_size < 1024:
            raise ValueError(f"Source audio file too small: {source_size} bytes")

        cache_path = self._get_cache_path(video_id)

        # Copy or move file to cache location
        def copy_file():
            """Synchronous file copy operation."""
            import shutil
            if audio_path != cache_path:
                shutil.copy2(audio_path, cache_path)
            return cache_path

        # Run file copy in executor to avoid blocking
        loop = asyncio.get_event_loop()
        result_path = await loop.run_in_executor(None, copy_file)

        # Update stats
        self.cache_stats["total_files"] = len(list(self.cache_dir.glob("*.mp3")))
        self.cache_stats["total_size_mb"] = sum(
            f.stat().st_size for f in self.cache_dir.glob("*.mp3")
        ) / (1024 * 1024)

        logger.info(
            "audio_cached",
            video_id=video_id,
            cache_path=str(cache_path),
            file_size_mb=source_size / (1024 * 1024)
        )

        return result_path

    async def invalidate_cache(self, video_id: str) -> bool:
        """
        Invalidate (delete) cached audio for a video ID.

        Args:
            video_id: YouTube video ID

        Returns:
            True if file was deleted, False if it didn't exist
        """
        cache_path = self._get_cache_path(video_id)

        if not cache_path.exists():
            logger.debug("cache_invalidate_not_found", video_id=video_id)
            return False

        await self._delete_file(cache_path)

        logger.info("cache_invalidated", video_id=video_id)
        return True

    async def _delete_file(self, file_path: Path) -> None:
        """
        Delete a file asynchronously.

        Args:
            file_path: Path to the file to delete
        """
        def delete():
            """Synchronous file deletion."""
            try:
                file_path.unlink()
            except Exception as e:
                logger.error("file_deletion_failed", file_path=str(file_path), error=str(e))

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, delete)

    async def cleanup_expired_files(self) -> int:
        """
        Clean up all expired cached files.

        Returns:
            Number of files deleted
        """
        deleted_count = 0

        logger.info("cache_cleanup_started", cache_dir=str(self.cache_dir))

        for file_path in self.cache_dir.glob("*.mp3"):
            if self._is_file_expired(file_path):
                await self._delete_file(file_path)
                deleted_count += 1

        # Update stats after cleanup
        self.cache_stats["total_files"] = len(list(self.cache_dir.glob("*.mp3")))
        self.cache_stats["total_size_mb"] = sum(
            f.stat().st_size for f in self.cache_dir.glob("*.mp3")
        ) / (1024 * 1024)

        logger.info(
            "cache_cleanup_completed",
            deleted_count=deleted_count,
            remaining_files=self.cache_stats["total_files"],
            total_size_mb=self.cache_stats["total_size_mb"]
        )

        return deleted_count

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics including:
            - cache_hits: Number of successful cache retrievals
            - cache_misses: Number of cache misses
            - cache_hit_rate: Percentage of cache hits
            - total_files: Current number of cached files
            - total_size_mb: Total size of cache in MB
        """
        total_requests = self.cache_stats["cache_hits"] + self.cache_stats["cache_misses"]
        cache_hit_rate = (
            (self.cache_stats["cache_hits"] / total_requests * 100)
            if total_requests > 0 else 0.0
        )

        return {
            "cache_hits": self.cache_stats["cache_hits"],
            "cache_misses": self.cache_stats["cache_misses"],
            "cache_hit_rate": round(cache_hit_rate, 2),
            "total_files": self.cache_stats["total_files"],
            "total_size_mb": round(self.cache_stats["total_size_mb"], 2)
        }

    async def schedule_periodic_cleanup(self, interval_hours: int = 24) -> None:
        """
        Schedule periodic cleanup of expired cache files.

        Args:
            interval_hours: Interval between cleanup runs in hours
        """
        logger.info(
            "cache_periodic_cleanup_scheduled",
            interval_hours=interval_hours
        )

        while True:
            await asyncio.sleep(interval_hours * 3600)  # Convert hours to seconds
            await self.cleanup_expired_files()
