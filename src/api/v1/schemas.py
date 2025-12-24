from datetime import datetime
from typing import Optional, List, Dict, Generic, TypeVar, Any
from enum import Enum

from pydantic import BaseModel, Field, field_validator

T = TypeVar('T')

class StandardAPIResponse(BaseModel, Generic[T]):
    status: str = Field(..., description="success or error")
    body: Optional[T] = Field(None, description="Response body")
    message: Optional[str] = Field(None, description="Human readable message")
    error_code: Optional[str] = Field(None, description="Error code for client handling")

    @classmethod
    def success(cls, data: T, message: str = "Success"):
        return cls(status="success", body=data, message=message)

    @classmethod
    def error(cls, message: str, error_code: str = None):
        return cls(status="error", message=message, error_code=error_code)


class JobStatus(str, Enum):
    PENDING = "JOB_PENDING"
    RUNNING = "JOB_RUNNING"
    SUCCESS = "JOB_SUCCESS"
    FAILED = "JOB_FAILED"
    CANCELLED = "JOB_CANCELLED"


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


class FileUploadUrlRequest(BaseModel):
    filename: str
    content_type: str
    file_size: int


class PresignedUrlResponse(BaseModel):
    upload_url: str
    file_id: str
    gcs_path: str
    cleanup_after: datetime



class FileViewResponse(BaseModel):
    url: str
    type: str = Field(..., description="'file' or 'external'")
    content_type: Optional[str] = None
    filename: Optional[str] = None


class FileConfirmRequest(BaseModel):
    file_id: str
    indexing: bool = True


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
    id: Optional[str] = None # Added id
    name: str
    created_at: Optional[str] = None # made optional
    file_count: int


class RAGCollectionResponse(BaseModel):
    status: str
    message: str
    # Relaxed to allow various body structures or strictly defined unions
    # For now, simplifying to generic Dict/Any to avoid strict validation errors during rapid dev
    # But following PR advice: we probably want specific models.
    # However, existing code uses this model for List Collections which returns Dict[str, List].
    # Create Collection returns single object.
    # Let's make body Any for flexibility or Union.
    body: Optional[Any] = None 


class RAGFileItem(BaseModel):
    file_id: str
    type: str = Field(default="file")
    name: str


class RAGLinkContentRequest(BaseModel):
    content_items: Optional[List[RAGFileItem]] = None # Deprecated?
    file_ids: Optional[List[str]] = None # New simpler request


class RAGLinkContentResponse(BaseModel):
    name: Optional[str] = None
    file_id: str
    type: Optional[str] = "file"
    created_at: Optional[str] = None
    indexing_status: Optional[str] = None
    status_code: int = 200
    message: str = "Success"


class RAGUnlinkContentRequest(BaseModel):
    file_ids: List[str]


class RAGFileDetail(BaseModel):
    file_id: str
    filename: str
    file_type: Optional[str] = None
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
    message: Optional[str] = None # Added message
    body: Optional[Dict[str, Any]] = None

class CollectionChatRequest(BaseModel):
    query: str
    answer_style: str = "detailed"
    max_chunks: int = 5

class CollectionSummaryResponse(BaseModel):
    summary: str
    processing_time_ms: int
    collection_id: Optional[str] = None
    chunks_analyzed: Optional[int] = None


class RAGEmbedding(BaseModel):
    text: str
    source: Optional[str] = None


class RAGEmbeddingsResponse(BaseModel):
    status: str
    message: str
    body: Optional[Dict[str, List[RAGEmbedding]]] = None


class LinkContentItem(BaseModel):
    type: str
    file_id: str
    collection_id: Optional[str] = None
    gcs_url: Optional[str] = None
    url: Optional[str] = None


class BatchLinkRequest(BaseModel):
    items: List[LinkContentItem]


class BatchItemResult(BaseModel):
    file_id: str
    status: str
    error: Optional[str] = None


class BatchLinkResponse(BaseModel):
    message: str
    batch_id: str
    results: List[BatchItemResult]


class StatusCheckRequest(BaseModel):
    file_ids: List[str]

class StatusItemResponse(BaseModel):
    file_id: str
    name: Optional[str] = None
    source: Optional[str] = None
    status: str
    error: Optional[str] = None

class StatusCheckResponse(BaseModel):
    message: str
    results: List[StatusItemResponse]

class QueryFilters(BaseModel):
    collection_ids: Optional[List[str]] = None
    file_ids: Optional[List[str]] = None

class QueryRequest(BaseModel):
    query: str
    filters: Optional[QueryFilters] = None
    top_k: int = 5
    include_sources: bool = False

class SourceChunk(BaseModel):
    chunk_id: str
    chunk_text: str
    relevance_score: float
    file_id: str
    page_number: Optional[int] = None
    timestamp: Optional[str] = None
    concepts: List[str] = []

class QueryResponse(BaseModel):
    answer: str
    confidence: float = 0.0
    is_relevant: bool = False
    chunks: List[Any] = Field(default_factory=list)
    critic: Optional[Any] = None

# Retrieve works same as Query but chunks only. 
# Reusing schemas where possible but keeping distinct if needed.
# Doc says Retrieve works on chunks only. 
# RetrieveRequest in doc: query, filters, top_k, include_graph_context
# The existing RetrieveRequest matches doc roughly (include_graph_context present).

class RetrieveRequest(BaseModel):
    query: str
    filters: Optional[QueryFilters] = None
    top_k: int = 5
    include_graph_context: bool = True

class RetrieveResponse(BaseModel):
    success: bool
    results: List[SourceChunk]


class DeleteFileRequest(BaseModel):
    file_ids: List[str]

class DeleteFileResponse(BaseModel):
    message: str

class DeleteCollectionRequest(BaseModel):
    collection_id: str

class DeleteCollectionResponse(BaseModel):
    message: str


class QuestionFilter(BaseModel):
    collection_ids: Optional[List[str]] = None
    file_ids: Optional[List[str]] = None
    entities: Optional[List[str]] = None
    chunk_types: Optional[List[str]] = None
    chapters: Optional[List[str]] = None
    key_terms: Optional[List[str]] = None


class QuestionSpec(BaseModel):
    type: str
    count: int
    difficulty: str
    filters: Optional[QuestionFilter] = None


class QuestionContext(BaseModel):
    exam_type: Optional[str] = None
    subject: Optional[str] = None
    avoid_duplicates: Optional[bool] = True
    include_explanations: Optional[bool] = True
    language: Optional[str] = "english"


class RagQuestionGenerationRequest(BaseModel):
    questions: List[QuestionSpec]
    context: Optional[QuestionContext] = None


class GeneratedQuestion(BaseModel):
    id: str
    type: str
    question: str
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    difficulty: str
    metadata: Optional[Dict[str, Any]] = None


class RagQuestionGenerationResponse(BaseModel):
    questions: List[GeneratedQuestion]
    total_generated: int
    generation_time: Optional[float] = None


class ContentStatsRequest(BaseModel):
    collection_ids: Optional[List[str]] = None


class ContentStatistics(BaseModel):
    total_chunks: int
    unique_files: int
    unique_collections: int
    avg_text_length: float
    chunk_types: List[str]
    sample_chapters: List[str]


class ContentStatsResponse(BaseModel):
    success: bool
    statistics: ContentStatistics
    message: str


class SupportedQuestionType(BaseModel):
    type: str
    name: str
    description: str
    typical_time: str


class DifficultyLevel(BaseModel):
    level: str
    name: str
    description: str
    characteristics: List[str]


class SupportedTypesResponse(BaseModel):
    question_types: List[SupportedQuestionType]
    difficulty_levels: List[DifficultyLevel]
    filters: List[str]


class ContentValidationRequest(BaseModel):
    questions: List[QuestionSpec]


class ContentValidationResult(BaseModel):
    question_type: str
    difficulty: str
    requested_count: int
    available_count: int
    can_fulfill: bool


class ContentValidationResponse(BaseModel):
    validation_results: List[ContentValidationResult]
    overall_feasible: bool


class HealthCheckResponse(BaseModel):
    status: str
    neo4j_connected: bool
    total_chunks: int
    unique_files: int
    service_ready: bool
    timestamp: str


# =============================================================================
# LEGAL RAG ENGINE SCHEMAS (for /law/chat, /questions/generate, /retrieve)
# =============================================================================

# Legal Question Types (as documented in BACKEND_API_INTEGRATION.md)
class LegalQuestionType(str, Enum):
    ASSERTION_REASONING = "assertion_reasoning"
    MATCH_FOLLOWING = "match_following"
    COMPREHENSION = "comprehension"


class LegalDifficultyLevel(str, Enum):
    EASY = "easy"
    MODERATE = "moderate"
    DIFFICULT = "difficult"


# Law Chat Endpoint Schemas (/law/chat)
class LawChatRequest(BaseModel):
    question: str = Field(..., min_length=10, max_length=500, description="Legal question (10-500 chars)")
    enable_rag: bool = Field(default=True, description="If True, use RAG with all legal documents. If False, use direct LLM with legal system prompt")


class LawSource(BaseModel):
    text: str = Field(..., description="First 200 chars of source")
    article: str = Field(..., description="Article reference")


class LawChatResponse(BaseModel):
    answer: str
    sources: List[LawSource]
    total_chunks: int


# Legal Question Generation Schemas (/questions/generate)
class LegalQuestionSpec(BaseModel):
    type: LegalQuestionType
    difficulty: LegalDifficultyLevel
    count: int = Field(..., ge=1, le=10, description="Number of questions (1-10)")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Optional filters like collection_ids")


class LegalQuestionContext(BaseModel):
    subject: Optional[str] = Field(default=None, description="Subject context")


class LegalQuestionRequest(BaseModel):
    questions: List[LegalQuestionSpec]
    context: Optional[LegalQuestionContext] = None


# Legal Question Content Structures (matches documentation)
class AssertionReasoningQuestion(BaseModel):
    question_text: str
    assertion: str
    reason: str
    options: List[str]
    correct_option: str
    explanation: str
    difficulty: str
    source_chunks: List[str]


class MatchFollowingQuestion(BaseModel):
    question_text: str
    list_I: List[str]
    list_II: List[str]
    correct_matches: Dict[str, str]
    explanation: str
    difficulty: str
    source_chunks: List[str]


class ComprehensionSubQuestion(BaseModel):
    question_text: str
    options: List[str]
    correct_option: str
    explanation: str


class ComprehensionQuestion(BaseModel):
    passage: str
    questions: List[ComprehensionSubQuestion]
    difficulty: str
    source_chunks: List[str]


class LegalQuestionMetadata(BaseModel):
    question_id: str = Field(..., description="UUID")
    type: str
    difficulty: str
    estimated_time: int = Field(..., description="Estimated time in minutes")
    source_files: List[str]
    generated_at: str = Field(..., description="ISO timestamp")


class LegalQuestion(BaseModel):
    metadata: LegalQuestionMetadata
    content: Dict[str, Any] = Field(..., description="Question content based on type")


class LegalQuestionStats(BaseModel):
    total_requested: int
    by_type: Dict[str, int]
    by_difficulty: Dict[str, int]
    content_selection_time: float = Field(..., description="Time in seconds")
    generation_time: float = Field(..., description="Time in seconds")


class LegalQuestionResponse(BaseModel):
    success: bool
    total_generated: int
    attempt_id: Optional[int] = None
    questions: List[LegalQuestion]
    generation_stats: LegalQuestionStats
    errors: List[str] = Field(default=[])
    warnings: List[str] = Field(default=[])


# =============================================================================
# NEW LEGAL QUIZ APIS - CUSTOM AND MOCK QUIZ
# =============================================================================

# Custom Quiz - User specifies question types and counts
class CustomQuestionSpec(BaseModel):
    type: LegalQuestionType
    count: int = Field(..., ge=1, le=10, description="Number of questions (1-10)")

class CustomQuizRequest(BaseModel):
    questions: List[CustomQuestionSpec]
    difficulty: LegalDifficultyLevel = Field(default=LegalDifficultyLevel.MODERATE, description="Overall difficulty level")
    subject: Optional[str] = Field(default="Constitutional Law", description="Subject context")
    scope: List[str] = Field(default=["constitution"], description="Scope: constitution, bns, or both")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Optional filters like collection_ids")

# Mock Quiz - System generates random mix with equal distribution
class MockQuizRequest(BaseModel):
    total_questions: int = Field(..., ge=3, le=50, description="Total questions for mock quiz (3-50, must be divisible by 3)")
    subject: Optional[str] = Field(default="Constitutional Law", description="Subject context")
    scope: List[str] = Field(default=["constitution"], description="Scope: constitution, bns, or both")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Optional filters like collection_ids")

    @field_validator('total_questions')
    @classmethod
    def validate_total_questions(cls, v):
        if v % 3 != 0:
            raise ValueError('total_questions must be divisible by 3 for equal distribution')
        return v

# Enhanced response for both new APIs
class QuizGenerationResponse(BaseModel):
    success: bool
    total_generated: int
    total_requested: int
    attempt_id: Optional[int] = None
    questions: List[LegalQuestion]
    generation_stats: LegalQuestionStats
    quiz_metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional quiz metadata")
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

# Alias for standard QuestionGenerationResponse
QuestionGenerationResponse = QuizGenerationResponse


# Legal Content Retrieval Schemas (/retrieve)
class LegalRetrieveRequest(BaseModel):
    query: str
    user_id: str
    collection_ids: List[str]
    top_k: int = Field(default=10, le=20, description="Max 20 results")


class LegalChunk(BaseModel):
    chunk_id: str
    chunk_text: str
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    file_id: str
    page_number: Optional[int] = None
    concepts: List[str]


class LegalRetrieveResponse(BaseModel):
    success: bool
    results: List[LegalChunk]


# =============================================================================
# PYQ (Previous Year Questions) SCHEMAS
# =============================================================================

# Base PYQ Schemas
class ExamPaperSummary(BaseModel):
    id: int
    title: str
    year: int
    exam_name: str
    total_questions: int
    total_marks: float
    time_limit_minutes: int
    display_name: str
    description: Optional[str] = None
    created_at: Optional[str] = None


class ExamPaperDetail(BaseModel):
    id: int
    title: str
    year: int
    exam_name: str
    total_questions: int
    total_marks: float
    time_limit_minutes: int
    display_name: str
    description: Optional[str] = None
    questions: Optional[List[Dict[str, Any]]] = None
    created_at: Optional[str] = None


class PaperListStats(BaseModel):
    total_papers: int
    available_years: List[int]
    available_exams: List[str]
    year_range: Dict[str, Optional[int]]


class PaperListResponse(BaseModel):
    papers: List[ExamPaperSummary]
    summary: PaperListStats
    pagination: Dict[str, int]


# Exam Attempt Schemas
class StartAttemptResponse(BaseModel):
    attempt_id: int
    paper_id: int
    paper_title: str
    exam_name: str
    year: int
    total_questions: int
    total_marks: float
    time_limit_minutes: int
    started_at: Optional[str] = None
    questions: List[Dict[str, Any]]


class ExamAnswers(BaseModel):
    answers: Dict[str, str] = Field(..., description="Mapping of question_id to selected_answer")


class QuestionResult(BaseModel):
    question_id: int
    question_text: str
    correct_answer: str
    user_answer: Optional[str] = None
    is_correct: bool
    is_attempted: bool
    marks: float


class AttemptDetailedResults(BaseModel):
    attempt_id: int
    paper_id: int
    score: Optional[float] = None
    percentage: Optional[float] = None
    total_marks: float
    time_taken_seconds: Optional[int] = None
    started_at: Optional[str] = None
    submitted_at: Optional[str] = None
    question_results: List[QuestionResult]


class PaperInfo(BaseModel):
    id: int
    title: str
    exam_name: str
    year: int


class SubmitAttemptResponse(BaseModel):
    attempt_id: int
    submitted: bool
    score: Optional[float] = None
    total_marks: float
    percentage: Optional[float] = None
    time_taken_seconds: Optional[int] = None
    display_time: str
    submitted_at: Optional[str] = None
    paper_info: PaperInfo
    detailed_results: AttemptDetailedResults


class AttemptResultsResponse(BaseModel):
    attempt_id: int
    score: Optional[float] = None
    total_marks: float
    percentage: Optional[float] = None
    time_taken_seconds: Optional[int] = None
    display_time: str
    started_at: Optional[str] = None
    submitted_at: Optional[str] = None
    paper_info: PaperInfo
    detailed_results: AttemptDetailedResults


# User History Schemas
class AttemptSummary(BaseModel):
    attempt_id: int
    paper_id: int
    paper_title: str
    exam_name: str
    year: Optional[int] = None
    score: Optional[float] = None
    total_marks: float
    percentage: Optional[float] = None
    time_taken_seconds: Optional[int] = None
    display_time: str
    is_completed: bool
    started_at: Optional[str] = None
    submitted_at: Optional[str] = None


class UserPerformanceStats(BaseModel):
    total_attempts: int
    completed_attempts: int
    completion_rate: float
    average_score: float
    average_percentage: float
    best_score: float
    best_percentage: float
    average_time_seconds: int


class UserHistoryResponse(BaseModel):
    attempts: List[AttemptSummary]
    performance_stats: UserPerformanceStats
    pagination: Dict[str, int]


class PaperPerformanceStats(BaseModel):
    paper_id: int
    total_attempts: int
    completed_attempts: int
    completion_rate: float
    average_score: float
    average_percentage: float
    highest_score: float
    lowest_score: float
    score_std_deviation: float


class PaperStatsResponse(BaseModel):
    paper_id: int
    paper_title: str
    exam_name: str
    year: int
    statistics: PaperPerformanceStats


class AvailableFiltersResponse(BaseModel):
    years: List[int]
    exam_names: List[str]


# PDF Parsing Schemas (for admin/dev data ingestion)
class ParsePDFRequest(BaseModel):
    url: str = Field(..., description="URL of the PDF to parse")
    title: Optional[str] = Field(None, description="Optional exam title")
    year: Optional[int] = Field(None, description="Optional exam year")
    exam_name: Optional[str] = Field(None, description="Optional exam name")
    time_limit_minutes: Optional[int] = Field(180, description="Time limit in minutes")


class ParsePDFResponse(BaseModel):
    success: bool
    parsed_data: Dict[str, Any] = Field(..., description="Parsed exam paper data")
    questions_found: int
    total_marks: float
    message: str


class ImportPaperRequest(BaseModel):
    url: str = Field(..., description="URL of the PDF to parse and import")
    title: Optional[str] = Field(None, description="Optional exam title")
    year: Optional[int] = Field(None, description="Optional exam year")
    exam_name: Optional[str] = Field(None, description="Optional exam name")
    time_limit_minutes: Optional[int] = Field(180, description="Time limit in minutes")
    activate: bool = Field(True, description="Whether to activate the paper immediately")


class ImportPaperResponse(BaseModel):
    success: bool
    paper_id: int
    title: str
    questions_imported: int
    total_marks: float
    message: str