# Data Ingestion Pipeline

## What It Is

The data pipeline continuously collects news articles from RSS feeds, extracts their content, splits them into chunks, and generates embeddings so they're searchable.

## Technology Stack

- **Celery**: Background task processor
- **Redis**: Message broker (task queue)
- **Celery Beat**: Scheduler for periodic tasks
- **Trafilatura**: Article content extraction
- **OpenAI**: Embedding generation

## The Pipeline (5 Stages)

### Stage 1: RSS Feed Crawling

**What happens**: Checks RSS feeds for new articles

**Trigger**: Celery Beat runs every 60 minutes (configurable)

**Process**:
1. Scheduler triggers `kickoff_all_crawls` task
2. Queries database for active RSS feeds
3. For each feed:
   - Fetches RSS XML
   - Parses to extract article URLs
   - Checks if URL already in database (skip if exists)
   - Creates Article record with basic metadata
4. Enqueues article for processing

**Feed configuration**: `config/sources.yaml`

**Example feed**:
```yaml
- name: "BBC News"
  feeds:
    - url: "http://feeds.bbci.co.uk/news/rss.xml"
      topic: "general"
      fetch_frequency_minutes: 60
```

### Stage 2: Content Scraping

**What happens**: Extracts full article text from web pages

**Process**:
1. Receives article URL from Stage 1
2. Fetches HTML using HTTP GET
3. Extracts content using Trafilatura
   - Removes ads, navigation, comments
   - Extracts: title, author, date, main text
4. Validates content (min 100 words)
5. Stores in Article.content field
6. Enqueues for chunking

**Fallback strategy**:
- Primary: Trafilatura (best quality)
- If fails: Store error, mark as failed

**Polite crawling**:
- Respects robots.txt
- Rate limiting per domain
- 1-2 second delays between requests

### Stage 3: Text Chunking

**What happens**: Splits articles into 500-2000 character segments

**Process**:
1. Receives article content
2. Splits on paragraph boundaries
3. Smart merging/splitting:
   - Merge small paragraphs (< 500 chars)
   - Split large paragraphs (> 2000 chars) on sentences
4. Creates ArticleChunk records
5. Stores each chunk with:
   - article_id (foreign key)
   - chunk_index (order)
   - text content
   - word count

**Vietnamese optimization**:
- Preserves compound words
- Handles both `\n` and `\n\n` paragraph breaks
- Sentence-aware splitting

**Result**: Average article → 5-20 chunks

### Stage 4: Embedding Generation

**What happens**: Generates 1536-dimensional vectors for each chunk

**Process**:
1. Collects batches of pending chunks (100 at a time)
2. Sends batch to OpenAI API
3. Receives array of 1536-dim vectors
4. Normalizes vectors to unit length
5. Stores in ArticleChunk.embedding column
6. Updates ArticleChunk status

**Optimization**:
- Batch processing (100 chunks per API call)
- Parallel workers (4-8 concurrent)
- Rate limiting (respects OpenAI limits)

**Cost**: ~$0.001 per article (average 10 chunks)

### Stage 5: Indexing

**What happens**: Creates database indexes for fast search

**Process**:
1. Generates full-text search vector
   - `to_tsvector('vietnamese', chunk.text)`
   - Stores in `search_vector` column
2. Vector indexes updated automatically by PostgreSQL
3. Runs ANALYZE to update statistics

**Indexes**:
- IVFFlat index on embeddings (for vector search)
- GIN index on search_vector (for text search)

## Task Queue Architecture

### Celery Workers

**Configuration**:
- 4 workers (adjustable)
- 4 threads per worker
- Total: 16 concurrent tasks

**Task priorities**:
- RSS crawling: Normal
- Content processing: Normal
- Embedding generation: Normal

### Celery Beat (Scheduler)

**Scheduled tasks**:
- Crawl all feeds: Every 60 minutes
- Cleanup failed: Daily at 2 AM
- Rebuild indexes: Weekly Sunday 3 AM

### Error Handling

**Retry logic**:
- Network errors: Retry 3 times with backoff
- Rate limits: Wait and retry
- Permanent failures: Mark as failed, don't retry

**Failed article tracking**:
- Stores error message
- Increments error_count on feed
- Auto-disables feed after many failures

## CLI Commands

**Start/Stop**:
```bash
./scripts/verinews crawler start   # Start workers + scheduler
./scripts/verinews crawler stop    # Stop all
./scripts/verinews crawler status  # Check status
```

**Feed Management**:
```bash
./scripts/verinews feeds sync    # Sync from sources.yaml
./scripts/verinews feeds list    # List all feeds
./scripts/verinews feeds add URL # Add new feed
```

**Monitoring**:
```bash
./scripts/verinews logs worker   # View worker logs
./scripts/verinews logs beat     # View scheduler logs
```

## Performance

**Throughput**:
- Current: ~1000 articles/day
- Scalable to: 10,000+ articles/day

**Timing per article**:
- RSS fetch: 5-10 seconds
- Content scraping: 10-30 seconds
- Chunking: 1-2 seconds
- Embedding: 5-10 seconds
- **Total**: 30-60 seconds per article

## Monitoring

**Key metrics**:
- Articles processed per hour
- Success/failure rates
- Queue lengths
- Processing time per stage

**Logs**:
- Worker logs: `logs/celery-worker.log`
- Beat logs: `logs/celery-beat.log`

## What's NOT Implemented

- JavaScript rendering (for JS-heavy sites)
- Paywall handling
- Image extraction
- Video transcription
- Real-time processing (currently batch every hour)
- Duplicate detection
- Multi-region crawling
