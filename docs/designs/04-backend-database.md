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
Represents trusted news organizations.

**Fields**:
- `id` (UUID, PK)
- `name` (String, unique) - e.g., "VnExpress", "Tuổi Trẻ"
- `base_url` (String, unique) - e.g., "https://vnexpress.net/"
- `created_at`, `updated_at` (Timestamps)

**Relationships**:
- Has many `RssFeed`s

### RssFeed
RSS feed configurations for crawling specific topics/sections.

**Fields**:
- `id` (UUID, PK)
- `source_id` (UUID, FK -> NewsSource)
- `feed_url` (String, unique)
- `topic` (String, optional) - e.g., "Politics", "Technology"
- `is_active` (Boolean, default=True)
- `last_fetched_at` (DateTime, optional)
- `created_at`, `updated_at` (Timestamps)

**Configured in**: `config/sources.yaml`

### Article
News articles collected from feeds.

**Fields**:
- `id` (UUID, PK)
- `feed_id` (UUID, FK -> RssFeed)
- `title` (String)
- `url` (String, unique)
- `content` (Text, optional) - Full article text
- `published_at` (DateTime, optional)
- `created_at`, `updated_at` (Timestamps)

**Relationships**:
- Belongs to `RssFeed`
- Has many `ArticleChunk`s

### ArticleChunk
Text chunks with embeddings for search.

**Fields**:
- `id` (UUID, PK)
- `article_id` (UUID, FK -> Article)
- `chunk_index` (Integer) - Order within article
- `chunk_text` (Text) - The actual content chunk
- **`embedding`** (VECTOR(1536)) - OpenAI embedding for semantic search
- **`search_vector`** (TSVECTOR) - Vietnamese-tokenized vector for keyword search
- **Denormalized Fields** (for faster retrieval):
  - `article_title`, `source_name`, `published_at`
- `created_at`, `updated_at` (Timestamps)

**Key point**: This is what gets searched. Each article is split into multiple chunks.

### VerificationRequest
Tracks user requests to verify Facebook posts.

**Fields**:
- `id` (UUID, PK)
- `original_text` (Text) - The raw Facebook post
- `text_hash` (String, unique index) - SHA256 of text for caching
- `clean_query` (Text) - Cleaned by AI
- `claims` (JSON) - Extracted claims list
- `status` (Enum) - PENDING, PROCESSING, COMPLETED, FAILED
- `created_at`, `updated_at` (Timestamps)

**Relationships**:
- Has one `RetrievalResult`

### RetrievalResult
Stores the full output of the retrieval pipeline for a request.

**Fields**:
- `id` (UUID, PK)
- `request_id` (UUID, FK -> VerificationRequest, unique)
- **`retrieved_chunks_json`** (JSON) - Intermediate RRF results
- **`reranked_chunks_json`** (JSON) - Results after AI reranking
- **`final_articles_json`** (JSON) - Final aggregated article results with confidence scores
- **`stage_timings_json`** (JSON) - Performance metrics breakdown
- `processing_time_ms` (Integer)
- `created_at` (Timestamp)

**Design Choice**: Uses JSON fields to store complex, nested pipeline results instead of normalized tables, as these are read-heavy, write-once records used for history/auditing.

## How Search Works

### Vector Search (Semantic)

**Index**: IVFFlat on `ArticleChunk.embedding`
```sql
CREATE INDEX article_chunk_embedding_idx
ON article_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

**Query**: Find similar chunks by cosine distance
```sql
SELECT id, chunk_text, article_id,
       1 - (embedding <=> :query_vector) AS score
FROM article_chunks
ORDER BY embedding <=> :query_vector
LIMIT 100;
```

### Full-Text Search (Keyword)

**Index**: GIN on `ArticleChunk.search_vector`
```sql
CREATE INDEX article_chunk_search_vector_idx
ON article_chunks
USING GIN (search_vector);
```

**Query**: BM25-style ranking with Vietnamese tokenization
```sql
SELECT id, chunk_text, article_id,
       ts_rank_cd(search_vector, query) AS score
FROM article_chunks,
     to_tsquery('simple', :tokenized_query) query
WHERE search_vector @@ query
ORDER BY score DESC
LIMIT 100;
```
*Note: Uses 'simple' config because we handle Vietnamese tokenization in Python via `pyvi` before indexing.*

## Database Migrations

Using Alembic for schema versioning:
- Migrations in `backend/alembic/versions/`
- Run migrations: `uv run alembic upgrade head`
- Create migration: `uv run alembic revision --autogenerate -m "description"`

## Access

**Adminer UI**: http://localhost:8080
- Server: postgres
- Default username: verinews_user
- Default password: verinews_password
- Database: verinews_db

## Performance

**Optimization**:
- **Denormalization**: `ArticleChunk` stores `article_title` and `source_name` to avoid 3-way joins during search.
- **Indexing**: IVFFlat for vectors, GIN for text, B-tree for UUIDs/Foreign Keys.
- **Connection Pooling**: Async SQLAlchemy with configured pool size.
