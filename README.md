# 🎓 Parkho AI Backend - Educational Content Processing System

**Production-Ready Multi-Agent Content Processing System** ✅

A high-performance, refactored multi-agent system that transforms various content types (YouTube videos, PDFs, documents, web pages) into educational materials including summaries and quiz questions. Built with FastAPI, SQLAlchemy, and modern async Python architecture following clean code principles.

## 🏆 **Major Refactoring Completed (December 2024)**

- ✅ **Code Quality**: All REVISIT/TODO comments eliminated from production code
- ✅ **Architecture**: Clean dependency injection throughout all components
- ✅ **Modularity**: YouTube parser refactored from 822-line monolith to 4 focused classes
- ✅ **Test Coverage**: 28/28 tests passing (100% success rate)
- ✅ **Exception Handling**: Root-level domain-specific exception hierarchy
- ✅ **API Endpoints**: Separated concerns, applied DRY principle with utilities
- ✅ **YAGNI Compliance**: Clean, minimal code following Single Responsibility Principle

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- OpenAI API Key (for content processing)
- Google API Key (for multi-agent workflows)
- Anthropic API Key (optional, for fallback LLM)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/nakuljn/ai-video-tutor.git
cd ai-video-tutor
```

2. **Set up virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set environment variables**
```bash
export OPENAI_API_KEY="your-openai-api-key"
export GOOGLE_API_KEY="your-google-api-key"
export ANTHROPIC_API_KEY="your-claude-api-key"  # Optional
export FIREBASE_SERVICE_ACCOUNT_PATH="firebase-service-account.json"
export FIREBASE_PROJECT_ID="your-firebase-project-id"
```

5. **Run database migrations**
```bash
alembic upgrade head
```

6. **Start the server**
```bash
python -m uvicorn src.main:app --host 127.0.0.1 --port 8080
```

7. **Access the API**
- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/api/v1/health

### Docker (Backend Only)
1. Copy the example env file and fill in secrets:
   ```bash
   cp env.docker.example .env.docker
   ```
2. Update `DATABASE_URL`, API keys, and Firebase paths to point at the services you already run (e.g., Postgres + MinIO).
3. Build and start the container so it appears in `docker ps`:
   ```bash
   docker compose -f docker-compose.backend.yml up -d --build
   ```
4. Verify:
   - `docker ps` should list `parkho-ai-backend`
   - API Docs: http://localhost:8080/docs

## 🏗️ **Refactored Architecture - Clean & Modular**

### **🎯 Design Philosophy (Post-Refactoring)**
- **Clean Code**: Single Responsibility Principle, YAGNI compliance, dependency injection
- **Performance First**: JSON-based flexible data model for efficient storage
- **Real-time Updates**: WebSocket-based progress tracking with centralized job management
- **Modular Components**: Each class has focused responsibilities (4 YouTube classes vs. 1 monolith)
- **Scalable**: Background job processing with proper exception handling

### **🏭 Refactored System Architecture**
```
┌─────────────────────────────────────────────────────────────────┐
│                       FastAPI Backend                          │
├──────────────────┬─────────────────┬──────────────────────────────┤
│   API Endpoints  │  WebSocket Hub  │     Exception Handling       │
│                  │                 │                              │
│ • Content API ♻️  │ • Real-time     │ • Root-level exceptions 🆕   │
│ • Quiz API 🆕     │   progress      │ • Domain-specific errors     │
│ • Auth API       │ • Job updates   │ • ValidationError, etc.      │
└──────────────────┴─────────────────┴──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Workflow Orchestration                       │
├──────────────────────┬──────────────────────┬───────────────────┤
│  ContentWorkflow ♻️   │  JobStatusManager 🆕  │ RAGIntegration 🆕  │
│                      │                      │                   │
│ • Clean DI (25 lines)│ • Centralized status │ • Context         │
│ • Session injection  │ • WebSocket notify   │   retrieval       │
│ • No SessionLocal()  │ • Progress tracking  │ • Collection mgmt │
└──────────────────────┴──────────────────────┴───────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Modular Content Parsing                       │
├──────────────────┬──────────────────┬─────────────────┬─────────┤
│  YouTube Parser  │   PDF Parser ♻️   │  Web Parser ♻️   │ Utils 🆕│
│     🆕 (4 classes) │                  │                 │         │
│                  │ • File utilities │ • WebContentFet │ • String│
│ • VideoExtractor │ • String utils   │ • WebContentPro │ • URL   │
│ • AudioProcessor │ • Validation     │ • Error handling│ • File  │
│ • TranscriptProc │ • Exception use  │ • Clean methods │ • Valid │
│ • YouTubeParser  │                  │                 │ • Resp  │
│   (Orchestrator) │                  │                 │  Map 🆕 │
└──────────────────┴──────────────────┴─────────────────┴─────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              Database & Storage (Repository Pattern)           │
├──────────────────────────────────────────┬───────────────────────┤
│            SQLite/PostgreSQL             │   Repository Layer   │
│                                          │                       │
│ • Flexible JSON-based schema            │ • Clean dependency    │
│ • Real-time progress tracking           │   injection           │
│ • TTL file cleanup                      │ • Single pattern      │
│ • Multi-status responses                │ • No direct DB calls │
└──────────────────────────────────────────┴───────────────────────┘
```

### Technology Stack
- **Backend**: FastAPI + Uvicorn (async Python web framework)
- **Database**: SQLite (dev) / PostgreSQL (prod) with flexible JSON-based design
- **AI Processing**: Multi-agent pipeline using Google ADK
- **LLMs**: OpenAI GPT-3.5-turbo (primary), Anthropic Claude (fallback)
- **Content Processing**: YouTube (yt-dlp + Whisper), PDFs, DOCX, web URLs
- **File Storage**: Temporary file system with automatic cleanup
- **Real-time**: WebSockets for progress updates
- **Auth**: Firebase Admin SDK

## 📊 Database Schema

**Flexible JSON-Based Design**:

```sql
-- Main content processing jobs
CREATE TABLE content_jobs (
    id INTEGER PRIMARY KEY,
    user_id VARCHAR,
    status VARCHAR NOT NULL DEFAULT 'pending',  -- pending|processing|completed|failed|cancelled
    progress FLOAT NOT NULL DEFAULT 0.0,        -- 0-100%
    created_at DATETIME NOT NULL,
    completed_at DATETIME,
    input_config TEXT,                          -- JSON configuration for input
    output_config TEXT,                         -- JSON configuration for output
    content_hash VARCHAR UNIQUE,                -- For duplicate detection
    error_message TEXT
);

-- Temporary file storage
CREATE TABLE uploaded_files (
    id INTEGER PRIMARY KEY,
    filename VARCHAR NOT NULL,
    original_filename VARCHAR NOT NULL,
    file_path VARCHAR NOT NULL,
    content_type VARCHAR NOT NULL,
    file_size INTEGER NOT NULL,
    uploaded_at DATETIME NOT NULL,
    expires_at DATETIME NOT NULL              -- TTL for automatic cleanup
);

-- User management
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    firebase_uid VARCHAR UNIQUE NOT NULL,
    email VARCHAR,
    display_name VARCHAR,
    created_at DATETIME NOT NULL,
    last_login DATETIME
);

-- Quiz questions storage
CREATE TABLE quiz_questions (
    id INTEGER PRIMARY KEY,
    content_job_id INTEGER NOT NULL,
    question_text TEXT NOT NULL,
    question_type VARCHAR NOT NULL,
    options TEXT,                            -- JSON array for multiple choice
    correct_answer TEXT NOT NULL,
    difficulty_level VARCHAR,
    created_at DATETIME NOT NULL,
    FOREIGN KEY (content_job_id) REFERENCES content_jobs (id)
);
```

## 🔌 API Endpoints

### Content Processing
```bash
POST /api/v1/content/upload          # Upload file for processing
POST /api/v1/content/process         # Submit content for processing
GET /api/v1/content/{job_id}/status  # Check processing status
GET /api/v1/content/{job_id}/results # Get completed results
GET /api/v1/content/{job_id}/summary # Get job summary
GET /api/v1/content/{job_id}/content # Get extracted content
GET /api/v1/content/jobs             # List all jobs
DELETE /api/v1/content/{job_id}      # Delete job
GET /api/v1/content/supported-types  # Get supported content types
```

### Quiz Management (🆕 Separated from content endpoints)
```bash
GET /api/v1/content/{job_id}/quiz    # Get quiz questions
POST /api/v1/content/{job_id}/quiz   # Submit quiz answers
```

### Authentication
```bash
POST /api/v1/auth/verify-token       # Verify Firebase token
POST /api/v1/auth/create-user        # Create user profile
GET /api/v1/auth/me                  # Get current user
```

### WebSocket
```bash
/ws/content/{job_id}                 # Real-time progress updates
```

### Example Usage

**Process a YouTube video:**
```bash
curl -X POST "http://localhost:8000/api/v1/content/process" \
  -H "Content-Type: application/json" \
  -d '{
    "content_type": "url",
    "content_data": {
      "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    },
    "processing_options": {
      "generate_summary": true,
      "generate_questions": true,
      "question_count": 10,
      "difficulty_level": "intermediate"
    }
  }'
```

**Upload and process a PDF:**
```bash
# First upload the file
curl -X POST "http://localhost:8000/api/v1/content/upload" \
  -F "file=@document.pdf"

# Then process it using the returned file_id
curl -X POST "http://localhost:8000/api/v1/content/process" \
  -H "Content-Type: application/json" \
  -d '{
    "content_type": "file",
    "content_data": {
      "file_id": "uploaded_file_id"
    },
    "processing_options": {
      "generate_summary": true,
      "generate_questions": true
    }
  }'
```

## 🤖 AI Processing Pipeline

### Multi-Agent Workflow
1. **Content Workflow Orchestrator**
   - Determines processing strategy based on content type
   - Coordinates agent execution
   - Manages progress updates

2. **Content Analyzer Agent**
   - Extracts and analyzes content from various sources
   - Generates comprehensive summaries
   - Updates progress: 0% → 70%

3. **Question Generator Agent**
   - Creates multiple choice, short answer, and essay questions
   - Applies difficulty level filtering
   - Updates progress: 70% → 100%

### Supported Content Types
- **YouTube Videos**: Audio extraction + Whisper transcription
- **PDF Documents**: Text extraction with formatting preservation
- **DOCX Files**: Microsoft Word document processing
- **Web URLs**: HTML content extraction and cleaning
- **Direct Text**: Plain text content processing

### Real-time Progress Tracking
- WebSocket connections provide live updates
- Progress tracking across multi-agent pipeline
- Error notifications and recovery mechanisms
- Automatic duplicate detection and prevention

## 📈 Performance Features

### Optimizations
- **JSON-based flexible data model** for efficient storage
- **Background job processing** prevents API blocking
- **Automatic temporary file cleanup** with TTL
- **Duplicate detection** prevents redundant processing
- **Configurable concurrent job limits**
- **Multi-status HTTP responses** for complex operations

### Performance Targets
- Process 10-minute videos in under 5 minutes
- Support 5 concurrent content processing jobs
- API response times under 500ms
- Support various file sizes with configurable limits

## 🛡️ Security & Best Practices

- **Firebase Authentication**: Secure user management
- **Input Validation**: Pydantic models for request/response validation
- **File Type Validation**: Strict content type checking
- **CORS Configuration**: Proper origin management
- **Rate Limiting**: API abuse prevention
- **Temporary File Storage**: Automatic cleanup with TTL
- **Structured Logging**: No sensitive data exposure

## 🧪 Development

### Running the Development Server
```bash
source venv/bin/activate
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload
```

### Database Migrations
```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

### **✅ Code Style (Post-Refactoring)**
- **SOLID Principles**: Single Responsibility, Open/Closed, Dependency Inversion
- **DRY Principle**: Response mapping utilities eliminate code duplication
- **YAGNI Compliance**: Only implement what's needed, clean minimal code
- **Clean Architecture**: Dependency injection, no direct database calls
- **Type Safety**: Pydantic models and Python type hints throughout
- **Exception Handling**: Root-level domain-specific exceptions
- **Modular Design**: 4 YouTube classes vs. 822-line monolith
- **Test Coverage**: 28/28 tests passing (100% success rate)

## 🚀 Deployment

### Environment Variables
```bash
# API Configuration
API_HOST=localhost
API_PORT=8000

# Database
DATABASE_URL=sqlite:///./ai_video_tutor.db  # or postgresql://...

# LLM APIs
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-claude-key
GOOGLE_API_KEY=your-google-key

# Firebase
FIREBASE_SERVICE_ACCOUNT_PATH=firebase-service-account.json
FIREBASE_PROJECT_ID=your-firebase-project-id

# Processing Limits
MAX_VIDEO_LENGTH_MINUTES=60
MAX_CONCURRENT_JOBS=5
JOB_TIMEOUT_MINUTES=10

# CORS
CORS_ALLOWED_ORIGINS=https://parkho-ai-frontend-ku7bn6e62q-uc.a.run.app,http://localhost:5173,http://localhost:3000
```

### Production Setup
1. Use PostgreSQL instead of SQLite
2. Set up reverse proxy (nginx/Apache)
3. Configure SSL certificates
4. Set up monitoring and logging
5. Configure backup strategy
6. Implement proper secret management

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: See [CLAUDE.md](CLAUDE.md) for detailed development guidelines
- **Issues**: Report bugs and feature requests via GitHub Issues
- **API Docs**: Access interactive documentation at `/docs` when running locally

---

**Built with ❤️ for efficient learning through AI-powered content analysis**