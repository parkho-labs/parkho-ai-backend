"""News API request schemas"""

from pydantic import BaseModel


class SummarizeRequest(BaseModel):
    """Request model for article summarization"""
    summary_type: str = "brief"  # "brief" or "detailed"


# Note: News fetching is now handled by background cron jobs only.
# No request schemas needed for frontend-triggered fetching.