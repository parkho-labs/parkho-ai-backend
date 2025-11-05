from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl, validator


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"


class DifficultyLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class InputType(str, Enum):
    YOUTUBE = "youtube"
    PDF = "pdf"
    DOCX = "docx"
    WEB_URL = "web_url"


class ContentInput(BaseModel):
    content_type: InputType
    id: str


class ContentProcessingRequest(BaseModel):
    input_config: List[ContentInput] = Field(min_items=1)
    question_types: List[QuestionType] = Field(default=[QuestionType.MULTIPLE_CHOICE])
    difficulty_level: DifficultyLevel = Field(default=DifficultyLevel.INTERMEDIATE)
    num_questions: int = Field(default=5, ge=1, le=50)
    generate_summary: bool = Field(default=True)
    llm_provider: LLMProvider = Field(default=LLMProvider.OPENAI)

    class Config:
        json_schema_extra = {
            "example": {
                "input_config": [
                    {"content_type": "youtube", "id": "https://youtu.be/abc123"},
                    {"content_type": "pdf", "id": "file-hash-456"}
                ],
                "question_types": ["multiple_choice", "short_answer"],
                "difficulty_level": "intermediate",
                "num_questions": 5,
                "generate_summary": True,
                "llm_provider": "openai"
            }
        }


class FileUploadResponse(BaseModel):
    file_id: str
    filename: str
    file_size: int
    content_type: Optional[str]
    upload_timestamp: datetime


class ContentJobResponse(BaseModel):
    id: int
    status: JobStatus
    progress: float = Field(..., ge=0.0, le=100.0)
    created_at: datetime
    completed_at: Optional[datetime]
    title: Optional[str]
    error_message: Optional[str]
    input_url: Optional[str] = None
    file_ids: List[str] = Field(default=[])

    class Config:
        from_attributes = True


# Individual file processing result for 207 Multi-Status response
class FileProcessingResult(BaseModel):
    file_id: str
    job_id: Optional[int] = None
    status: JobStatus
    message: str
    estimated_duration_minutes: Optional[int] = None
    websocket_url: Optional[str] = None
    error_details: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "file_id": "file_abc123",
                "job_id": 42,
                "status": "processing",
                "message": "File processing started successfully",
                "estimated_duration_minutes": 5,
                "websocket_url": "ws://127.0.0.1:8080/ws/jobs/42"
            }
        }


# 207 Multi-Status response for content processing
class MultiStatusProcessingResponse(BaseModel):
    results: List[FileProcessingResult]

    class Config:
        json_schema_extra = {
            "example": {
                "results": [
                    {
                        "file_id": "file_abc123",
                        "job_id": 42,
                        "status": "processing",
                        "message": "File processing started successfully",
                        "estimated_duration_minutes": 5,
                        "websocket_url": "ws://127.0.0.1:8080/ws/jobs/42"
                    }
                ]
            }
        }


# Legacy single job response (kept for backward compatibility)
class ProcessingJobResponse(BaseModel):
    job_id: int
    status: JobStatus
    message: str
    estimated_duration_minutes: int
    websocket_url: str


class ContentResults(BaseModel):
    job_id: int
    status: JobStatus
    title: Optional[str]
    processing_duration_seconds: Optional[int]
    created_at: datetime
    completed_at: Optional[datetime]
    summary: Optional[str] = None
    questions: Optional[List[dict]] = None
    content_text: Optional[str] = None


class SummaryResponse(BaseModel):
    summary: Optional[str]


class ContentTextResponse(BaseModel):
    content_text: Optional[str]


class WebSocketMessage(BaseModel):
    job_id: int
    message_type: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ContentJobsListResponse(BaseModel):
    total: int
    jobs: List[ContentJobResponse]


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    database: str
    timestamp: datetime
    environment: str
    uptime_check: str


class QuizQuestionResponse(BaseModel):
    question_id: str
    question: str
    type: str
    options: Optional[List[str]] = None
    context: Optional[str] = None
    max_score: int


class QuizResponse(BaseModel):
    questions: List[QuizQuestionResponse]
    total_questions: int
    max_score: int


class QuizSubmission(BaseModel):
    answers: Dict[str, str]