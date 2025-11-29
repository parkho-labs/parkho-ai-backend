"""
Performance measurement utilities for timing workflow stages.
"""

import time
import functools
from typing import Optional
from contextlib import contextmanager


class PerformanceTimer:
    """Simple performance timer for measuring processing stages."""

    def __init__(self, stage_name: str):
        self.stage_name = stage_name
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    def start(self) -> None:
        """Start timing the stage."""
        self.start_time = time.time()
        print(f"[PERF] Starting: {self.stage_name}")

    def stop(self) -> float:
        """Stop timing and return duration in seconds."""
        if self.start_time is None:
            raise ValueError("Timer not started")

        self.end_time = time.time()
        duration = self.end_time - self.start_time
        print(f"[PERF] Completed: {self.stage_name} | Duration: {duration:.3f}s")
        return duration

    @property
    def duration(self) -> float:
        """Get duration if timing is complete."""
        if self.start_time is None or self.end_time is None:
            raise ValueError("Timing not complete")
        return self.end_time - self.start_time


@contextmanager
def time_stage(stage_name: str):
    """Context manager for timing a code block."""
    timer = PerformanceTimer(stage_name)
    timer.start()
    try:
        yield timer
    finally:
        timer.stop()


def time_function(stage_name: Optional[str] = None):
    """Decorator for timing function execution."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            name = stage_name or f"{func.__module__}.{func.__name__}"
            with time_stage(name):
                return func(*args, **kwargs)
        return wrapper
    return decorator


class WorkflowTimer:
    """Timer for tracking overall workflow performance."""

    def __init__(self):
        self.stages = []
        self.total_start = None

    def start_workflow(self):
        """Start timing the entire workflow."""
        self.total_start = time.time()
        print(f"[PERF] ====== WORKFLOW STARTED ======")

    def time_stage(self, stage_name: str):
        """Return a context manager for timing a stage."""
        return time_stage(stage_name)

    def complete_workflow(self):
        """Complete timing and print summary."""
        if self.total_start is None:
            return

        total_duration = time.time() - self.total_start
        print(f"[PERF] ====== WORKFLOW COMPLETED ======")
        print(f"[PERF] TOTAL PROCESSING TIME: {total_duration:.3f}s")
        print(f"[PERF] =====================================")