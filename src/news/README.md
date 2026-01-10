# News Module

A self-contained module for legal news processing, designed for optimal performance and scalability.

## Architecture Overview

### **Background-Only Processing**
- ✅ **Frontend APIs are read-only** - No processing triggered by users
- ✅ **Cron jobs handle all heavy lifting** - Fetching, scraping, RAG indexing
- ✅ **Instant response times** - Pre-processed data from database
- ✅ **Controlled resource usage** - Processing runs on your schedule

### **Module Structure**
```
src/news/
├── models/
│   └── news_article.py           # Enhanced with is_rag_indexed field
├── services/
│   ├── news_service.py           # Read-only service for APIs
│   ├── content_scraper.py        # Web scraping and image download
│   ├── news_cron_service.py      # Background processing pipeline
│   └── sources/                  # Multi-source news fetching
│       ├── manager.py
│       ├── base.py
│       └── indian_kanoon_rss.py  # Proven working RSS source
├── schemas/
│   ├── requests.py               # API request models
│   └── responses.py              # API response models
└── repositories/                 # Future: Database access layer
```

## Database Schema

### **Minimal Schema Changes**
Only **1 new field** added to existing `news_articles` table:

```sql
-- New field
is_rag_indexed BOOLEAN DEFAULT FALSE

-- Logic:
-- full_content IS NOT NULL = article has extracted content
-- is_rag_indexed = TRUE = AI features available for users
```

### **Key Properties**
```python
# NewsArticle model properties
article.has_content     # True if full_content exists
article.ai_enabled      # True if is_rag_indexed = True (user-facing)
```

## Background Processing Pipeline

### **Main Cron Job Flow**
```python
# Run: python news_cron.py --limit 50

1. 📰 Fetch articles from RSS sources
   └── Store basic article info (title, url, description, images)

2. 📝 Extract full content for articles without content
   └── Scrape article text from URLs
   └── Download and store images to GCS
   └── Update full_content field

3. 🤖 Index articles in RAG system
   └── Process articles with content but not indexed
   └── Mark is_rag_indexed = TRUE when complete
```

### **Cron Job Commands**
```bash
# Run full pipeline (fetch 50 articles)
python news_cron.py

# Run with custom limit
python news_cron.py --limit 100

# Health check only
python news_cron.py --health-check

# Verbose logging
python news_cron.py --verbose
```

### **Cron Schedule Examples**
```bash
# Every 2 hours
0 */2 * * * cd /path/to/project && python news_cron.py --limit 30

# Twice daily (9 AM and 6 PM)
0 9,18 * * * cd /path/to/project && python news_cron.py --limit 50

# Custom schedule - you control timing
```

## Frontend APIs (Read-Only)

### **Available Endpoints**

#### **Get News List**
```http
GET /api/v1/news/?source=Indian%20Kanoon&limit=20&offset=0
```
**Features:**
- ✅ Only returns articles with extracted content
- ✅ Includes `ai_enabled` field for frontend features
- ✅ Fast pagination
- ✅ Source and date filtering

#### **Get News Detail**
```http
GET /api/v1/news/{id}
```
**Features:**
- ✅ Complete article with full extracted content
- ✅ Related articles
- ✅ Auto-triggers RAG indexing if needed
- ✅ Rich image data

#### **Get Categories**
```http
GET /api/v1/news/categories
```
**Features:**
- ✅ Categories with article counts
- ✅ Only counts articles with content

### **Response Format**
```json
{
  "id": 123,
  "title": "Supreme Court Ruling on...",
  "url": "https://indiankanoon.org/doc/123456/",
  "source": "Indian Kanoon - Supreme Court",
  "category": "constitutional",
  "published_at": "2024-01-09T10:30:00Z",
  "full_content": "Complete extracted article text...",
  "summary": "Brief summary...",
  "keywords": ["supreme court", "constitutional", "ruling"],
  "featured_image_url": "https://storage.googleapis.com/...",
  "ai_enabled": true,
  "related_articles": [...]
}
```

## Content Extraction

### **Intelligent Web Scraping**
```python
# Extraction methods (in order of preference):
1. newspaper3k - Best for article extraction
2. BeautifulSoup - Fallback with smart selectors
3. Basic text extraction - Final fallback

# Image processing:
1. Extract main article image from webpage
2. Download and store in GCS
3. Update featured_image_url with GCS URL
```

### **Quality Assurance**
- ✅ Content validation (minimum length, relevance)
- ✅ Error handling and fallback strategies
- ✅ Duplicate detection via URL uniqueness
- ✅ Retry mechanisms for failed extractions

## News Sources

### **Multi-Source Architecture**
```python
# Current sources:
- Indian Kanoon RSS (proven working)
  ├── Supreme Court feed
  ├── Delhi HC feed
  ├── Bombay HC feed
  └── All Judgments feed

# Adding new sources:
# Just drop a new adapter file in sources/ directory
# Auto-discovery will include it automatically
```

### **Source Health Monitoring**
```bash
# Check source health
python news_cron.py --health-check

# Output:
{
  "overall_health": "healthy",
  "total_articles": 1250,
  "articles_with_content": 1180,
  "content_extraction_rate": 94.4,
  "rag_indexing_rate": 88.2,
  "source_health": {
    "indian_kanoon_rss": true
  }
}
```

## RAG Integration

### **Seamless AI Features**
- ✅ Articles indexed automatically in background
- ✅ `ai_enabled` field indicates RAG availability
- ✅ Existing RAG endpoints work unchanged
- ✅ Manual indexing endpoint available if needed

### **RAG Status Tracking**
```sql
-- Find articles ready for RAG indexing
SELECT COUNT(*) FROM news_articles
WHERE full_content IS NOT NULL
AND is_rag_indexed = FALSE;

-- Check RAG indexing rate
SELECT
  COUNT(*) as total,
  COUNT(CASE WHEN is_rag_indexed THEN 1 END) as indexed
FROM news_articles
WHERE full_content IS NOT NULL;
```

## Performance Benefits

### **Frontend Performance**
- ⚡ **Zero wait times** - All content pre-processed
- ⚡ **Consistent response times** - Pure database reads
- ⚡ **No timeouts** - No external API dependencies
- ⚡ **Scalable** - Handles high traffic effortlessly

### **Server Resource Optimization**
- 🎯 **Controlled processing** - Runs on your schedule
- 🎯 **No user-triggered load** - Background processing only
- 🎯 **Efficient batching** - Process multiple articles together
- 🎯 **Error isolation** - Failed processing doesn't affect users

## Setup Instructions

### **1. Install Dependencies**
```bash
pip install feedparser newspaper3k beautifulsoup4 requests
```

### **2. Run Database Migration**
```bash
python -m alembic upgrade head
```

### **3. Test the Pipeline**
```bash
# Test news sources
python -c "
from src.news.services.sources.manager import NewsSourceManager
manager = NewsSourceManager()
print(manager.health_check())
"

# Test full pipeline
python news_cron.py --limit 5 --verbose
```

### **4. Setup Cron Job**
```bash
# Edit crontab
crontab -e

# Add line (adjust path and schedule):
0 */3 * * * cd /path/to/project && python news_cron.py --limit 30 >> logs/cron.log 2>&1
```

### **5. Monitor Health**
```bash
# Check pipeline health
python news_cron.py --health-check

# Check logs
tail -f logs/news_cron.log
```

## Migration from Old System

The new news module is **fully backward compatible**:

✅ **Existing APIs unchanged** - Same endpoints, same responses
✅ **Database schema preserved** - Only 1 new field added
✅ **RAG integration intact** - All existing RAG features work
✅ **Frontend unchanged** - No frontend modifications needed

## Future Enhancements

### **Easy to Add:**
- New news sources (drop adapter files)
- Content processing improvements
- Additional image processing
- Custom categorization rules
- Source-specific extraction logic

### **Module Extraction Ready**
This module is designed to be easily extracted to a separate repository with minimal changes to imports.

---

**Result: Lightning-fast frontend + controlled background processing = optimal user experience with minimal server load.**