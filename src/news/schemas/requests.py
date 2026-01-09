"""News API request schemas"""

from pydantic import BaseModel, Field


class SummarizeRequest(BaseModel):
    """Request model for article summarization"""
    summary_type: str = "brief"  # "brief" or "detailed"


class NewsAskQuestionRequest(BaseModel):
    """Request model for asking questions about a news article"""
    question: str = Field(
        ..., 
        min_length=5, 
        max_length=500, 
        description="Question about the news article"
    )


# Note: News fetching is now handled by background cron jobs only.
# No request schemas needed for frontend-triggered fetching.