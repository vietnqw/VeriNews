# Backend: Database

## What It Is

The database stores all news articles, their text chunks, embeddings, and metadata. It's PostgreSQL with the pgvector extension for vector search.

## Database: PostgreSQL 18 + pgvector

**Why PostgreSQL**:
- Reliable, mature relational database
- pgvector extension adds vector similarity search
- Full-text search built-in
- Handles both structured data and vectors

**pgvector Extension**:
- Stores high-dimensional vectors (1536 dimensions)
- Fast similarity search using IVFFlat index
- Cosine distance operations built-in

## Data Models

### NewsSource
Represents trusted news organizations

**Fields**:
- id, name, url
- credibility_rating (high/medium/low)
- country, language
- is_active (can disable sources)
- timestamps

**Example**: BBC News, CNN, VnExpress

### RssFeed
RSS feed configurations for crawling

**Fields**:
- id, news_source_id
- url (RSS feed URL)
- topic (politics, tech, etc.)
- fetch_frequency_minutes
- is_active
- last_fetched_at, error_count
- timestamps

**Configured in**: `config/sources.yaml`

### Article
News articles collected from feeds

**Fields**:
- id, news_source_id, rss_feed_id
- title, url, author
- published_at
- content (full article text)
- language, word_count
- indexed_at (when chunks created)
- timestamps

### ArticleChunk
Text chunks with embeddings for search

**Fields**:
- id, article_id
- chunk_index (order within article)
- text (500-2000 characters)
- word_count
- **embedding** (VECTOR(1536)) - for semantic search
- **search_vector** (tsvector) - for keyword search
- timestamp

**Key point**: This is what gets searched. Each article is split into multiple chunks.

### VerificationRequest
Tracks verification requests (currently minimal use)

**Fields**:
- id, post_text, post_metadata
- status, verdict, credibility_score
- explanation, evidence
- processing_time_ms, cached
- timestamps

### RetrievalResult
Links verification requests to retrieved articles

**Fields**:
- id, verification_request_id, article_id
- relevance_score, rank
- matching_chunks
- timestamp

## How Search Works

### Vector Search (Semantic)

**Index**: IVFFlat on `ArticleChunk.embedding`
```sql
CREATE INDEX article_chunk_embedding_idx
ON article_chunk
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

**Query**: Find similar chunks by cosine distance
```sql
SELECT id, article_id, text,
       1 - (embedding <=> :query_vector) AS similarity
FROM article_chunk
ORDER BY embedding <=> :query_vector
LIMIT 50;
```

The `<=>` operator is cosine distance (lower = more similar)

### Full-Text Search (Keyword)

**Index**: GIN on `ArticleChunk.search_vector`
```sql
CREATE INDEX article_chunk_search_vector_idx
ON article_chunk
USING GIN (search_vector);
```

**Query**: BM25-style ranking
```sql
SELECT id, article_id, text,
       ts_rank_cd(search_vector, query) AS relevance
FROM article_chunk,
     to_tsquery('vietnamese', :query) query
WHERE search_vector @@ query
ORDER BY ts_rank_cd(search_vector, query) DESC
LIMIT 50;
```

`ts_rank_cd` provides BM25-like ranking (term frequency, document length normalization)

## Database Migrations

Using Alembic for schema versioning:
- Migrations in `backend/alembic/versions/`
- Run migrations: `uv run alembic upgrade head`
- Create migration: `uv run alembic revision --autogenerate -m "description"`

## Connection Management

- Async SQLAlchemy (AsyncEngine, AsyncSession)
- Connection pooling configured
- Handles concurrent requests efficiently

## Access

**Adminer UI**: http://localhost:8080
- Server: postgres
- Default username: verinews_user
- Default password: verinews_password
- Database: verinews_db

## Performance

**Current capacity**:
- Handles ~100K article chunks efficiently
- Vector search: ~30-50ms
- Keyword search: ~20-30ms
- Scales to millions with proper indexing

**Optimization**:
- IVFFlat index for fast approximate vector search
- GIN index for fast text search
- Connection pooling reduces overhead
- Async operations for concurrency

## What's NOT Implemented

- Read replicas (for scaling reads)
- Partitioning (for very large datasets)
- Advanced analytics tables
- User authentication tables
