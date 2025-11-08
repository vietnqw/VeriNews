# Backend: Cache Layer

## Overview

The Cache Layer provides high-speed in-memory storage for frequently accessed data, reducing database load and improving response times. It serves as the first line of data retrieval, handling the majority of read requests without touching the database.

## Purpose

Optimize system performance by:
- Caching verification results for repeated queries
- Storing frequently accessed article data
- Caching embeddings for common queries
- Reducing AI API calls through result caching
- Decreasing database load and query latency
- Improving overall system throughput

## Technology: Redis

### Why Redis?
- **Speed**: In-memory storage (sub-millisecond latency)
- **Data Structures**: Supports strings, hashes, lists, sets, sorted sets
- **Persistence**: Optional disk persistence for durability
- **Scalability**: Supports clustering and replication
- **Pub/Sub**: Real-time messaging capabilities
- **TTL**: Automatic expiration of cached data
- **Atomic Operations**: Thread-safe operations

### Redis Version
- Version: 7.x
- Deployment: Single instance (dev), Redis Cluster (production)

## Key Responsibilities

1. **Result Caching**
   - Cache verification results by post hash
   - Cache search results by query hash
   - Cache article metadata
   - Invalidate on data updates

2. **Session Management** (Future)
   - Store user sessions
   - Manage JWT tokens
   - Track active connections

3. **Rate Limiting**
   - Track API request counts per key
   - Implement sliding window counters
   - Enforce quotas and throttling

4. **Task Queue** (Celery)
   - Message broker for background tasks
   - Task result storage
   - Queue management

5. **Temporary Storage**
   - Store intermediate processing results
   - Cache expensive computation results
   - Temporary file references

## Caching Strategies

### 1. Verification Result Caching

**Purpose**: Avoid re-verifying identical or similar posts

**Key Generation**:
```
cache_key = "verification:" + SHA256(post_text + post_images)
```

**Value Structure** (JSON):
```json
{
  "verdict": "verified",
  "credibility_score": 85,
  "explanation": "Supported by 3 trusted sources...",
  "evidence": {
    "matched_articles": [...],
    "claims": [...]
  },
  "cached_at": "2024-01-15T10:30:00Z",
  "processing_time_ms": 1250
}
```

**TTL**: 1 hour (3600 seconds)
- Reason: News changes rapidly, verification may become outdated

**Cache Hit Handling**:
1. Check cache for key
2. If hit: Return cached result with `cached: true` flag
3. If miss: Process verification, store result in cache

**Benefits**:
- Instant response for duplicate posts (< 10ms vs. 2000ms)
- Reduce AI API costs (no re-embedding, re-reranking)
- Lower database query load

**Invalidation**:
- Automatic via TTL (1 hour)
- Manual invalidation if article database updated
- User-triggered refresh (optional)

### 2. Retrieval Result Caching

**Purpose**: Cache search results for common queries

**Key Generation**:
```
cache_key = "retrieval:" + SHA256(clean_query + claims)
```

**Value Structure**:
```json
{
  "articles": [
    {
      "article_id": "uuid",
      "title": "...",
      "relevance_score": 0.92,
      "matching_chunks": [...]
    }
  ],
  "processing_stages": {
    "total": "935ms"
  }
}
```

**TTL**: 30 minutes (1800 seconds)

**Benefits**:
- Faster retrieval for similar queries
- Reduced database vector/text search load
- Lower AI API usage (no re-reranking)

### 3. Embedding Caching

**Purpose**: Cache embeddings for frequently searched queries

**Key Generation**:
```
cache_key = "embedding:" + SHA256(query_text)
```

**Value**: Base64-encoded embedding vector (1536 floats)

**TTL**: 24 hours (86400 seconds)
- Embeddings are deterministic and stable

**Benefits**:
- Avoid OpenAI API calls for repeated queries
- Significant cost savings ($0.02 per 1M tokens)
- Faster embedding generation (< 1ms vs. 100ms)

### 4. Query Extraction Caching

**Purpose**: Cache extracted queries and claims from posts

**Key Generation**:
```
cache_key = "query_extraction:" + SHA256(post_text)
```

**Value**:
```json
{
  "clean_query": "President announces climate policy",
  "claims": [
    "President announced climate policy",
    "Policy targets emissions reduction"
  ]
}
```

**TTL**: 1 hour (3600 seconds)

**Benefits**:
- Avoid LLM calls for repeated posts
- Cost savings on GPT-4 API usage
- Faster query extraction (< 1ms vs. 500ms)

### 5. Article Metadata Caching

**Purpose**: Cache frequently accessed article information

**Key Generation**:
```
cache_key = "article:" + article_id
```

**Value**:
```json
{
  "id": "uuid",
  "title": "...",
  "source": "BBC News",
  "published_at": "2024-01-15",
  "url": "https://..."
}
```

**TTL**: 6 hours (21600 seconds)

**Benefits**:
- Reduce database queries for article metadata
- Faster result enrichment
- Lower database connection usage

## Cache Patterns

### Cache-Aside (Lazy Loading)

**Most Common Pattern**

**Flow**:
1. Application requests data
2. Check cache first
3. If **cache hit**: Return cached data
4. If **cache miss**:
   - Query database
   - Store result in cache
   - Return data to application

**Pros**:
- Only cache data that's actually requested
- Resilient to cache failures (fallback to DB)
- Simple to implement

**Cons**:
- Initial request always slower (cold cache)
- Potential cache stampede on expiration

**Implementation**:
```python
def get_verification_result(post_hash):
    # Check cache
    cached = redis.get(f"verification:{post_hash}")
    if cached:
        return json.loads(cached)

    # Cache miss - compute result
    result = perform_verification(post_hash)

    # Store in cache
    redis.setex(
        f"verification:{post_hash}",
        3600,  # TTL: 1 hour
        json.dumps(result)
    )

    return result
```

### Write-Through Cache

**Used for Critical Data**

**Flow**:
1. Application writes data
2. Write to cache and database simultaneously
3. Ensure consistency between cache and DB

**Pros**:
- Cache always has latest data
- No cache misses on reads after writes

**Cons**:
- Slower writes (dual write)
- More complex error handling

**Use Case**: User settings, API keys (future)

### Cache Warming

**Proactive Caching**

**Strategy**:
- Pre-populate cache with popular content
- Run during off-peak hours
- Update periodically

**Example**:
- Cache top 100 news articles daily
- Pre-generate embeddings for trending topics
- Warm up query extraction for common post formats

## Cache Invalidation

### Challenges
"There are only two hard things in Computer Science: cache invalidation and naming things." - Phil Karlton

### Strategies

**TTL-Based Expiration** (Primary):
- Set expiration time when storing data
- Redis automatically removes expired keys
- Simple and reliable

**Event-Based Invalidation**:
- Invalidate cache when underlying data changes
- Example: Article updated → Invalidate article cache
- Requires event tracking

**Manual Invalidation**:
- Admin endpoint to clear specific cache keys
- Useful for debugging or urgent updates
- Pattern-based deletion: `DEL verification:*`

**LRU Eviction** (When memory full):
- Redis evicts least recently used keys
- Configure maxmemory-policy: allkeys-lru

### Invalidation Implementation

**Single Key**:
```python
redis.delete(f"verification:{post_hash}")
```

**Pattern Deletion** (Use sparingly - expensive):
```python
# Find keys matching pattern
keys = redis.keys("verification:*")
# Delete in batches
for i in range(0, len(keys), 1000):
    batch = keys[i:i+1000]
    redis.delete(*batch)
```

**Versioned Keys** (Better approach):
```
cache_key = f"verification:v2:{post_hash}"
# When schema changes, increment version
# Old v1 keys expire naturally via TTL
```

## Performance Optimization

### Key Design Best Practices

1. **Use Prefixes**: Organize keys by type
   - `verification:*`, `retrieval:*`, `embedding:*`

2. **Keep Keys Short**: Save memory
   - `art:123` instead of `article:123`

3. **Use Hashes for Related Data**: More memory-efficient
   - Instead of `article:123:title`, `article:123:url`
   - Use single hash: `article:123` with fields `title`, `url`

4. **Avoid Large Values**: Break up if needed
   - Keep values < 100KB
   - Use compression for large data

### Memory Management

**Redis Memory Settings**:
```
maxmemory 2gb                    # Maximum memory limit
maxmemory-policy allkeys-lru     # Evict least recently used
```

**Memory Usage Estimation**:
- Verification result: ~5KB per entry
- Embedding: ~6KB (1536 floats)
- Query extraction: ~500 bytes
- Total for 100K cached verifications: ~500MB

**Monitoring**:
```
INFO memory                      # Check memory usage
MEMORY USAGE verification:abc    # Check size of specific key
```

### Connection Pooling

**Redis Client Pool**:
- Min connections: 5
- Max connections: 50
- Connection timeout: 5s
- Retry on failure: 3 attempts

**Benefits**:
- Reuse connections (avoid handshake overhead)
- Limit resource usage
- Handle transient failures

## High Availability

### Redis Sentinel (Production)

**Purpose**: Automatic failover and monitoring

**Components**:
- 1 Master (read/write)
- 2+ Replicas (read-only)
- 3+ Sentinels (monitoring)

**Failover Process**:
1. Sentinels detect master failure
2. Vote on new master (quorum)
3. Promote replica to master
4. Update clients with new master address

**Benefits**:
- High availability (automatic recovery)
- Read scalability (read from replicas)
- Minimal downtime (< 30 seconds)

### Redis Cluster (Future)

**For Extreme Scale**:
- Horizontal partitioning (sharding)
- 1000+ nodes supported
- Automatic resharding

**When Needed**:
- Cache size > 100GB
- Request rate > 100K ops/sec
- Need for geographic distribution

## Persistence Options

### RDB (Snapshotting)
- Save full dataset at intervals
- Compact binary format
- Fast restart
- Risk of data loss (up to snapshot interval)

**Configuration**:
```
save 900 1      # Save after 900s if 1 key changed
save 300 10     # Save after 300s if 10 keys changed
save 60 10000   # Save after 60s if 10000 keys changed
```

### AOF (Append-Only File)
- Log every write operation
- Better durability (fsync options)
- Larger file size, slower restart

**Configuration**:
```
appendonly yes
appendfsync everysec    # Fsync every second (good balance)
```

### Recommendation for VeriNews
- Use **RDB** for development (simpler)
- Use **AOF with everysec** for production (balance durability/performance)
- Cache can be rebuilt from DB if lost (not critical data)

## Monitoring & Metrics

### Key Metrics

**Performance**:
- Hit rate: (hits / (hits + misses)) * 100%
  - Target: > 80%
- Average latency: < 1ms
- Throughput: operations per second

**Memory**:
- Memory usage: < 80% of maxmemory
- Evicted keys per second
- Expired keys per second

**Connections**:
- Active connections
- Blocked clients (should be 0)
- Rejected connections

**Replication** (if using):
- Replication lag (bytes)
- Master-replica sync status

### Monitoring Tools

**Redis CLI**:
```bash
redis-cli INFO stats               # Cache statistics
redis-cli INFO replication         # Replication status
redis-cli MONITOR                  # Real-time command stream
redis-cli --bigkeys                # Find large keys
```

**Application-Level**:
- Log cache hits/misses
- Track cache latency
- Monitor cache size growth

**External Tools**:
- Redis Insight (GUI)
- Prometheus + Grafana (metrics)
- ElasticHQ (alerts)

## Security

### Access Control

**Authentication**:
```
requirepass strong_password_here
```

**ACL** (Redis 6+):
- Define users with specific permissions
- Limit commands per user
- Restrict key access by pattern

**Example**:
```
user app_user on >password ~verification:* ~retrieval:* +get +set +del
```

### Network Security

**Bind Address**:
```
bind 127.0.0.1 192.168.1.10    # Only accessible from specific IPs
```

**TLS Encryption** (Redis 6+):
```
tls-port 6380
tls-cert-file /path/to/cert.crt
tls-key-file /path/to/key.key
```

### Data Privacy

- No sensitive data in cache (PII, passwords)
- Sanitize data before caching
- Use encryption for sensitive values if needed
- Monitor access patterns for anomalies

## Best Practices

1. **Always Set TTL**: Avoid unbounded growth
2. **Handle Cache Misses Gracefully**: Don't fail on cache unavailable
3. **Use Connection Pooling**: Reduce overhead
4. **Monitor Hit Rate**: Optimize caching strategy
5. **Compress Large Values**: Save memory
6. **Version Cache Keys**: Easier schema updates
7. **Avoid Cache Stampede**: Use locks or probabilistic early expiration
8. **Test Cache Failure**: Ensure system works without cache

## Common Pitfalls

### Cache Stampede
**Problem**: Many requests miss cache simultaneously, overload DB

**Solution**:
- Lock on cache miss (only one request computes)
- Probabilistic early expiration
- Always return stale data while refreshing

### Large Key Sizes
**Problem**: Memory exhaustion, slow operations

**Solution**:
- Break large objects into smaller keys
- Use compression (gzip, snappy)
- Set size limits

### Hot Keys
**Problem**: Single key gets too many requests

**Solution**:
- Replicate hot keys
- Use local application cache for extremely hot data
- Shard hot keys (add random suffix, query all)

## Future Enhancements

1. **Redis Cluster**: For horizontal scaling
2. **Multi-Layer Caching**: Application cache (in-process) + Redis
3. **Smart Cache Warming**: ML-based prediction of popular content
4. **Cache Analytics**: Track which cache strategies are most effective
5. **Distributed Caching**: Geographic distribution for global users
