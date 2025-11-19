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

**Trigger**: Celery Beat runs every 15 minutes (configurable)

**Process**:
1. Scheduler triggers `kickoff_all_crawls` task
2. Queries database for active RSS feeds
3. For each feed:
   - Fetches RSS XML
   - Parses to extract article URLs
   - **Ingest Cutoff**: Skips articles older than 24 hours (configurable)
   - Checks if URL already in database (skip if exists)
   - Creates Article record with basic metadata
4. Enqueues article for processing

**Feed configuration**: `config/sources.yaml`

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

### Stage 3: Text Chunking & Denormalization

**What happens**: Splits articles into 500-2000 character segments and prepares them for search.

**Process**:
1. Receives article content
2. Splits on paragraph boundaries (using smart `\n` and `\n\n` handling)
3. **ParagraphChunker**:
   - Merges small paragraphs (< 500 chars)
   - Splits large paragraphs (> 2000 chars) on sentences
4. Creates ArticleChunk records
5. **Denormalization**: Copies metadata to chunk for faster retrieval:
   - `article_title`
   - `source_name`
   - `published_at`

**Result**: Average article → 5-20 chunks

### Stage 4: Embedding Generation

**What happens**: Generates 1536-dimensional vectors for each chunk

**Process**:
1. Iterates through chunks created in Stage 3
2. Calls OpenAI API (`text-embedding-3-small`) for each chunk
3. Stores vector in `ArticleChunk.embedding`
4. Handling is integrated into the `process_article_task` (sequential processing per article)

**Cost**: ~$0.001 per article (average 10 chunks)

### Stage 5: Indexing (Vector + Keyword)

**What happens**: Creates database indexes for fast hybrid search

**Process**:
1. **Vector Indexing**: `pgvector` automatically maintains IVFFlat index on `embedding` column.
2. **Keyword Indexing**:
   - Tokenizes text using `pyvi` (Vietnamese tokenizer)
   - Generates search vector: `to_tsvector('simple', tokenized_text)`
   - Stores in `search_vector` column
   - Updates GIN index automatically

**Why `pyvi` + `simple`?**
- PostgreSQL's built-in parsers don't handle Vietnamese compound words well (e.g., "nhà máy").
- We tokenize in Python ("nhà_máy") and use 'simple' config to treat them as single tokens.

## Data Retention & Cleanup

To manage storage and relevance:

1. **Ingest Cutoff**:
   - Articles older than `crawler.ingest_max_age_hours` (default: 24h) are skipped during crawling.

2. **Cleanup Task**:
   - `cleanup_expired_articles` runs periodically
   - Deletes articles created > `crawler.retention_hours` ago (default: 24h)
   - Cascading deletes remove associated chunks and embeddings

## Task Queue Architecture

### Celery Workers

**Configuration**:
- 4 workers (adjustable)
- Handles concurrent processing of multiple feeds/articles

### Celery Beat (Scheduler)

**Scheduled tasks**:
- Crawl all feeds: Every 15 minutes
- Cleanup expired articles: Every 15 minutes

### Error Handling

**Retry logic**:
- Network errors: Retry 3 times with backoff
- Permanent failures: Logged and skipped

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

**Timing per article**:
- RSS fetch: 5-10 seconds
- Content scraping: 10-30 seconds
- Chunking & Embedding: 5-10 seconds
- **Total**: 30-60 seconds per article

## What's NOT Implemented

- JavaScript rendering (for JS-heavy sites)
- Paywall handling
- Image/Video analysis
- Real-time processing (currently batch every 15 min)
- Duplicate content detection (beyond URL check)
