# Backend: Database

## Overview

The Database component serves as the persistent storage layer for VeriNews, storing trusted news articles, their vector embeddings, metadata, and verification history. It provides both traditional relational data access and specialized vector similarity search capabilities.

## Purpose

Provide reliable, efficient storage and retrieval for:
- Trusted news articles and their content
- Vector embeddings for semantic search
- News sources and RSS feed configurations
- Verification requests and results history
- User data and API keys (future)
- System configuration and metadata

## Technology Stack

### PostgreSQL 18
- **Why**: Industry-standard relational database
- **Strengths**: ACID compliance, rich query capabilities, mature ecosystem
- **Version**: 18 (latest stable)

### pgvector Extension
- **Why**: Enable vector similarity search within PostgreSQL
- **Capabilities**: Store and query high-dimensional vectors
- **Performance**: Approximate nearest neighbor search with IVFFlat index
- **Integration**: Native SQL queries for vector operations

### Full-Text Search (Built-in)
- **Why**: PostgreSQL native FTS is powerful and well-integrated
- **Capabilities**: BM25-like ranking, multiple languages, custom dictionaries
- **Performance**: GIN indexes for fast text search

## Key Responsibilities

1. **Data Persistence**
   - Store articles, chunks, and embeddings
   - Maintain referential integrity
   - Handle concurrent writes safely
   - Ensure data durability (WAL, replication)

2. **Vector Search**
   - Fast approximate nearest neighbor (ANN) search
   - Cosine similarity calculations
   - Index management for performance
   - Support for 1536-dimensional vectors

3. **Full-Text Search**
   - Index article text for keyword search
   - Support Vietnamese and English languages
   - Rank results by relevance (BM25)
   - Handle stemming and stopwords

4. **Relational Queries**
   - Complex joins across tables
   - Aggregations and analytics
   - Transaction support
   - Foreign key enforcement

5. **Performance Optimization**
   - Query optimization and indexing
   - Connection pooling
   - Query result caching
   - Partition large tables (future)

## Data Models

### Core Entities

#### NewsSource
**Purpose**: Represent trusted news organizations

**Fields**:
- `id`: UUID primary key
- `name`: News source name (e.g., "BBC News")
- `url`: Homepage URL
- `credibility_rating`: Enum (high, medium, low)
- `country`: ISO country code
- `language`: Primary language (vi, en, etc.)
- `is_active`: Boolean (for disabling sources)
- `created_at`: Timestamp
- `updated_at`: Timestamp

**Relationships**:
- One-to-many with RssFeed
- One-to-many with Article

**Indexes**:
- Primary key on `id`
- Index on `is_active` (for filtering)
- Unique constraint on `name`

#### RssFeed
**Purpose**: RSS feed configurations for news sources

**Fields**:
- `id`: UUID primary key
- `news_source_id`: UUID foreign key → NewsSource
- `url`: RSS feed URL
- `topic`: Category (politics, tech, sports, etc.)
- `fetch_frequency_minutes`: How often to crawl
- `is_active`: Boolean
- `last_fetched_at`: Timestamp
- `last_success_at`: Timestamp
- `error_count`: Integer (consecutive failures)
- `created_at`: Timestamp
- `updated_at`: Timestamp

**Relationships**:
- Many-to-one with NewsSource
- One-to-many with Article

**Indexes**:
- Primary key on `id`
- Foreign key index on `news_source_id`
- Index on `is_active`
- Index on `last_fetched_at` (for scheduling)

#### Article
**Purpose**: Trusted news articles

**Fields**:
- `id`: UUID primary key
- `news_source_id`: UUID foreign key → NewsSource
- `rss_feed_id`: UUID foreign key → RssFeed (nullable)
- `title`: Text
- `url`: Text (unique)
- `author`: Text (nullable)
- `published_at`: Timestamp
- `content`: Text (full article text)
- `summary`: Text (nullable, excerpt)
- `language`: Language code
- `word_count`: Integer
- `indexed_at`: Timestamp (when chunks/embeddings created)
- `created_at`: Timestamp
- `updated_at`: Timestamp

**Relationships**:
- Many-to-one with NewsSource
- Many-to-one with RssFeed
- One-to-many with ArticleChunk

**Indexes**:
- Primary key on `id`
- Unique index on `url`
- Foreign key indexes on `news_source_id`, `rss_feed_id`
- Index on `published_at` (for recency sorting)
- Full-text search index on `content` (GIN)

#### ArticleChunk
**Purpose**: Text chunks with embeddings for retrieval

**Fields**:
- `id`: UUID primary key
- `article_id`: UUID foreign key → Article
- `chunk_index`: Integer (order within article)
- `text`: Text (500-2000 characters)
- `word_count`: Integer
- `embedding`: VECTOR(1536) (pgvector type)
- `search_vector`: tsvector (full-text search)
- `created_at`: Timestamp

**Relationships**:
- Many-to-one with Article

**Indexes**:
- Primary key on `id`
- Foreign key index on `article_id`
- Index on `chunk_index` (for ordering)
- **IVFFlat index** on `embedding` (for vector search)
- **GIN index** on `search_vector` (for text search)

**Special Considerations**:
- Chunks are immutable (never updated, only recreated)
- IVFFlat index parameters:
  - `lists`: 100-1000 (depends on data size)
  - `probes`: 10-20 (query-time parameter)

#### VerificationRequest
**Purpose**: Track verification requests and results

**Fields**:
- `id`: UUID primary key
- `post_text`: Text
- `post_images`: JSONB (array of URLs)
- `post_metadata`: JSONB (platform, author, etc.)
- `status`: Enum (pending, completed, failed)
- `verdict`: Enum (verified, likely_verified, unverified, likely_false, false)
- `credibility_score`: Float (0-100)
- `explanation`: Text
- `evidence`: JSONB (matched articles, claims, etc.)
- `processing_time_ms`: Integer
- `cached`: Boolean
- `api_key_id`: UUID (nullable, for tracking usage)
- `created_at`: Timestamp
- `completed_at`: Timestamp

**Relationships**:
- One-to-many with RetrievalResult

**Indexes**:
- Primary key on `id`
- Index on `created_at` (for history queries)
- Index on `api_key_id` (for usage tracking)
- GIN index on `evidence` (for JSON queries)

#### RetrievalResult
**Purpose**: Store retrieved articles for each verification request

**Fields**:
- `id`: UUID primary key
- `verification_request_id`: UUID foreign key → VerificationRequest
- `article_id`: UUID foreign key → Article
- `relevance_score`: Float (0-1)
- `rank`: Integer (1, 2, 3, ...)
- `matching_chunks`: JSONB (array of chunk data)
- `created_at`: Timestamp

**Relationships**:
- Many-to-one with VerificationRequest
- Many-to-one with Article

**Indexes**:
- Primary key on `id`
- Foreign key indexes on `verification_request_id`, `article_id`
- Composite index on `(verification_request_id, rank)`

## Vector Search Implementation

### pgvector Setup

**Extension Installation**:
```sql
CREATE EXTENSION vector;
```

**Vector Column**:
```sql
ALTER TABLE article_chunk
ADD COLUMN embedding VECTOR(1536);
```

**IVFFlat Index Creation**:
```sql
-- Create index for approximate nearest neighbor search
CREATE INDEX article_chunk_embedding_idx
ON article_chunk
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- "lists" parameter:
-- - More lists = faster search, less accurate
-- - Fewer lists = slower search, more accurate
-- - Rule of thumb: sqrt(total_rows) or rows/1000
```

### Vector Search Queries

**Cosine Similarity Search**:
```sql
-- Find top 50 most similar chunks
SELECT
    id,
    article_id,
    text,
    1 - (embedding <=> :query_vector) AS similarity_score
FROM article_chunk
WHERE 1 - (embedding <=> :query_vector) > 0.5  -- Minimum similarity threshold
ORDER BY embedding <=> :query_vector  -- <=> is cosine distance operator
LIMIT 50;
```

**Query-Time Parameters**:
```sql
-- Adjust probes for accuracy/speed tradeoff
SET ivfflat.probes = 10;  -- Check 10 nearest lists
-- More probes = more accurate, slower
-- Fewer probes = less accurate, faster
```

### Performance Characteristics

**Index Build Time**:
- 100K chunks: ~2-5 minutes
- 1M chunks: ~20-30 minutes
- 10M chunks: ~3-4 hours

**Query Latency** (with proper index):
- 100K chunks: ~10-30ms
- 1M chunks: ~30-50ms
- 10M chunks: ~50-100ms

**Accuracy**:
- IVFFlat typically achieves 95-98% recall@50
- Trade accuracy for speed by adjusting probes parameter

## Full-Text Search Implementation

### Vietnamese Text Search

**Custom Configuration**:
```sql
-- Create Vietnamese text search configuration
CREATE TEXT SEARCH CONFIGURATION vietnamese (COPY = simple);

-- Customize tokenization for Vietnamese compound words
-- (Handled by application-level preprocessing)
```

**Search Vector Column**:
```sql
ALTER TABLE article_chunk
ADD COLUMN search_vector tsvector;

-- Populate search vector
UPDATE article_chunk
SET search_vector = to_tsvector('vietnamese', text);

-- Create GIN index
CREATE INDEX article_chunk_search_vector_idx
ON article_chunk
USING GIN (search_vector);
```

### BM25 Search Queries

**Basic Text Search**:
```sql
-- Find matching chunks with BM25-like ranking
SELECT
    id,
    article_id,
    text,
    ts_rank_cd(search_vector, query) AS relevance_score
FROM article_chunk,
     to_tsquery('vietnamese', :query_string) query
WHERE search_vector @@ query
ORDER BY ts_rank_cd(search_vector, query) DESC
LIMIT 50;
```

**Advanced Ranking** (ts_rank_cd):
- Considers term frequency (more matches = higher score)
- Considers document length (normalizes scores)
- Considers term proximity (close matches score higher)
- Adjustable with weights parameter

## Database Scaling

### Vertical Scaling
**Initial Setup** (1M articles):
- CPU: 4 cores
- RAM: 8GB
- Storage: 100GB SSD

**Medium Scale** (10M articles):
- CPU: 8 cores
- RAM: 32GB
- Storage: 500GB SSD

**Large Scale** (100M articles):
- CPU: 16+ cores
- RAM: 64GB+
- Storage: 2TB+ SSD

### Horizontal Scaling

**Read Replicas**:
- Offload read-heavy operations (search queries)
- Async replication from primary
- Route search traffic to replicas
- Keep write traffic on primary

**Partitioning** (future):
- Partition articles by date (monthly or yearly)
- Partition chunks by article (hash partitioning)
- Query planner automatically routes to relevant partitions

**Sharding** (future, if needed):
- Shard by news source region
- Shard by language
- Application-level routing

## Connection Management

### Connection Pooling

**AsyncPG Pool** (for Python async):
- Min connections: 10
- Max connections: 100
- Idle timeout: 300s
- Connection lifetime: 3600s

**Benefits**:
- Reuse connections (avoid connection overhead)
- Limit concurrent connections
- Handle connection failures gracefully

**Configuration**:
```
Pool Size = (CPU cores * 2) + effective_spindle_count
For SSD: Pool Size = CPU cores * 4
```

## Backup & Recovery

### Backup Strategy

**Continuous Archiving (WAL)**:
- Write-Ahead Log (WAL) streaming
- Point-in-time recovery capability
- Backup to S3 or similar object storage

**Full Backups**:
- Daily full backup using pg_dump
- Retain for 30 days
- Compress and encrypt backups

**Incremental Backups**:
- WAL archiving every 5 minutes
- Enables recovery to any point in last 30 days

### Disaster Recovery

**RTO** (Recovery Time Objective): 15 minutes
**RPO** (Recovery Point Objective): 5 minutes (WAL interval)

**Recovery Steps**:
1. Provision new database instance
2. Restore latest full backup
3. Apply WAL logs up to desired point
4. Verify data integrity
5. Update application connection strings

## Monitoring

### Key Metrics

**Performance**:
- Query response time (p50, p95, p99)
- Queries per second (QPS)
- Cache hit rate
- Connection pool usage

**Health**:
- Database uptime
- Replication lag (if using replicas)
- Disk usage (% full)
- WAL size and growth rate

**Indexes**:
- Index size
- Index usage statistics
- Unused indexes (candidates for removal)
- Index build/rebuild time

### Alerts

- Slow queries (> 1 second)
- High connection count (> 80% of max)
- Disk usage (> 85% full)
- Replication lag (> 10 seconds)
- Failed backups

## Maintenance

### Regular Tasks

**Daily**:
- Monitor slow query log
- Check backup completion
- Review error logs

**Weekly**:
- Analyze table statistics (ANALYZE)
- Review index usage
- Check for table bloat

**Monthly**:
- Vacuum full on large tables (if bloated)
- Rebuild indexes (if fragmented)
- Review and archive old verification requests

**Quarterly**:
- Review and optimize slow queries
- Evaluate partitioning needs
- Assess scaling requirements

## Security

### Access Control

**Roles**:
- `verinews_app`: Application user (read/write on all tables)
- `verinews_readonly`: Read-only user (for analytics)
- `verinews_admin`: DBA user (full access)

**Permissions**:
- Principle of least privilege
- Application uses only `verinews_app` role
- No superuser access for application

### Encryption

**At Rest**:
- Disk encryption (LUKS or cloud provider encryption)
- Backup encryption (GPG or S3 encryption)

**In Transit**:
- SSL/TLS for all connections
- Certificate verification enforced

**Sensitive Data**:
- API keys hashed with bcrypt
- User passwords (future) hashed with Argon2
- PII redacted in logs

## Future Enhancements

1. **Partitioning**
   - Time-based partitioning for articles (monthly)
   - Automatic partition creation and archival
   - Improved query performance on large tables

2. **Multi-Tenant Support**
   - Separate schemas per customer (enterprise)
   - Row-level security (RLS) policies
   - Isolated backups per tenant

3. **Advanced Analytics**
   - Materialized views for dashboards
   - Pre-aggregated statistics
   - Time-series data for trends

4. **Distributed Database**
   - Consider Citus for PostgreSQL sharding
   - Or migrate to distributed database (CockroachDB, YugabyteDB)
   - For extreme scale (> 100M articles)
