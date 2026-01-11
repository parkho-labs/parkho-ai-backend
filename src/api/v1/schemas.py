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
    body: Optional[Any] = None 


class RAGFileItem(BaseModel):
    file_id: str
    type: str = Field(default="file")
    name: str


class RAGFileDetail(BaseModel):
    file_id: str
    filename: str
    file_type: Optional[str] = None
    file_size: int
    upload_date: str
    indexing_status: Optional[str] = "pending"


class CollectionStatusResponse(BaseModel):
    collection_id: str
    name: str
    files: List[RAGFileDetail]
    status: str = "success"


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
    processing_time_ms: Optional[int] = 0
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




LegalDifficultyLevel = str


class LawChatRequest(BaseModel):
    question: str = Field(..., max_length=2000, description="Legal question")
    enable_rag: bool = Field(default=False, description="If True, use RAG with all legal documents. If False, use direct LLM with legal system prompt")
    news_context_id: Optional[int] = Field(default=None, description="Limit search to specific news article context")


class LawSource(BaseModel):
    text: str = Field(..., description="First 200 chars of source")
    article: str = Field(..., description="Article reference")


class LawChatResponse(BaseModel):
    answer: str
    sources: List[LawSource]
    total_chunks: int
    context_used: Optional[str] = Field(default=None, description="Context type used: 'news', 'general', or 'mixed'")
    # Intent classification metadata (from IntentClassifier)
    detected_expertise: Optional[str] = Field(default=None, description="Detected user expertise: 'layman', 'student', or 'professional'")
    detected_question_type: Optional[str] = Field(default=None, description="Detected question type: 'conceptual', 'procedural', 'case_based', 'comparison', or 'practical'")


class LegalQuestionSpec(BaseModel):
    type: str = Field(..., description="Question type (e.g., 'mcq', 'assertion_reasoning', 'match_following', 'comprehension')")
    difficulty: LegalDifficultyLevel
    count: int = Field(..., ge=1, le=10, description="Number of questions (1-10)")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Optional filters like collection_ids")


class LegalQuestionContext(BaseModel):
    subject: Optional[str] = Field(default=None, description="Subject context")


class LegalQuestionRequest(BaseModel):
    questions: List[LegalQuestionSpec]
    context: Optional[LegalQuestionContext] = None


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


class CustomQuestionSpec(BaseModel):
    type: str = Field(..., description="Question type (e.g., 'mcq', 'assertion_reasoning', 'match_following', 'comprehension')")
    count: int = Field(..., ge=1, le=10, description="Number of questions (1-10)")

class CustomQuizRequest(BaseModel):
    questions: List[CustomQuestionSpec]
    difficulty: LegalDifficultyLevel = Field(default="moderate", description="Overall difficulty level")
    subject: Optional[str] = Field(default="Constitutional Law", description="Subject context")
    scope: List[str] = Field(default=["constitution"], description="Scope: constitution, bns, or both")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Optional filters like collection_ids")
    include_answers: bool = Field(default=False, description="If True, include answers in response. If False, only return questions for quiz-taking")

class MockQuizRequest(BaseModel):
    total_questions: int = Field(..., ge=3, le=50, description="Total questions for mock quiz (3-50, must be divisible by 3)")
    subject: Optional[str] = Field(default="Constitutional Law", description="Subject context")
    scope: List[str] = Field(default=["constitution"], description="Scope: constitution, bns, or both")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Optional filters like collection_ids")
    include_answers: bool = Field(default=False, description="If True, include answers in response. If False, only return questions for quiz-taking")

    @field_validator('total_questions')
    @classmethod
    def validate_total_questions(cls, v):
        if v % 3 != 0:
            raise ValueError('total_questions must be divisible by 3 for equal distribution')
        return v

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

QuestionGenerationResponse = QuizGenerationResponse


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
    question_id: str
    question_text: str
    correct_answer: str
    user_answer: Optional[str] = None
    is_correct: bool
    is_attempted: bool
    explanation: Optional[str] = None
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


# News Schemas
class NewsArticleSummary(BaseModel):
    id: int
    title: str
    url: str
    source: str
    category: str
    published_at: Optional[datetime] = None
    summary: Optional[str] = None
    featured_image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    image_caption: Optional[str] = None
    image_alt_text: Optional[str] = None


class NewsListResponse(BaseModel):
    articles: List[NewsArticleSummary]
    total: int
    has_more: bool


class NewsDetailResponse(BaseModel):
    id: int
    title: str
    url: str
    source: str
    category: str
    published_at: Optional[datetime] = None
    full_content: str
    summary: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    related_articles: List[NewsArticleSummary] = Field(default_factory=list)
    rag_document_id: Optional[str] = None
    featured_image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    image_caption: Optional[str] = None
    image_alt_text: Optional[str] = None
