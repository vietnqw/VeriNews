# Backend: Cache Layer

## What It Is

The cache layer stores verification results in Redis so repeated queries return instantly without reprocessing.

## Technology: Redis

**Why Redis**:
- In-memory storage (very fast: < 1ms access)
- Simple key-value store
- Automatic expiration (TTL)
- Also used as Celery message broker

**Deployment**:
- Development: Single Redis instance
- Docker: Runs in container alongside PostgreSQL

## What's Cached

### Retrieval Results

**What**: Complete article retrieval results

**Key format**: `SHA256(post_text)`

**Value**: JSON containing:
- List of matched articles
- Relevance scores
- Stage timing information
- Query count

**TTL**: 1 hour (3600 seconds)

**Why cache**:
- Retrieval takes ~1 second
- Cached results return in < 10ms
- Saves AI API costs (no re-embedding, re-reranking)
- Reduces database load

## How It Works

**On verification request**:
1. Generate hash of post text
2. Check Redis for cached result
3. If found: Return immediately with `cache_hit: true`
4. If not found: Run full retrieval pipeline
5. Store result in Redis with 1-hour TTL
6. Return result with `cache_hit: false`

**Implementation**: `RetrievalCache` service class

## Cache Strategy

**Pattern**: Cache-Aside (Lazy Loading)
- Application checks cache first
- On miss, fetches from source (runs pipeline)
- Stores result in cache for next time

**Benefits**:
- Only cache what's actually requested
- Simple to implement
- Resilient (if Redis down, still works, just slower)

**Expiration**: Time-based (TTL)
- Results expire after 1 hour
- News changes frequently, so don't cache too long
- Redis automatically removes expired keys

## Implementation Details

**Redis Client**: Using `redis-py` with async support

**Connection**: Connection pooling configured

**Error Handling**:
- If Redis unavailable, skips caching (degrades gracefully)
- Logs errors but doesn't fail the request

## Configuration

**Redis connection** (in `.env`):
- `REDIS_URL`: Connection string (default: redis://localhost:6379/0)

**Cache settings** (in `config/config.yaml`):
- Cache enabled/disabled toggle
- TTL duration
- Clear cache command available

## Performance Impact

**Without cache**:
- Every query: ~1 second
- Cost: $0.025 per verification

**With cache (80% hit rate)**:
- Cached queries: ~10ms
- Uncached queries: ~1 second
- Average cost: ~$0.005 per verification

## What's NOT Implemented

- Embedding caching (queries → embeddings)
- Query extraction caching (posts → clean queries)
- Article metadata caching
- Multi-level caching (application + Redis)
- Redis Sentinel (high availability)
- Redis Cluster (horizontal scaling)
