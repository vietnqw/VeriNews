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

All models located in `/backend/app/models/` with complete ORM definitions using SQLAlchemy 2.0 async.

### NewsSource
Represents trusted news organizations/sources.

**Table Name:** `news_sources`

**Fields**:
| Field | Type | Constraints | Purpose |
|-------|------|-----------|---------|
| `id` | UUID | PK | Auto-generated identifier |
| `name` | String(255) | UNIQUE, NOT NULL | Source name (e.g., "VnExpress") |
| `base_url` | String(512) | UNIQUE, NOT NULL | Domain base URL |
| `created_at` | DateTime | NOT NULL, server_default=now() | Creation timestamp |
| `updated_at` | DateTime | NOT NULL, auto-updated | Last update timestamp |

**Relationships**:
- One-to-Many: `rss_feeds` (cascade delete-orphan)

**Constraints**:
- Primary Key: `id`
- Unique Constraint: `name` (prevent duplicate sources)
- Unique Constraint: `base_url` (prevent duplicate domains)

### RssFeed
RSS feed configurations for crawling specific topics/sections.

**Table Name:** `rss_feeds`

**Fields**:
| Field | Type | Constraints | Purpose |
|-------|------|-----------|---------|
| `id` | UUID | PK | Auto-generated identifier |
| `source_id` | UUID | FK→news_sources.id, NOT NULL | Parent news source |
| `feed_url` | String(512) | UNIQUE, NOT NULL | RSS feed URL |
| `topic` | String(255) | NULLABLE | Topic category (e.g., "Politics") |
| `is_active` | Boolean | NOT NULL, default=true | Feed active status |
| `last_fetched_at` | DateTime | NULLABLE | Last successful fetch timestamp |
| `created_at` | DateTime | NOT NULL, server_default=now() | Creation timestamp |
| `updated_at` | DateTime | NOT NULL, auto-updated | Last update timestamp |

**Relationships**:
- Many-to-One: `news_source` (parent NewsSource)
- One-to-Many: `articles` (cascade delete-orphan)

**Constraints**:
- Primary Key: `id`
- Unique Constraint: `feed_url` (prevent duplicate feeds)
- Foreign Key: `source_id` → `news_sources.id` (ON DELETE CASCADE)
- Index: `source_id` (for lookup)

**Configured in**: `config/sources.yaml` (YAML template for RSS sources)

### Article
News articles collected from RSS feeds.

**Table Name:** `articles`

**Fields**:
| Field | Type | Constraints | Purpose |
|-------|------|-----------|---------|
| `id` | UUID | PK | Auto-generated identifier |
| `feed_id` | UUID | FK→rss_feeds.id, NOT NULL | Parent RSS feed |
| `title` | String(512) | NOT NULL | Article headline |
| `url` | String(1024) | UNIQUE, NOT NULL | Canonical article URL |
| `content` | Text | NULLABLE | Full article body (raw HTML/text) |
| `published_at` | DateTime | NULLABLE | Original publication date |
| `created_at` | DateTime | NOT NULL, server_default=now() | When crawled/indexed |
| `updated_at` | DateTime | NOT NULL, auto-updated | Last update timestamp |

**Relationships**:
- Many-to-One: `rss_feed` (parent RssFeed)
- One-to-Many: `chunks` (cascade delete-orphan, ordered by chunk_index)

**Constraints**:
- Primary Key: `id`
- Unique Constraint: `url` (prevent duplicate articles)
- Foreign Key: `feed_id` → `rss_feeds.id` (ON DELETE CASCADE)
- Index: `feed_id` (for lookup), `published_at` (for sorting)

### ArticleChunk (CRITICAL FOR SEARCH)
Text chunks with semantic embeddings - the core search table.

**Table Name:** `article_chunks`

**Fields**:
| Field | Type | Constraints | Purpose |
|-------|------|-----------|---------|
| `id` | UUID | PK | Auto-generated identifier |
| `article_id` | UUID | FK→articles.id, NOT NULL | Parent article |
| `chunk_index` | Integer | NOT NULL | Sequential position (0-based) |
| `chunk_text` | Text | NOT NULL | Paragraph-level content |
| **`embedding`** | **Vector(1536)** | **NOT NULL** | **OpenAI embedding (1536-dim)** |
| **`search_vector`** | **TSVECTOR** | **NULLABLE** | **FTS vector (Vietnamese-tokenized)** |
| `article_title` | String(512) | NULLABLE | **DENORM** from Article.title |
| `source_name` | String(256) | NULLABLE | **DENORM** from NewsSource.name |
| `published_at` | DateTime | NULLABLE | **DENORM** from Article.published_at |
| `created_at` | DateTime | NOT NULL, server_default=now() | Creation timestamp |
| `updated_at` | DateTime | NOT NULL, auto-updated | Last update timestamp |

**Relationships**:
- Many-to-One: `article` (parent Article)

**Constraints**:
- Primary Key: `id`
- Unique Constraint: `(article_id, chunk_index)` - ensure chunk order integrity
- Foreign Key: `article_id` → `articles.id` (ON DELETE CASCADE)

**Critical Indexes** (See Search Implementation section):
- **IVFFlat** on `embedding` (vector_cosine_ops, lists=100) - semantic search
- **GIN** on `search_vector` - full-text search

**Denormalization Design**:
- **Why:** Search returns 100+ chunks per query; avoids 2-3 table joins
- **Fields:** `article_title`, `source_name`, `published_at` from parent tables
- **Sync:** Populated on chunk creation; no auto-sync on article updates (potential gap)
- **Performance Impact:** Eliminates ~90% of joins in result retrieval

**Key Point**: This table is searched extensively; IVFFlat + GIN indexes are critical performance

### VerificationRequest
Tracks user verification requests for Facebook posts.

**Table Name:** `verification_requests`

**Fields**:
| Field | Type | Constraints | Purpose |
|-------|------|-----------|---------|
| `id` | UUID | PK | Auto-generated identifier |
| `original_text` | Text | NOT NULL | Raw Facebook post text |
| `text_hash` | String(64) | UNIQUE, INDEXED, NOT NULL | SHA256 hash for cache lookup |
| `clean_query` | Text | NULLABLE | AI-cleaned query from extraction |
| `claims` | JSON | NULLABLE | Array of extracted claims |
| `status` | Enum | NOT NULL, default=PENDING | Request status (see below) |
| `created_at` | DateTime | NOT NULL, server_default=now() | Request timestamp |
| `updated_at` | DateTime | NOT NULL, auto-updated | Last status update |

**Status Enum Values** (stored as lowercase strings in the database):
- `pending` - Request received, not yet processing
- `processing` - Currently verifying
- `completed` - Verification finished
- `failed` - Error during verification

**Relationships**:
- One-to-One: `retrieval_result` (cascade delete-orphan, optional)

**Constraints**:
- Primary Key: `id`
- Unique Constraint: `text_hash` - enables exact-match cache lookup
- Index: `text_hash` (for fast O(log N) cache checks)

**Cache Strategy**:
- **Key Generation:** SHA256(original_text) → text_hash
- **Redis Lookup:** Check if text_hash exists in Redis (24-hour TTL)
- **Miss Action:** If not found in Redis, run full verification pipeline

### RetrievalResult
Stores complete pipeline output for a verification request (audit/history trail).

**Table Name:** `retrieval_results`

**Fields**:
| Field | Type | Constraints | Purpose |
|-------|------|-----------|---------|
| `id` | UUID | PK | Auto-generated identifier |
| `request_id` | UUID | FK→verification_requests.id, UNIQUE, NOT NULL | Parent request (1:1) |
| **`retrieved_chunks_json`** | **JSON** | **NULLABLE** | **RRF-fused search results** |
| **`reranked_chunks_json`** | **JSON** | **NULLABLE** | **After LLM chunk reranking** |
| **`final_articles_json`** | **JSON** | **NULLABLE** | **Final aggregated articles + verdicts** |
| **`stage_timings_json`** | **JSON** | **NULLABLE** | **Perf breakdown {stage: ms, ...}** |
| `processing_time_ms` | Integer | NULLABLE | Total pipeline duration (milliseconds) |
| `created_at` | DateTime | NOT NULL, server_default=now() | When result was generated |

**Relationships**:
- One-to-One: `verification_request` (parent VerificationRequest)

**Constraints**:
- Primary Key: `id`
- Unique Constraint: `request_id` (one result per verification)
- Foreign Key: `request_id` → `verification_requests.id` (ON DELETE CASCADE)

**JSON Structure Examples**:

**retrieved_chunks_json:**
```json
[
  {
    "chunk_id": "uuid",
    "chunk_index": 12,
    "chunk_text": "...",
    "article_id": "uuid",
    "article_title": "Article title",
    "source_name": "VnExpress",
    "score": 0.85
  }
]
```

**final_articles_json:**
```json
[
  {
    "article_id": "uuid",
    "title": "...",
    "source_name": "VnExpress",
    "published_at": "2025-01-15T10:30:00Z",
    "url": "https://example.com/article",
    "relevance_score": 8.5,
    "chunk_count": 3,
    "relevant_chunks": [
      {
        "chunk_id": "uuid",
        "chunk_index": 0,
        "chunk_text": "...",
        "score": 8.2
      }
    ]
  }
]
```

**stage_timings_json:**
```json
{
  "query_extraction": 250.0,
  "embedding": 300.5,
  "hybrid_search": 500.4,
  "fusion": 20.1,
  "reranking": 800.6,
  "aggregation": 15.2,
  "article_reranking": 140.7,
  "confidence_scoring": 200.0
}
```

**Design Choice - JSON vs Normalized Tables**:
- ✅ **Why JSON:** These are write-once, read-heavy historical records
- ✅ **Audit Trail:** Complete pipeline snapshot for each verification
- ✅ **Schema Flexibility:** Results change as algorithms improve
- ✅ **Performance:** No joins needed to retrieve complete result
- ⚠️ **Tradeoff:** Can't efficiently query individual fields (OK for audit logs)

## How Search Works

### Hybrid Search Architecture

VeriNews uses **dual parallel search** combining semantic + lexical matching:

```
Post Input
    ↓
Query Extraction (LLM) → 1 clean_query + N claims
    ↓
Embedding Generation (OpenAI) → 1536-dim vectors for each query
    ↓
Parallel Search (for each query):
    ├─ Vector Search (pgvector IVFFlat)
    │   └─ 100 semantically similar chunks
    └─ BM25 Search (PostgreSQL FTS GIN)
        └─ 100 keyword-matching chunks
    ↓
RRF Fusion → merge ranked lists (100-200 unique chunks)
    ↓
[Continue to reranking...]
```

### Vector Search (Semantic Similarity)

**Index Definition**:
```sql
CREATE INDEX ix_article_chunks_embedding_ivfflat
ON article_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

**Index Details**:
- **Type:** IVFFlat (Inverted File with Flat encoding)
- **Dimension:** 1536 (OpenAI text-embedding-3-small standard)
- **Lists:** 100 (clustering parameter, suitable for 10K-100K vectors)
- **Operator:** `vector_cosine_ops` (cosine distance metric)
- **Performance:** O(log N) approximate nearest neighbor lookup

**Actual Query** (from `vector_search_service.py`):
```sql
SELECT
    id, chunk_text, chunk_index, article_id,
    article_title, source_name,
    (1 - (embedding <=> :query_vector)) AS score
FROM article_chunks
ORDER BY embedding <=> :query_vector
LIMIT :top_k;  -- Default: 100
```

**Supported Distance Metrics** (configurable):
- `<=>` (Cosine distance) - **default** - good for normalized embeddings
- `<->` (L2/Euclidean) - good for sparse vectors
- `<#>` (Inner product) - negative scores, requires special handling

**Performance Characteristics**:
- Approximate (not exhaustive) - trades recall for speed
- Typical latency: 50-100ms for 1M+ vectors
- Accuracy: 95%+ for top-100 results

### BM25 Full-Text Search (Keyword Matching)

**Index Definition**:
```sql
CREATE INDEX ix_article_chunks_search_vector
ON article_chunks
USING GIN (search_vector);
```

**Index Details**:
- **Type:** GIN (Generalized Inverted Index)
- **Content:** TSVECTOR (PostgreSQL text search vectors)
- **Preprocessing:** Vietnamese word segmentation via `pyvi` library
- **Tokenization:** Underscore-joined compound words ("công_ty" stays together)
- **Ranking:** PostgreSQL `ts_rank_cd()` (cover density ranking, BM25-like)

**Actual Query** (from `bm25_search_service.py`):
```sql
SELECT
    id, chunk_text, chunk_index, article_id,
    article_title, source_name,
    ts_rank_cd(search_vector, query_tsv) AS score
FROM article_chunks
WHERE search_vector @@ query_tsv  -- @@ = matches operator
ORDER BY score DESC
LIMIT :top_k;  -- Default: 100
```

Where `query_tsv = to_tsquery('simple', :tokenized_query)` with tokenized_query like:
```
"công_ty & xây_dựng & mới"  -- AND logic (all words must match)
```

**Vietnamese Tokenization Process**:
1. **Input:** "công ty xây dựng mới"
2. **Tokenize** (pyvi): "công_ty xây_dựng mới"
3. **Sanitize:** Remove special chars, keep alphanumeric + underscore
4. **Format:** Join with `&` for AND logic
5. **Output:** `ts_query('simple', 'công_ty & xây_dựng & mới')`

**Performance Characteristics**:
- Exact keyword matching (100% recall on exact terms)
- Typical latency: 10-30ms for reasonable-sized result sets
- Good for handling Vietnamese compound words
- Note: Uses PostgreSQL 'simple' config (no stemming)

### Reciprocal Rank Fusion (Results Merging)

**Input**:
- N vector search result lists (from N queries)
- N BM25 search result lists (from N queries)
- Total: 2N lists of ~100 results each

**Algorithm** (from `fusion_service.py`):
```
RRF_score(chunk_id) = Σ 1 / (k + rank_in_list)
where k = 60 (default, configurable)
```

**Example Calculation**:
```
Chunk appears in:
  - Vector search 1: rank 5  → 1/(60+5) = 0.0145
  - BM25 search 1:   rank 2  → 1/(60+2) = 0.0159
  - Vector search 2: rank 15 → 1/(60+15) = 0.0123
  Total RRF score = 0.0427 (high score = good match across lists)
```

**Benefits**:
- Combines different search methods' strengths
- Rank-based (not score-based) - avoids normalization issues
- Boosts chunks appearing in multiple result lists
- Handles incomparable scores (vector scores vs BM25 scores)

## Database Migrations

**Tool:** Alembic with SQLAlchemy 2.0 async support

**Location**: `backend/alembic/versions/`

**Migration History**:

| ID | Timestamp | Description | Key Changes |
|----|-----------|----|---|
| `15cf52c90f29` | 2025-11-06 02:44 | `initial_setup_pgvector` | Install pgvector extension |
| `ed3b3babc76b` | 2025-11-06 07:17 | `add_core_models` | Create news_sources, rss_feeds, articles, article_chunks |
| `9df5c6353542` | 2025-11-06 09:00 | `add_content_field` | Add `content` column to articles (nullable) |
| `a929819b432a` | 2025-11-08 04:08 | `add_retrieval_pipeline` | Verification, retrieval_results, denorm fields, indexes |

**Current Status**: All migrations applied (HEAD: a929819b432a)

**Common Operations**:

```bash
# Apply all pending migrations
uv run alembic upgrade head

# Check current migration version
uv run alembic current

# Create new migration (auto-detects schema changes)
uv run alembic revision --autogenerate -m "description"

# Apply specific revision
uv run alembic upgrade <revision_id>
```

**Async Driver**: `asyncpg` (high-performance async PostgreSQL)
**Sync Driver** (migrations): `psycopg2` (standard driver for Alembic)

## Configuration & Access

### Connection Settings

**Environment Variables** (from `.env`):
```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=verinews_user
POSTGRES_PASSWORD=your_password
POSTGRES_DB=verinews_db
```

**Connection URLs**:
- **Async (Application):** `postgresql+asyncpg://user:password@host:5432/db`
- **Sync (Migrations):** `postgresql+psycopg2://user:password@host:5432/db`

### Connection Pool Configuration

**From `database.py`**:
```python
pool_size: 5              # Base connections
max_overflow: 10          # Additional connections
pool_pre_ping: True       # Verify connections (TCP probe)
echo: False               # SQL logging (set True for debug)
expire_on_commit: False   # Keep objects after commit
autocommit: False         # Explicit transaction management
```

**Total Capacity**: 5 + 10 = **15 concurrent connections** (suitable for 5-15 concurrent requests)

### Database Administration

**Adminer Web UI**: http://localhost:8080
- Server: postgres
- Username: verinews_user
- Password: verinews_password
- Database: verinews_db

**Direct Access**:
```bash
psql -h localhost -U verinews_user -d verinews_db
```

## Performance Characteristics

### Index Summary

| Index | Table | Type | Purpose | Performance |
|-------|-------|------|---------|------------|
| `ix_article_chunks_embedding_ivfflat` | article_chunks | IVFFlat | Vector search | O(log N) ~50-100ms |
| `ix_article_chunks_search_vector` | article_chunks | GIN | Full-text search | O(log N) ~10-30ms |
| `ix_verification_requests_text_hash` | verification_requests | B-tree | Cache lookup | O(log N) ~1ms |
| Foreign Key indexes | All tables | B-tree | FK lookups | O(log N) |
| Unique constraint indexes | All tables | B-tree | Unique validation | O(log N) |

### Storage Estimate (per 1M articles)

| Component | Size | Notes |
|-----------|------|-------|
| Article metadata | ~1 GB | Titles, URLs, metadata |
| Chunk text content | ~250 GB | 5 chunks/article × 50 bytes avg |
| Vector embeddings | ~6 GB | 5M chunks × 1536 dims × 4 bytes |
| TSVECTOR indexes | ~80 GB | GIN text search indexes |
| IVFFlat vector index | ~150 GB | Approximate nearest neighbor index |
| **Total** | **~487 GB** | With 3x replication = 1.5 TB |

### Query Latency Breakdown

| Operation | Time (ms) | Bottleneck |
|-----------|-----------|-----------|
| Vector search | 50-100 | IVFFlat index lookup |
| BM25 search | 10-30 | GIN index + ranking |
| Chunk aggregation | 20-50 | SQL joins + grouping |
| Cache lookup (Redis) | <5 | Network I/O |
| **Total retrieval** | **80-180** | Index performance |

## Data Retention & Lifecycle

**From `config.yaml`**:

```yaml
crawler:
  ingest_max_age_hours: 48      # Skip articles older than 48 hours
  retention_hours: 24            # Delete articles after 24 hours

cache:
  ttl_hours: 24                  # Redis cache TTL
```

**Article Lifecycle**:
1. **Crawl Window**: 48 hours (skip older articles)
2. **Storage**: 24 hours (aggressive retention)
3. **Deletion**: Hard delete after 24 hours (no archival)
4. **Cache**: Results cached 24 hours in Redis

**Implications**:
- ✅ Suitable for breaking news (30-second freshness)
- ⚠️ Aggressive (investigative pieces may expire)
- ⚠️ No archival (historical analysis not supported)

## Denormalization Strategy

### Why Denormalize?

**Problem**: Search returns 100+ chunks per query
- Each chunk needs: title, source_name, published_at
- Without denormalization: 200+ joins per query (Article + NewsSource)
- **Impact:** 5-10x slowdown

**Solution**: Denormalize 3 fields into `article_chunks`

### Fields Denormalized

| Field | Source | Updated | Sync |
|-------|--------|---------|------|
| `article_title` | `Article.title` | On chunk creation | Manual only |
| `source_name` | `NewsSource.name` | On chunk creation | Manual only |
| `published_at` | `Article.published_at` | On chunk creation | Manual only |

### Synchronization Gap ⚠️

**Current Implementation**:
- ✅ Populated during initial chunk creation (crawler)
- ❌ NO automatic sync if article is updated
- ❌ NO automatic sync if source name changes
- Celery task: `update_denormalized_fields_for_all_chunks` (one-time bulk fix)

**Potential Issue**: If articles are updated post-crawl, denormalized data becomes stale

**Mitigation**:
1. Articles rarely change after crawling (immutable news)
2. Source names change very rarely
3. Task can be run manually to resync all chunks

## Implementation Deviations & Notes

### Documented vs Actual

| Feature | Current Behavior | Considerations |
|---------|------------------|----------------|
| Data retention | Articles older than 24h are hard-deleted even though the crawler ingests up to 48h of history | Great for real-time use-cases, but historical analysis is impossible without an archival tier |
| Entity filtering | Chunk reranking runs with entity filtering enabled (60% coverage threshold) | Tune `retrieval.reranking.entity_filter` if recall becomes an issue |
| Denormalization sync | `article_title`, `source_name`, `published_at` in `article_chunks` are only populated at chunk creation | Run the Celery `update_denormalized_fields_for_all_chunks` task whenever upstream metadata changes |
| Connection pool | Async engine uses pool_size=5, max_overflow=10, pool_pre_ping=True | Monitor under heavy concurrency; scale horizontally or adjust pool sizes if saturation occurs |

### Undocumented Features

1. **Text Hash Caching**: SHA256 of original_text for exact-match cache lookup
2. **JSON Audit Trail**: Full stage_timings_json for performance debugging
3. **Cascade Deletes**: All tables use ON DELETE CASCADE (data integrity)
4. **Pool Pre-Ping**: TCP probe to verify connections before use
5. **Auto-Updated Timestamps**: All `updated_at` columns automatically updated

## Optimization Opportunities

### Short-term (< 1 month)

1. **Denormalization Sync Task**: Schedule periodic sync of denormalized fields
2. **Index Tuning**: Adjust IVFFlat lists parameter based on chunk count growth
3. **Connection Tuning**: Monitor connection pool utilization, adjust pool_size if needed

### Medium-term (1-3 months)

1. **Table Partitioning**: Partition `article_chunks` by `created_at` (monthly partitions)
2. **Read Replica**: Add read-only PostgreSQL replica for search queries
3. **Caching Layer**: Pre-compute and cache top-100 embeddings per topic

### Long-term (3+ months)

1. **Distributed Search**: Separate PostgreSQL node for chunks table
2. **Vector Index Sharding**: Distribute IVFFlat across multiple partitions
3. **Archival Tier**: Cold storage (S3) for articles older than 7 days
4. **Query Caching**: Cache full queries (not just results) for repeat patterns
