from datetime import datetime
from typing import Optional, List, Dict, Generic, TypeVar, Any
from enum import Enum

from pydantic import BaseModel, Field

T = TypeVar('T')

class StandardAPIResponse(BaseModel, Generic[T]):
    status: str = Field(..., description="success or error")
    body: Optional[T] = Field(None, description="Response body")
    message: Optional[str] = Field(None, description="Human readable message")
    error_code: Optional[str] = Field(None, description="Error code for client handling")

    @classmethod
    def success(cls, data: T, message: str = "Success"):
        return cls(status="success", data=data, message=message)

    @classmethod
    def error(cls, message: str, error_code: str = None):
        return cls(status="error", message=message, error_code=error_code)


class JobStatus(str, Enum):
    PENDING = "pending"      # Job is queued, waiting to start
    RUNNING = "running"      # Job has started and is actively processing
    SUCCESS = "success"      # Job completed successfully
    FAILED = "failed"        # Job failed with errors
    CANCELLED = "cancelled"  # Job was cancelled by user


class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"
    MULTIPLE_CORRECT = "multiple_correct"


class QuestionTypeCount(BaseModel):
    question_type: QuestionType
    count: int


class QuestionCountsResponse(BaseModel):
    counts: List[QuestionTypeCount]

    def get_count_for_type(self, question_type: QuestionType) -> int:
        for item in self.counts:
            if item.question_type == question_type:
                return item.count
        return 0


class DifficultyLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class LLMProvider(str, Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    ANTHROPIC = "anthropic"

class InputType(str, Enum):
    YOUTUBE = "youtube"
    WEB_URL = "web_url"
    COLLECTION = "collection"
    FILES = "files"


class ContentSubject(str, Enum):
    PHYSICS = "physics"
    MATHEMATICS = "mathematics"
    CHEMISTRY = "chemistry"
    BIOLOGY = "biology"
    GENERAL = "general"


class ContentInput(BaseModel):
    content_type: InputType
    id: str


class ContentProcessingRequest(BaseModel):
    input_config: List[ContentInput] = Field(min_items=1)
    question_types: Dict[str, int] = Field(default={"multiple_choice": 5}, description="Question types with counts")
    difficulty_level: DifficultyLevel = Field(default=DifficultyLevel.INTERMEDIATE)
    generate_summary: bool = Field(default=True)
    llm_provider: LLMProvider = Field(default=LLMProvider.OPENAI)
    collection_name: Optional[str] = Field(default=None, description="Collection to use for RAG context")
    should_add_to_collection: bool = Field(default=False, description="Whether to add processed content to the collection")
    structured_response: bool = Field(default=True, description="Enable structured JSON response for question generation")

    class Config:
        json_schema_extra = {
            "example": {
                "input_config": [
                    {"content_type": "youtube", "id": "https://youtu.be/abc123"},
                    {"content_type": "files", "id": "file-hash-456"}
                ],
                "question_types": {"multiple_choice": 3, "short_answer": 2},
                "difficulty_level": "intermediate",
                "generate_summary": True,
                "llm_provider": "openai",
                "collection_name": "physics_course",
                "should_add_to_collection": True,
                "structured_response": True
            }
        }


class ContentJobBase(BaseModel):
    status: JobStatus
    created_at: datetime
    completed_at: Optional[datetime]
    title: Optional[str]


class ContentJobResponse(ContentJobBase):
    id: int
    progress: float = Field(..., ge=0.0, le=100.0)
    error_message: Optional[str]
    input_url: Optional[str] = None
    file_ids: List[str] = Field(default=[])

    class Config:
        from_attributes = True

class ContentResults(ContentJobBase):
    job_id: int
    processing_duration_seconds: Optional[int]


class FileUploadResponse(BaseModel):
    file_id: str
    filename: str
    file_size: int
    content_type: str
    upload_timestamp: datetime

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


class SummaryResponse(BaseModel):
    summary: Optional[str]


class ContentTextResponse(BaseModel):
    content_text: Optional[str]


class ContentJobsListResponse(BaseModel):
    total: int
    jobs: List[ContentJobResponse]


class QuizQuestionResponse(BaseModel):
    question_id: str
    question: str
    type: str
    options: Optional[List[str]] = None
    context: Optional[str] = None
    max_score: int


class QuestionConfig(BaseModel):
    type: QuestionType
    options: Optional[Dict[str, str]] = None
    requires_diagram: bool = False
    diagram_type: Optional[str] = None
    diagram_elements: Optional[Dict[str, Any]] = None

class QuestionMetadata(BaseModel):
    video_timestamp: Optional[str] = None
    sources: Optional[Dict[str, Any]] = None

class QuizQuestion(BaseModel):
    question_id: str
    question: str
    question_config: QuestionConfig
    metadata: QuestionMetadata = Field(default_factory=dict)
    max_score: int = 1

class QuizResponse(BaseModel):
    quiz_id: str
    quiz_title: str
    questions: List[QuizQuestion]
    total_questions: int
    total_score: int
    summary: Optional[str] = None

class QuizSubmission(BaseModel):
    answers: Dict[str, str]

class QuizResult(BaseModel):
    question_id: str
    user_answer: str
    correct_answer: str
    is_correct: bool
    score: int

class QuizEvaluationResult(BaseModel):
    total_score: int
    max_possible_score: int
    percentage: float
    results: List[QuizResult]


class RAGFileUploadResponse(BaseModel):
    file_id: str
    filename: str
    status: str
    message: str


class RAGCollectionCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class RAGCollectionInfo(BaseModel):
    name: str
    created_at: str
    file_count: int


class RAGCollectionResponse(BaseModel):
    status: str
    message: str
    body: Optional[Dict[str, List[RAGCollectionInfo]]] = None


class RAGFileItem(BaseModel):
    file_id: str
    type: str = Field(default="file")
    name: str


class RAGLinkContentRequest(BaseModel):
    content_items: List[RAGFileItem]


class RAGLinkContentResponse(BaseModel):
    name: str
    file_id: str
    type: str
    created_at: Optional[str] = None
    indexing_status: str
    status_code: int
    message: str


class RAGUnlinkContentRequest(BaseModel):
    file_ids: List[str]


class RAGFileDetail(BaseModel):
    file_id: str
    filename: str
    file_type: str
    file_size: int
    upload_date: str


class RAGCollectionFilesResponse(BaseModel):
    status: str
    message: str
    body: Optional[Dict[str, List[RAGFileDetail]]] = None


class RAGFilesListResponse(BaseModel):
    status: str
    message: str
    body: Optional[Dict[str, List[RAGFileDetail]]] = None


class RAGQueryRequest(BaseModel):
    query: str
    enable_critic: bool = True


class RAGQueryResponse(BaseModel):
    status: str
    message: str
    body: Optional[Dict[str, Any]] = None


class RAGEmbedding(BaseModel):
    text: str
    source: Optional[str] = None


class RAGEmbeddingsResponse(BaseModel):
    status: str
    message: str
    body: Optional[Dict[str, List[RAGEmbedding]]] = None