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
- Development: Single Redis instance (Docker service `verinews-redis`)
- Docker Compose: `redis:7-alpine`, persistent `redis_data` volume, health check enabled

## What's Cached

### Retrieval Results (Partial)

**What**: Subset of article retrieval results

**Key format**: `retrieval:{SHA256(post_text)}`
*(Prefix "retrieval:" is configurable)*

**Value** (current implementation):
- `articles`: Article list (denormalized chunks) from retrieval pipeline
- `total_time_ms`: Retrieval pipeline wall clock time
- `stage_timings`: Per-stage timings captured before verification
- `query_count`: Number of LLM-generated queries processed

**NOT Cached** (recomputed every request):
- Extracted claims from post
- Factual confidence score (1‑3) from query extraction
- Retrieval confidence score (0‑1) and confidence metrics
- Early exit flags (`LOW_CONFIDENCE`, `NO_RELEVANT_ARTICLES`) and user messages
- **Verification results** (stance classifications, verdict aggregation, explanation)

**TTL**: 24 hours (configurable)

**Why cache the retrieval only**:
- Retrieval pipeline takes ~1-2 seconds
- Cached articles return in < 10ms
- Saves AI API costs for embedding and reranking
- Reduces database load

**Why NOT cache verification**:
- Verification pipeline re-runs on every request (even on cache hits)
- Missing verification result caching means verification is always recomputed
- This limits cache performance benefits for the full pipeline

## How It Works

**On verification request**:
1. Generate SHA256 hash of post text
2. Check Redis for cached result using key `{prefix}{hash}`
3. If found:
   - Return cached articles immediately
   - **BUT** re-run verification pipeline (NLI-based verdict, evidence, explanation)
   - Return combined result with `cache_hit: true`
4. If not found:
   - Run full retrieval pipeline (query extraction, embedding, search, reranking)
   - Run verification pipeline (stance classification, verdict aggregation, explanation generation)
   - Store retrieval results (articles + timings) in Redis with 24-hour TTL
   - Return result with `cache_hit: false`

**Implementation**: `RetrievalCache` service class (`backend/app/services/cache/retrieval_cache.py`)

**Actual Behavior on Cache Hit**:
- Reuses retrieval artifacts from Redis (saves ~700-1,000 ms)
- Still re-runs verification pipeline (stance classification, verdict aggregation, explanation → ~1,000-2,000 ms)
- Response includes all verification fields, but any columns not cached (confidence metrics, factual/retrieval confidence, exit_reason, message) remain `None` unless recomputed

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
- Results expire after 24 hours (default)
- News changes frequently, but 24h allows catching viral repeats
- Redis automatically removes expired keys

## Implementation Details

### Redis Client
- Library: `redis.asyncio` (async Python Redis client)
- Connection URL: `redis://localhost:6379` (hardcoded defaults)
- Initialization: Lazy (created on first cache access, not at startup)
- Encoding: UTF-8 with `decode_responses=True` (returns strings, not bytes)

### Connection Configuration
**Current Settings**:
- Host: `REDIS_HOST` env var (default `localhost`)
- Port: `REDIS_PORT` env var (default `6379`)
- Database: `0` (hardcoded)
- Connection Pool: Redis client defaults (no explicit max/min tuning)
- Timeouts: Not set explicitly (inherit client defaults)
- Authentication/SSL: Not supported yet (assumes local, unauthenticated Redis)

**For Production**:
- Redis connection should be configurable via environment variables
- Connection pooling should be explicitly configured
- Health checks should be enabled
- Timeout values should be set for reliability

### Error Handling
**On Cache Miss/Error**:
- All Redis operations wrapped in try-except blocks
- Catches all exceptions (generic `Exception`)
- Logs error message with logger.error()
- Returns None/empty result (graceful fallback)
- API continues normally, doesn't fail the request

**Behavior**:
- Redis unavailable: Falls back to full pipeline re-run (slower but functional)
- Connection timeout: Results in full re-run
- Data corruption: Returns None, triggers full re-run
- Cache write failure: Silent failure (data not cached, but result still returned)

**Resilience**: ✅ API won't crash if Redis is down
**Limitations**: ❌ No retry policy, ❌ No connection monitoring, ❌ No health checks

## Configuration

### Redis Connection (in settings.py)
**Environment Variables**:
- `REDIS_HOST`: Redis server hostname (default: `localhost`)
- `REDIS_PORT`: Redis server port (default: `6379`)
- Database: Always uses database `0` (hardcoded, not configurable)

**Note**: `.env.example` does NOT document `REDIS_HOST` and `REDIS_PORT`, so defaults apply unless explicitly set

**Not Configurable**:
- Connection timeout
- Pool size / max connections
- Connection retry policy
- SSL/TLS for Redis connection
- Redis authentication (password)
- Health check interval

### Cache Settings (in config/config.yaml)
```yaml
cache:
  enabled: true              # Enable/disable caching
  ttl_hours: 24              # Cache expiration (default: 24 hours)
  redis_key_prefix: retrieval:  # Cache key prefix
```

**In Python** (app/config/settings.py lines 191-201):
```python
class CacheSettings(BaseSettings):
    enabled: bool = True
    ttl_hours: int = 24
    redis_key_prefix: str = "retrieval:"

    @property
    def ttl_seconds(self) -> int:
        return self.ttl_hours * 3600
```

## Performance Impact

### Response Times

**Without cache (Retrieval pipeline only)**:
- Typical query: 2,500-4,500ms
- Cost: ~$0.015-0.027 per verification (embedding + reranking)

**With cache hit (Articles reused)**:
- Retrieval lookup: ~10-50ms (cache get)
- Verification pipeline (re-run): ~1,000-2,000ms (stance classification, verdict aggregation)
- **Total: ~1,010-2,050ms** (saves ~1,500-2,500ms from retrieval)
- Cost: Still ~$0.01-0.02 per verification (stance classification still runs)

**Viral post scenario** (same article content, repeated verification):
- Cache savings: ~1,500-2,500ms per request
- Cost savings: Minimal (verification still costs ~$0.01)
- Effective only for retrieval-only scenarios (when articles don't change)

### Cost Analysis

**Cost per Verification**:
- Embedding generation (OpenAI): ~$0.0001-0.0002
- Chunk reranking (LLM): ~$0.005-0.01
- Article reranking (LLM): ~$0.002-0.004
- Stance classification (LLM): ~0.01-0.02
- Explanation generation (LLM): ~$0.001-0.003
- **Total (no cache): ~$0.019-0.039 per verification**

**With Cache Hit** (articles from cache):
- Embedding generation: **SAVED** (~$0.0001-0.0002)
- Reranking: **SAVED** (~$0.007-0.014)
- Stance classification: **STILL RUNS** (~$0.01-0.02)
- Explanation generation: **STILL RUNS** (~$0.001-0.003)
- **Total (cache hit): ~$0.011-0.023 per verification** (saves ~$0.008-0.016)

**Current Limitation**:
- Verification results are NOT cached, so stance classification and explanation generation always re-run
- To achieve full cache benefits, verification results should also be cached

## What's NOT Implemented

### Critical Gaps
- **Verification result caching** - NLI-based verdicts, evidence, explanations re-computed on every request (even on cache hit)
- **Confidence metric caching** - Factual confidence, retrieval confidence, and multi-signal confidence metrics not cached
- **Claim extraction caching** - Extracted claims from post not cached

### Performance Optimizations Not Yet Done
- **Query embedding caching** - OpenAI embeddings for extracted queries could be cached separately
- **Title similarity caching** - Title embeddings re-generated for every verification
- **Adaptive cache invalidation** - Currently uses fixed 24-hour TTL regardless of article update frequency

### Production Features Not Implemented
- **Redis health monitoring** - No health check in /health endpoint for Redis connectivity
- **Connection pooling configuration** - Redis client uses library defaults, not explicit pool settings
- **Connection timeout settings** - No configurable timeout for Redis operations
- **Authentication/SSL** - No support for Redis password or SSL/TLS connections
- **Redis Sentinel** - High availability not configured
- **Redis Cluster** - Horizontal scaling not configured
- **Cache statistics/metrics** - No tracking of cache hit rate, memory usage, or performance metrics
- **Graceful degradation monitoring** - When Redis unavailable, users aren't notified (silent fallback)

### Partial Implementations
- **Cache bypass**: Client can request `cache_bypass=true` to skip cache, but no automatic invalidation mechanism
- **Cache clear utility**: `RetrievalCache.clear_all()` helper exists (used in unit tests/CLI), not exposed via API endpoints

## Implementation Status & Deviations

### Key Discrepancies Between Documentation and Implementation

| Aspect | Current Behavior | Impact |
|--------|------------------|--------|
| Cached payload | Stores `articles`, `total_time_ms`, `stage_timings`, `query_count` (no claims/confidence metrics/verification result) | Cache hits provide fast article reuse, but verification data must be recomputed |
| Cache hit flow | Retrieval skipped, verification always re-run | Saves ~1.5‑2.5 s per request, but still pays verification latency + LLM costs |
| Redis connection | `redis.asyncio.from_url()` with host/port env vars, no explicit pool/timeout tuning | Works locally; production deployments should add auth/SSL/timeouts/pool sizing |
| Health monitoring | Redis not included in `/health` checks | Outages are silent; operators rely on logs to detect cache failures |
| Configuration exposure | `REDIS_HOST`/`REDIS_PORT` documented; Redis DB index, password, TLS not configurable yet | Fine for dev, needs enhancement before hosting managed Redis |

### Positive Implementations Matching Docs
- ✅ Lazy Redis client initialization (only created on first use)
- ✅ 24-hour TTL configuration with Python property conversion
- ✅ Cache-Aside pattern correctly implemented
- ✅ SHA256 deterministic key generation for exact-match caching
- ✅ Graceful degradation when Redis unavailable
- ✅ Excellent test coverage (24 unit tests)
- ✅ Unicode/Vietnamese character support
- ✅ Cache bypass parameter available to clients

### Critical Issues Requiring Attention
1. **Data Loss on Cache Hit** - Confidence metrics and claims are not returned when cache is hit
   - File: `backend/app/api/verification.py` lines 89-94
   - Impact: Client receives incomplete response
   - Recommendation: Cache all fields or recalculate on hit

2. **Verification Re-computation on Cache Hit** - Stance classification, verdict aggregation, and explanation generation are always re-run
   - File: `backend/app/api/verification.py` lines 65-73
   - Impact: Cache doesn't improve end-to-end response time significantly
   - Recommendation: Add verification result caching

3. **Missing Production Configuration** - REDIS_HOST, REDIS_PORT, timeouts not configurable via .env
   - File: `backend/app/config/settings.py` lines 333-334
   - Impact: Difficult to deploy to non-localhost Redis instances
   - Recommendation: Add proper environment variables with documentation

4. **No Health Monitoring** - Redis availability not checked in health endpoint
   - File: `backend/app/api/health.py`
   - Impact: Operators can't detect Redis failures
   - Recommendation: Add Redis connectivity check
