# Data Ingestion Pipeline

## Overview

The Data Ingestion Pipeline is the background system responsible for continuously collecting, processing, and indexing trusted news articles. It operates independently from the verification workflow, ensuring the database is always populated with fresh, searchable content.

## Purpose

Build and maintain a comprehensive database of trusted news by:
- Continuously monitoring RSS feeds from trusted sources
- Extracting full article content from web pages
- Processing text into searchable chunks
- Generating embeddings for semantic search
- Indexing content for fast retrieval
- Keeping data fresh and up-to-date

## Key Responsibilities

1. **News Collection**
   - Monitor RSS feeds from configured sources
   - Fetch new article URLs as they're published
   - Track processing status
   - Handle feed failures gracefully

2. **Content Extraction**
   - Scrape full article text from web pages
   - Extract metadata (title, author, date)
   - Handle various website structures
   - Deal with paywalls and anti-scraping measures

3. **Text Processing**
   - Clean and normalize article text
   - Split into semantic chunks (500-2000 chars)
   - Optimize for Vietnamese language
   - Preserve context and meaning

4. **Embedding Generation**
   - Generate vector embeddings for each chunk
   - Batch process for efficiency
   - Store in vector database
   - Handle API rate limits

5. **Indexing**
   - Create full-text search indexes
   - Build vector similarity indexes
   - Update database incrementally
   - Maintain index quality

6. **Scheduling & Orchestration**
   - Run crawls at regular intervals
   - Manage task queues and priorities
   - Handle retries and failures
   - Monitor pipeline health

## Architecture

### Technology Stack

**Task Queue**: Celery
- Distributed task processing
- Retry logic and error handling
- Task scheduling (Celery Beat)
- Monitoring and management

**Message Broker**: Redis
- Fast, reliable message delivery
- Task result storage
- Queue management
- Pub/sub for events

**Scheduler**: Celery Beat
- Periodic task execution
- Cron-like scheduling
- Flexible intervals
- Persistent schedule

**Content Extraction**: Trafilatura
- High-quality article extraction
- Multi-language support
- Handles complex HTML
- Fallback strategies

## Pipeline Stages

### Stage 1: Feed Crawling

**Purpose**: Discover new articles from RSS feeds

**Scheduler Configuration**:
- Default interval: Every 60 minutes
- Configurable per feed (15 min to 24 hours)
- Stagger crawls to avoid spikes

**Process**:
1. **Kickoff Task** (Scheduled by Celery Beat)
   - Query database for active RSS feeds
   - Check last fetch time
   - Enqueue crawl task for each due feed

2. **Fetch RSS Feed**
   - HTTP GET request to feed URL
   - Parse XML/Atom format
   - Extract article URLs and metadata
   - Handle various feed formats

3. **Deduplication**
   - Check if article URL already in database
   - Skip existing articles
   - Mark as "seen" in feed tracker

4. **Article Creation**
   - Create Article record with URL and basic metadata
   - Set status: pending_processing
   - Enqueue processing task

**Error Handling**:
- Network timeout → Retry up to 3 times
- Invalid feed format → Log error, skip, alert admin
- Too many failures → Disable feed automatically

**Feed Configuration** (sources.yaml):
```yaml
sources:
  - name: "BBC News"
    url: "https://bbc.com"
    feeds:
      - url: "http://feeds.bbci.co.uk/news/rss.xml"
        topic: "general"
        fetch_frequency_minutes: 60
        is_active: true
```

### Stage 2: Content Scraping

**Purpose**: Extract full article content from web pages

**Process**:
1. **Receive Article URL**
   - Task triggered by feed crawler
   - Load article metadata from database

2. **Fetch HTML Content**
   - HTTP GET request with appropriate headers
   - User-Agent: "VeriNews/1.0 (+https://verinews.com/bot)"
   - Timeout: 30 seconds
   - Follow redirects (max 5)

3. **Multi-Stage Extraction**
   - **Primary**: Trafilatura (best quality)
   - **Fallback 1**: Newspaper3k
   - **Fallback 2**: BeautifulSoup with heuristics
   - **Fallback 3**: Store error, mark as failed

4. **Extract Components**
   - Title (if not from RSS)
   - Author
   - Published date
   - Main article text
   - Remove ads, navigation, comments

5. **Content Validation**
   - Minimum word count: 100 words
   - Maximum word count: 50,000 words
   - Language detection (must match source language)
   - Content quality checks

6. **Store Article**
   - Update Article record with content
   - Set status: content_extracted
   - Trigger chunking task

**Handling Edge Cases**:

**Paywalls**:
- Detect common paywall patterns
- Mark article as "paywall" (don't retry)
- Future: Integrate with archive services

**JavaScript-Heavy Sites**:
- Use Playwright/Selenium for rendering (optional)
- More resource-intensive (slower, more expensive)
- Only for high-value sources

**Rate Limiting**:
- Respect robots.txt
- Implement per-domain rate limits
- Use polite crawling delays (1-2 seconds)

**Anti-Scraping**:
- Rotate user agents
- Use proxies if blocked (optional)
- Mimic human browsing patterns

### Stage 3: Text Chunking

**Purpose**: Split articles into semantic segments for retrieval

**Chunking Strategy**: Intelligent paragraph-level splitting

**Process**:
1. **Text Preprocessing**
   - Normalize whitespace
   - Fix encoding issues
   - Remove extra newlines

2. **Paragraph Detection**
   - Split on double newlines (`\n\n`)
   - Also handle single newlines (common in scraped text)
   - Preserve paragraph boundaries

3. **Smart Chunking**
   - **Target size**: 500-2000 characters per chunk
   - **Merge small paragraphs**: < 500 chars
   - **Split large paragraphs**: > 2000 chars
     - Split on sentence boundaries
     - Use sentence tokenizer (NLTK, spaCy)
     - Ensure logical breaks

4. **Vietnamese Optimization**
   - Preserve compound words
   - Handle Vietnamese sentence structure
   - Keep context (e.g., don't split mid-sentence)

5. **Create ArticleChunk Records**
   - Store each chunk with:
     - Article ID (foreign key)
     - Chunk index (order within article)
     - Text content
     - Word count
   - Status: pending_embedding

**Chunking Example**:
```
Input Article (3000 chars):
Paragraph 1 (800 chars) → Chunk 1
Paragraph 2 (400 chars) + Paragraph 3 (350 chars) → Chunk 2 (merged)
Paragraph 4 (2500 chars) → Split into Chunk 3 (1200 chars) + Chunk 4 (1300 chars)
Paragraph 5 (600 chars) → Chunk 5
```

**Quality Metrics**:
- Average chunk size: 1000-1500 chars
- Min chunk size: 500 chars (exceptions: last chunk)
- Max chunk size: 2000 chars
- Chunks per article: ~5-20 (varies by article length)

### Stage 4: Embedding Generation

**Purpose**: Create vector representations for semantic search

**Process**:
1. **Batch Collection**
   - Query database for chunks with status: pending_embedding
   - Collect batches of 100 chunks
   - Prioritize recent articles

2. **Batch Embedding Request**
   - Call OpenAI API with batch of texts
   - Model: text-embedding-3-small (1536 dimensions)
   - Max batch size: 100 items (API limit: technically higher, but 100 is optimal)
   - Request timeout: 60 seconds

3. **Process Response**
   - Receive array of 1536-dim vectors
   - Normalize vectors to unit length (for cosine similarity)
   - Validate dimensions

4. **Store Embeddings**
   - Update ArticleChunk records
   - Store vector in `embedding` column (pgvector)
   - Set status: indexed

5. **Trigger Indexing**
   - Once batch complete, rebuild vector index (if needed)
   - Update full-text search vectors

**Optimization**:
- Batch processing (100 chunks at once)
- Parallel workers (4-8 concurrent tasks)
- Rate limiting (3000 requests/min limit)
- Cost tracking (monitor token usage)

**Error Handling**:
- API timeout → Retry with smaller batch
- Rate limit (429) → Queue and wait
- Token limit exceeded → Split chunk, generate separately
- API error → Retry up to 3 times, then alert

**Cost Management**:
- Target: < $0.001 per article
- Average article: ~10 chunks × 500 chars = 5000 chars = ~1250 tokens
- Cost: 1250 tokens × $0.02 / 1M tokens = $0.000025
- Budget: $500/month → ~20M tokens → ~16K articles

### Stage 5: Indexing

**Purpose**: Build database indexes for fast search

**Process**:
1. **Full-Text Search Vector Generation**
   - For each chunk:
     - Generate tsvector: `to_tsvector('vietnamese', chunk.text)`
     - Store in `search_vector` column
   - PostgreSQL handles automatically with trigger

2. **Vector Index Building**
   - IVFFlat index on `embedding` column
   - Rebuild incrementally as new chunks added
   - Automatic maintenance by PostgreSQL

3. **Statistics Update**
   - Run ANALYZE on ArticleChunk table
   - Update query planner statistics
   - Optimize index usage

**Index Maintenance**:
- Incremental updates (no full rebuild needed)
- Monitor index size and query performance
- Reindex if performance degrades (monthly)

## Task Queue Architecture

### Celery Configuration

**Workers**:
- Number of workers: 4 (adjustable)
- Concurrency per worker: 4 (threads)
- Total concurrent tasks: 16

**Queues**:
- `crawler`: Feed crawling and scraping (high priority)
- `embedding`: Embedding generation (medium priority)
- `maintenance`: Indexing and cleanup (low priority)

**Task Routing**:
```python
CELERY_TASK_ROUTES = {
    'kickoff_all_crawls': {'queue': 'crawler'},
    'crawl_feed': {'queue': 'crawler'},
    'process_article': {'queue': 'crawler'},
    'generate_embeddings_batch': {'queue': 'embedding'},
    'rebuild_indexes': {'queue': 'maintenance'},
}
```

**Task Priorities**:
- Breaking news sources: High priority
- Regular feeds: Normal priority
- Reprocessing old articles: Low priority

### Celery Beat Schedule

**Periodic Tasks**:
```python
CELERY_BEAT_SCHEDULE = {
    'crawl-all-feeds': {
        'task': 'kickoff_all_crawls',
        'schedule': crontab(minute='*/60'),  # Every hour
    },
    'cleanup-failed-tasks': {
        'task': 'cleanup_failed_articles',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'rebuild-indexes': {
        'task': 'rebuild_indexes',
        'schedule': crontab(day_of_week=0, hour=3),  # Weekly Sunday 3 AM
    },
}
```

### Task Retry Logic

**Retry Configuration**:
```python
@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # 60 seconds
    autoretry_for=(NetworkError, TimeoutError),
)
def process_article(self, article_id):
    try:
        # Processing logic
        pass
    except RetryableError as exc:
        # Exponential backoff
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
```

**Retry Strategies**:
- Network errors: Retry with exponential backoff
- Rate limits: Retry after specified wait time
- Temporary failures: Retry up to 3 times
- Permanent failures: Mark as failed, don't retry

## Monitoring & Management

### Health Checks

**Celery Worker Health**:
- Check worker status: `celery -A app.celery_app inspect active`
- Monitor queue lengths
- Track task processing rate
- Alert if workers down

**Pipeline Metrics**:
- Articles processed per hour
- Success/failure rates per stage
- Average processing time per stage
- Queue backlog size

### Performance Metrics

**Throughput**:
- Target: 1000 articles/day (initial)
- Scale to: 10,000 articles/day (production)

**Latency** (per article):
- Feed crawling: 5-10 seconds
- Content scraping: 10-30 seconds
- Chunking: 1-2 seconds
- Embedding generation: 5-10 seconds
- Total: ~30-60 seconds per article

**Resource Usage**:
- CPU: ~50% average on 4-core machine
- Memory: ~2GB for workers
- Network: ~1-5 Mbps
- Database: ~100 writes/sec during peak

### Failure Handling

**Failed Article Tracking**:
- Store error messages in database
- Categorize failure types
- Retry logic per failure type
- Alert admin for persistent failures

**Common Failure Modes**:
- Feed unavailable: Retry later, disable if persistent
- Scraping blocked: Rotate IPs, adjust rate limits
- Embedding API down: Queue and retry
- Database connection lost: Reconnect and resume

**Recovery Strategies**:
- Automatic retry with backoff
- Dead letter queue for unrecoverable errors
- Manual reprocessing interface
- Bulk retry for systemic issues

## Maintenance & Operations

### CLI Commands

**Start/Stop Pipeline**:
```bash
./scripts/verinews crawler start
./scripts/verinews crawler stop
./scripts/verinews crawler status
```

**Feed Management**:
```bash
./scripts/verinews feeds sync          # Sync from sources.yaml
./scripts/verinews feeds list          # List all feeds
./scripts/verinews feeds add URL       # Add new feed
./scripts/verinews feeds remove URL    # Remove feed
```

**Manual Operations**:
```bash
# Trigger immediate crawl for all feeds
./scripts/verinews crawler trigger

# Reprocess specific article
./scripts/verinews article reprocess <article_id>

# Rebuild all indexes
./scripts/verinews index rebuild
```

### Monitoring Dashboard

**Key Metrics to Display**:
- Articles indexed (total, today, last hour)
- Active workers and queue status
- Recent errors and failures
- Processing time trends
- Cost tracking (API usage)

**Alerts**:
- Worker down: Immediate alert
- High failure rate (> 20%): Alert within 5 min
- Queue backlog (> 1000): Alert within 15 min
- API budget exceeded: Alert immediately

## Scaling Strategies

### Vertical Scaling (Initial)
- Increase worker count (4 → 8 → 16)
- More CPU cores for parallel processing
- More memory for larger batches

### Horizontal Scaling (Future)
- Multiple worker machines
- Distributed Redis cluster
- Load balancer for task distribution

### Optimization Techniques
- Prioritize high-traffic sources
- Cache frequent scraping targets
- Batch embedding generation more aggressively
- Parallel processing of independent articles

## Future Enhancements

1. **Intelligent Crawling**
   - ML-based prediction of article importance
   - Dynamic crawl frequency based on source velocity
   - Prioritize trending topics

2. **Advanced Content Extraction**
   - JavaScript rendering for complex sites
   - Image extraction and analysis
   - Video transcription integration

3. **Real-Time Processing**
   - WebSocket connections for instant updates
   - Stream processing (Kafka, Flink)
   - Sub-minute latency from publish to indexed

4. **Multi-Region Deployment**
   - Geographic distribution of crawlers
   - Regional content preferences
   - Reduced latency for international sources

5. **Quality Assurance**
   - Automated content quality scoring
   - Duplicate detection and merging
   - Source credibility tracking
   - User feedback integration
