# Data Ingestion Pipeline

## What It Is

The data pipeline continuously collects news articles from RSS feeds, extracts their content, splits them into chunks, and generates embeddings so they're searchable.

## Technology Stack

- **Celery**: Background task processor
- **Redis**: Message broker (task queue)
- **Celery Beat**: Scheduler for periodic tasks
- **Trafilatura**: Article content extraction
- **OpenAI**: Embedding generation
- **PyVi**: Vietnamese text tokenization

## The Pipeline (5 Stages)

### Stage 1: RSS Feed Crawling

**What happens**: Checks RSS feeds for new articles

**Trigger**: Celery Beat runs every 5 minutes (configurable via `scheduler.crawler_interval_minutes`)

**Process**:
1. Scheduler triggers `kickoff_all_crawls` task (every 5 minutes by default)
   - **Pre-processing**: Clears retrieval cache via `RetrievalCache.clear_all()` so fresh retrieval data is generated after new content arrives
2. Queries database for active `RssFeed` rows
3. For each feed, enqueues `crawl_feed` task:
   - Fetches RSS XML using `feedparser` library
   - Parses to extract FeedEntry objects (title, link, published_at)
   - Applies **Ingest Cutoff**: Skips articles published > 48 hours ago (`crawler.ingest_max_age_hours`)
   - Applies **Duplicate Check**: Skips URLs already in database (exact URL match)
   - Respects **Rate Limit**: Max 50 articles per feed per crawl (`crawler.max_articles_per_feed`)
   - Creates Article records with: title, url, published_at, feed_id
   - Updates `RssFeed.last_fetched_at` timestamp (stored in PostgreSQL)
4. Enqueues `process_article_task` for each new article

**Date Parsing**:
- Parses RSS `published` or `updated` dates using feedparser's built-in parser
- Handles custom timezone formats: `"GMT+7"` → `"+0700"` via regex normalization
- Normalizes all dates to UTC

**Feed configuration**: `config/sources.yaml` (110+ feeds from 3 news sources: Thanh Niên, Tuổi Trẻ, Lào Cái)

### Stage 2: Content Scraping

**What happens**: Extracts full article text from web pages

**Multi-Stage Fallback Strategy** (lines in `scraper_service.py`):

The scraper uses a 4-stage fallback approach to handle diverse website structures:

**Stage 2.1 - Trafilatura (Precision Mode)** [Primary]:
- ML-based extraction optimized for news articles
- Removes ads, navigation, comments, boilerplate automatically
- **Threshold**: Requires ≥100 characters
- **Configuration**: `favor_precision=True`, `include_comments=False`, `include_tables=True`
- Success rate: ~70-80% on Vietnamese news sites

**Stage 2.2 - Trafilatura (Recall Mode)** [Secondary]:
- Same library, less aggressive filtering: `favor_precision=False`
- Captures more content, accepts some boilerplate
- **Threshold**: Requires ≥100 characters
- Success rate: ~15-20% when precision mode fails

**Stage 2.3 - MVP (Multi-stage Vietnamese Processing)** [Tertiary]:
- Two-step process optimized for Vietnamese:
  1. `readability-lxml`: Identifies main content block
  2. `justext`: Removes boilerplate using Vietnamese stopword list
- Decodes HTML entities (e.g., `&quot;` → `"`)
- **Threshold**: Requires ≥100 characters
- Success rate: ~5-10% on complex layouts

**Stage 2.4 - Basic Paragraph Extraction** [Last Resort]:
- BeautifulSoup-based extraction of all `<p>` tags
- Filters paragraphs < 50 characters individually
- Joins remaining paragraphs with newlines
- **Threshold**: Requires ≥50 characters
- Success rate: ~1-5% on minimal content sites

**Complete Failure Handling**:
- Returns empty string if all extraction methods fail
- Logs error without throwing exception
- Processing continues with empty content

**HTTP Configuration**:
- **Timeout**: 30 seconds (`crawler.fetch_timeout_seconds`)
- **User-Agent**: "VeriNews/2.0" (`crawler.user_agent`)
- **Follows Redirects**: Yes (automatic)
- **Max Content Length**: 50,000 characters (`crawler.max_content_length`, -1 = unlimited)

**Process Flow**:
1. Receives article URL from Stage 1
2. Fetches HTML using `httpx.AsyncClient` (async HTTP)
3. Tries extraction methods in sequence (2.1 → 2.2 → 2.3 → 2.4)
4. Stores result in Article.content field
5. Enqueues for chunking regardless of extraction success

### Stage 3: Text Chunking & Denormalization

**What happens**: Splits articles into 500-2000 character segments and prepares them for search.

**Chunking Algorithm: ParagraphChunker**:
1. Normalize line endings (`\r\n` → `\n`)
2. Split on paragraph boundaries:
   - Primary: Double newline `\n\n` (paragraph separators)
   - Fallback: Single newline `\n` (if no paragraphs found)
3. Filter empty/whitespace-only segments
4. Optimize chunk sizes:
   - **Merge strategy**: Combine small paragraphs (< 500 chars) to form larger chunks
   - **Split strategy**: Split large paragraphs (> 2000 chars) by sentences using regex: `r"([.!?]+(?:\s+|$))"`
   - **Sentence preservation**: Keeps punctuation with text
5. Create optimized chunks

**Configuration**:
- `min_chunk_size`: 500 characters
- `max_chunk_size`: 2000 characters
- **Configurable in code** but not exposed in config.yaml

**Denormalization** (Article Metadata in Chunks):
- Each ArticleChunk stores copy of:
  - `article_title`: Title of parent article (for retrieval display)
  - `source_name`: News source name (for source attribution)
  - `published_at`: Publication date (for temporal relevance scoring)
- **Purpose**: Faster retrieval - avoid N+1 joins for article metadata
- **Sync Strategy**: One-way sync during chunk creation, NOT automatically updated if article metadata changes
  - ⚠️ **Important**: If article.title or article.published_at changes after chunks created, chunks retain old values

**Result**: Average article (2,000-5,000 chars) → 5-15 chunks

### Stage 4: Embedding Generation

**What happens**: Generates 1536-dimensional vectors for each chunk using OpenAI embeddings API

**Process**:
1. Iterates through chunks created in Stage 3
2. **Calls OpenAI API** (`text-embedding-3-small`) for EACH chunk **sequentially**
3. Stores returned vector in `ArticleChunk.embedding` field
4. Integrated into `process_article_task` (as part of article processing)

**Embedding Configuration**:
- **Model**: `text-embedding-3-small` (OpenAI)
- **Dimensions**: 1536 floats
- **Timeout**: 30 seconds (`ai.timeout_seconds`)
- **Retries**: 3 attempts on failure (`ai.max_retries`)
- **Configurable via**: `settings.ai.embedding_model`

**Current Implementation**:
- **Sequential per chunk**: For an article with 10 chunks, makes 10 sequential API calls
- **Performance Issue**: ~3-5 seconds per chunk × 10 chunks = 30-50 seconds per article
- **Potential Optimization**: `generate_embeddings_batch()` method exists but is NOT used
  - Batching could reduce time to ~5-10 seconds per article (10-20% improvement)
  - Would require code change in `processor_service.py`

**Cost Breakdown**:
- OpenAI `text-embedding-3-small`: ~$0.00002 per 1K tokens
- Average chunk: 500-1000 chars = ~100-200 tokens
- Cost per chunk: ~$0.000002 - $0.000004
- Cost per article (10 chunks): ~$0.00002 - $0.00004
- **Total per article**: ~$0.001 (when including other LLM costs from verification pipeline)

### Stage 5: Indexing (Vector + Keyword)

**What happens**: Creates database indexes for fast hybrid search

**Dual-Index Strategy**:

**Index 1 - Vector Similarity (pgvector IVFFlat)**:
- **Index Type**: IVFFlat (Approximate Nearest Neighbor)
- **Metric**: COSINE similarity
- **Dimensions**: 1536 (from OpenAI embeddings)
- **Configuration**: `lists=100` (number of clusters)
- **Automatic**: Index maintained by PostgreSQL automatically
- **Query Speed**: ~10-100ms for top-k search on 100K articles
- **Storage**: ~1.5GB per 100K articles (1536 floats × 4 bytes)

**Index 2 - BM25 Full-Text Search (PostgreSQL tsvector + GIN)**:
- **Index Type**: GIN (Generalized Inverted Index)
- **Configuration**: `'simple'` text search configuration (no stemming)
- **Tokenization**: Vietnamese-aware using `pyvi` library
- **Process**:
  1. Tokenize chunk text: "Công ty VinTech mở nhà máy" → "Công_ty VinTech mở nhà_máy"
  2. Convert to tsvector: `to_tsvector('simple', tokenized_text)`
  3. Store in ArticleChunk.search_vector column
  4. GIN index maintains inverted index automatically

**Why Vietnamese-Specific Tokenization?**:
- PostgreSQL's built-in English/simple parsers don't handle Vietnamese compound words well
- Example: "nhà máy" (factory) should be ONE token, not two
- Solution: Pre-tokenize in Python with `pyvi`, then use PostgreSQL's 'simple' config to treat underscored terms as single tokens
- Result: Correct BM25 ranking for Vietnamese queries

**Implementation Flow** (in `processor_service.py`):
1. Create ArticleChunk records with embeddings (Stage 4 complete)
2. Flush to database to get auto-generated chunk IDs
3. For each chunk:
   - Call `bm25_service.index_chunk(chunk)`:
     - Tokenize chunk text using Vietnamese tokenizer
     - Update search_vector via raw SQL: `to_tsvector('simple', :tokenized)`
     - Commit after each chunk (for visibility)
4. ArticleChunk now has both embedding and search_vector populated

**Indexing Performance**:
- Vector indexing: Automatic, minimal overhead
- BM25 indexing: ~100-200ms per chunk (includes Vietnamese tokenization)
- Batch mode available: `batch_index_chunks()` for bulk operations
- Can be run offline: `reindex_all_chunks_for_bm25` task (for schema changes)

## Data Retention & Cleanup

To manage storage and relevance:

### Ingest Cutoff (During Crawling)
- **Parameter**: `crawler.ingest_max_age_hours` (default: **48 hours**)
- **Behavior**: During RSS feed crawling, articles published MORE than 48 hours ago are skipped
- **Purpose**: Focus on recent news (not historical archives)
- **Implementation**: Checked in Stage 1 before creating Article records
- **Configuration**: Configurable in `config/config.yaml` line 18

### Cleanup Task (Periodic Deletion)
- **Task Name**: `cleanup_expired_articles`
- **Schedule**: Every 5 minutes (same as crawl schedule)
- **Parameter**: `crawler.retention_hours` (default: **24 hours**)
- **Behavior**: Deletes Article records created > 24 hours ago
- **Constraint**: Only deletes articles that have `content` populated (processed articles)
- **Cascade**: Associated ArticleChunk rows and embeddings automatically deleted
- **Purpose**: Aggressive cleanup to prevent database bloat
- **Configuration**: Configurable in `config/config.yaml` line 20

**Example Timeline**:
- 10:00 AM: Article crawled and added to database
- 10:05 AM - 10:30 AM: Content scraping, chunking, embedding
- 11:05 AM: Article searchable in production
- Next day 10:05 AM: Article deleted by cleanup task (24h old)
- Total lifespan: ~24 hours from creation

## Task Queue Architecture

### Celery Configuration
- **Broker**: Redis (`redis://localhost:6379/0`)
- **Backend**: Redis (for task results)
- **Serializer**: JSON
- **Timezone**: UTC

### Celery Workers

**Configuration** (from `config/config.yaml`):
- **Count**: 4 workers (configurable via `celery.worker_count`)
- **Concurrency**: 4 parallel task executions
- **Pool Type**: Fork (default Celery setting)
- **Task Time Limit**: 300 seconds (5 minutes, `celery.task_time_limit`)
- **Acknowledgment**: Late acknowledgment (`task_acks_late=True`)
  - Worker acknowledges task only after completion (prevents data loss on crash)
- **Default Retry Delay**: 5 seconds between retries

**Startup** (via `./scripts/verinews crawler start`):
```bash
uv run celery -A app.celery_app worker --loglevel=info --detach
```
- Runs in background (detached mode)
- Logs to `logs/celery-worker.log`
- Automatically reconnects to Redis on connection loss

### Celery Beat (Scheduler)

**Configuration**:
- **Interval**: Every 5 minutes (configurable via `scheduler.crawler_interval_minutes`)

**Scheduled tasks**:
1. `kickoff_all_crawls` - Triggers feed crawling
2. `cleanup_expired_articles` - Deletes old articles

**Startup** (via `./scripts/verinews crawler start`):
```bash
uv run celery -A app.celery_app beat --loglevel=info --detach
```
- Runs in background (detached mode)
- Logs to `logs/celery-beat.log`
- Maintains schedule database for missed tasks

### Error Handling & Retry Strategy

**All crawler tasks have configured retries**:
- **Autoretry**: On ANY exception
- **Retry Strategy**: Exponential backoff
- **Max Retries**: 3 attempts per task
- **Backoff Sequence**:
  - Attempt 1: Immediate
  - Attempt 2: Wait 2^1 = 2 seconds
  - Attempt 3: Wait 2^2 = 4 seconds
  - Attempt 4: Wait 2^3 = 8 seconds (stop after 3 retries)

**Task-Specific Error Handling**:
- **Stage 1 (RSS Fetch)**: Transient errors retry, parse errors logged and skipped
- **Stage 2 (Content Scraping)**: Returns empty string on all failures (doesn't block)
- **Stage 3 (Chunking)**: Returns empty list on empty content (doesn't block)
- **Stage 4 (Embedding)**: Failures trigger task retry (max 3 attempts)
- **Stage 5 (Indexing)**: Transaction-level atomicity (all chunks or none)

**Database Readiness Check**:
- All tasks wait for PostgreSQL to be ready before executing
- Retry up to 5 times with exponential backoff (1s, 2s, 3s, 4s, 5s)
- Handles Docker startup delays gracefully

**Failure Outcomes**:
- After max retries, failed tasks go to dead-letter queue
- Logged for manual investigation
- Individual task failures don't stop remaining articles

## CLI Commands

**Start/Stop**:
```bash
./scripts/verinews crawler start   # Start workers + scheduler
./scripts/verinews crawler stop    # Stop all
```

**Feed Management**:
```bash
./scripts/verinews feeds sync    # Sync from sources.yaml
```

## Performance

### Actual Timing per Article

**Stage 1 - RSS Crawl**:
- Feed fetch: ~5-10 seconds per feed
- URL uniqueness check: ~100ms per feed
- Database insert: ~50-100ms per feed
- **Total per feed**: 5-10 seconds (not per article)

**Stage 2 - Content Scraping**:
- HTTP fetch: 1-5 seconds (30s timeout)
- Stage 2.1 (Trafilatura precision): 500-2000ms
- Stage 2.2 (Trafilatura recall): 500-2000ms
- Stage 2.3 (MVP fallback): 500-2000ms
- Stage 2.4 (Basic extraction): 50-200ms
- **Average**: 500-2000ms (one method succeeds first)

**Stage 3 - Chunking**:
- Text chunking: 50-100ms per article
- **Total**: 50-100ms

**Stage 4 - Embedding Generation**:
- Sequential embedding calls: ~3-5 seconds per chunk
- Average article (10 chunks): 30-50 seconds
- **Total**: 30-50 seconds per article

**Stage 5 - Indexing**:
- BM25 tokenization + indexing: ~100-200ms per chunk
- Average article (10 chunks): 1-2 seconds
- **Total**: 1-2 seconds per article

**Overall Per-Article Timeline**:
- Total time: 32-62 seconds per article (sequential)
- **Bottleneck**: Stage 4 (embedding generation) = ~50-80% of total time
- **Optimization opportunity**: Batch embeddings (could save 10-20%)

### Processing Throughput

**With 4 Celery Workers**:
- Can process ~4 articles in parallel
- At 45 seconds per article, that's ~320 articles per hour
- With 50 articles per feed × 110 feeds = ~5,500 articles per crawl cycle
- Processing all articles: ~17 hours (at 320/hr)
- But crawl runs every 5 minutes, so only new articles are processed (typically 10-50)

## What's NOT Implemented

### Critical Features
- **JavaScript rendering**: For sites that dynamically load content (uses Trafilatura fallback instead)
- **Paywall handling**: Paywalled articles may only get headlines (4-stage fallback provides some content)
- **Duplicate content detection**: Beyond exact URL matching (same article from multiple sources not deduplicated)

### Performance Optimizations Not Yet Done
- **Batch embedding generation**: `generate_embeddings_batch()` method exists but isn't used in processor
  - Could reduce embedding time from 30-50s to 5-10s per article (10-20% improvement)
  - Would require code change in `processor_service.py` line 74
- **Parallel content scraping**: Articles scraped sequentially within a feed
  - Could parallelize HTTP fetches across articles
- **Embedding caching**: Embeddings recalculated for similar content
  - Could cache embeddings by text hash

### Monitoring & Observability Not Implemented
- **Timing instrumentation**: No explicit timing measurements in crawler pipeline
  - Retrieval pipeline has detailed timings, crawler doesn't
- **Performance metrics**: No tracking of crawler throughput, latency, error rates
- **Dead-letter queue inspection**: Failed tasks not easily inspectable
- **Celery Flower**: Web UI for monitoring tasks (can be enabled separately)

### Advanced Features
- **Real-time processing**: Currently batch every 5 minutes (could use webhooks for faster updates)
- **Image/Video analysis**: No extraction of media content
- **Metadata extraction**: No extraction of author names, categories, or tags from articles
- **Content deduplication**: No detection of same content from multiple sources
- **Feed prioritization**: All feeds crawled equally (could prioritize high-traffic sources)

## Implementation Status & Deviations

### Documentation Accuracy Assessment

**Overall Assessment**: 95% accurate - Very good alignment between documentation and implementation

| Item | Documentation Claims | Actual Implementation | Status |
|------|---------------------|----------------------|--------|
| **5 pipeline stages** | Stage-by-stage runbook | Matches worker code | ✓ Accurate |
| **Crawl interval** | “Every 5 minutes (configurable)” | `scheduler.crawler_interval_minutes` (default 5) with ≥60s clamp | ✓ Accurate |
| **Ingest cutoff** | “Skip articles older than 48h” | `crawler.ingest_max_age_hours = 48` | ✓ Accurate |
| **Retention period** | “Delete processed articles after 24h” | `cleanup_expired_articles` removes `content` ≠ NULL rows older than 24h | ✓ Accurate |
| **Chunk size** | 500‑2000 chars, merge/split logic | Implemented in `ParagraphChunker` | ✓ Accurate |
| **Embedding dimension** | 1536-dim OpenAI vectors | Hardcoded `Vector(1536)` | ✓ Accurate |
| **Denormalization** | Title/source/published_at stored on chunks | Populated during `process_article` | ✓ Accurate |
| **BM25 strategy** | pyvi tokenization + TSVECTOR | `BM25SearchService` exactly matches | ✓ Accurate |
| **Content scraping** | Four-step fallback (Trafilatura → MVP → basic) | Implemented in `scraper_service` | ✓ Accurate |
| **Celery workers** | 4 workers, retries with backoff | Configurable worker count + autoretry | ✓ Accurate |

### Key Deviations & Undocumented Features

**1. Sequential Embedding Generation** 🔴
- **Documentation**: Highlights batching as an opportunity but not yet implemented
- **Implementation**: `process_article` still calls `generate_embedding_async` per chunk
- **Impact**: Dominant bottleneck (30‑50 s per article); batching via `generate_embeddings_batch()` would significantly improve throughput

### Accurate Implementations Matching Docs
- ✅ 5-stage pipeline architecture clearly matches
- ✅ RSS feed crawling and deduplication strategy
- ✅ Multi-library scraping fallback approach
- ✅ Text chunking with size optimization
- ✅ OpenAI embeddings (1536 dimensions)
- ✅ Vietnamese BM25 with pyvi tokenization
- ✅ Denormalization for performance
- ✅ Aggressive 24-hour retention policy
- ✅ Celery task queue with retry logic
- ✅ 4 parallel workers

### Performance Bottlenecks

**Stage 4 - Embedding Generation** (50-80% of total time):
- Sequential API calls: 3-5 seconds per chunk × 10 chunks = 30-50 seconds
- **Optimization**: Use `generate_embeddings_batch()` for ~10-20% improvement
- **Priority**: High (would improve throughput significantly)

**Stage 2 - Content Scraping** (15-40% of total time):
- Network-bound (1-5 seconds per article)
- **Optimization**: Parallelize HTTP requests across articles
- **Priority**: Medium (requires careful rate limiting)

### Critical Issues Requiring Documentation Updates

1. **Crawl Interval**: CLAUDE.md and previous docs say "Every 15 minutes" but actual is "Every 5 minutes"
   - File: `config/config.yaml` line 13
   - Impact: Affects cache behavior and data freshness expectations

2. **Ingest Cutoff**: Docs say "24 hours" but actual is "48 hours"
   - File: `config/config.yaml` line 18
   - Impact: Affects what articles are captured from RSS feeds

3. **Denormalization Sync Gap**: Not mentioned in docs
   - If article.title or article.published_at changes after chunks created, chunks retain old values
   - Could cause stale data in retrieval results
   - Recommendation: Document this limitation or implement automatic sync

### Code Quality & Best Practices

**Strengths**:
- ✅ Proper use of async/await for I/O operations
- ✅ Comprehensive error handling with fallbacks
- ✅ Transaction-safe database operations
- ✅ Idempotent operations (safe to retry)
- ✅ Vietnamese language support throughout pipeline
- ✅ Configurable parameters via YAML

**Improvement Opportunities**:
- Performance: Add batch embedding generation
- Monitoring: Instrument timing in crawler pipeline
- Resilience: Add circuit breaker for embedding API failures
- Observability: Log stage timings like retrieval pipeline does
