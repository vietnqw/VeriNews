# Backend: API Layer

## What It Is

The API Layer is the HTTP interface that receives requests and returns responses. It's built with FastAPI and provides three main capabilities: health checks, article verification, and system status monitoring.

## What's Implemented

### Root Endpoint

**GET /**
- Returns API metadata and documentation links
- Provides version and service information
- Entry point for API discovery

### Health Check Endpoints

**GET /api/v1/health**
- Full system health check
- Tests database connectivity via `SELECT 1` query
- Verifies pgvector extension is available and returns version
- Shows last crawled article timestamp
- Returns unhealthy status with error details if any check fails
- Returns HTTP 200 even when unhealthy (includes status field in response)

**GET /api/v1/health/simple**
- Lightweight health check without database dependencies
- Useful for load balancers and orchestration tools
- Returns simple `{"status": "ok"}` response

### Verification Endpoint

**POST /api/v1/verify**
- Accepts a social media post (text) and optional `cache_bypass` flag (default: `false`)
- Runs the complete two-pipeline system:
  - **9-stage retrieval pipeline**: Extracts claims, generates embeddings, performs hybrid search, reranks articles
  - **4-stage verification pipeline**: Classifies claim stances, aggregates verdicts, generates Vietnamese explanations
- Returns list of matching articles with detailed relevance breakdowns
- Includes **full verification result** with verdict, confidence, and claim-by-claim analysis
- Uses SHA256-keyed Redis caching (24-hour TTL) for retrieval output (articles, timings, query count). Verification always runs per request so verdicts/explanations stay current. Set `cache_bypass=true` to force a fresh retrieval pass.
- Provides comprehensive timing breakdown for each pipeline stage

**Status**: Fully functional - both retrieval and verification logic are implemented and operational.

## How It Works

### Request Flow

1. Client sends `POST /api/v1/verify` with `text` and optional `cache_bypass`.
2. Unless `cache_bypass=true`, the API hashes the post text (`retrieval:{sha256}`) and checks Redis for a cached retrieval payload.
3. On cache hit, cached articles, `total_time_ms`, `stage_timings`, and `query_count` are reused and the retrieval pipeline is skipped. Note: claims are NOT cached, so verification will run with an empty claims list on cache hits.
4. On cache miss, `RetrievalOrchestrator` runs the full retrieval pipeline (below) and caches only the retrieval payload (articles, timings, query_count) to Redis.
5. `VerificationService` (if enabled) runs on the available articles and claims. On cache hits, claims will be empty, limiting verification capabilities.
6. Retrieval and verification timings are merged before responding.

### Retrieval Pipeline (9 Stages)

1. **Query Extraction & Guard**: LLM produces a clean query, up to 10 claims, entity lists, and a factual confidence score (1-3 scale). Posts with confidence below the configured threshold (default: 2) exit early with `exit_reason: "LOW_CONFIDENCE"`.
2. **Batch Embedding Generation**: OpenAI `text-embedding-3-small` embeddings are created for the clean query plus each claim.
3. **Similarity Filtering (optional)**: Highly redundant claims (cosine similarity > 0.9 vs. clean query) are dropped when the similarity filter is enabled.
4. **Multi-Query Hybrid Search**: For every remaining query, pgvector COSINE search and PostgreSQL BM25 search run in parallel (top 100 chunks per strategy).
5. **Reciprocal Rank Fusion**: The chunk lists are merged via RRF (`k=60`) to create a single ranked candidate list.
6. **Chunk Reranking**: The top 100 fused chunks are LLM-reranked with entity filtering (match ratio ≥ 0.6, `score_threshold` 5/10, `top_n` 10).
7. **Article Aggregation**: Reranked chunks are grouped into parent articles (max 10, chunk metadata retained, `min_chunk_score` 5.0).
8. **Article-Level Reranking**: Top articles are re-scored via LLM (score threshold 7.0, up to 15 articles, 8 parallel workers) to ensure the article truly matches the user post.
9. **Confidence Scoring & Final Validation**: Multi-signal metrics (top article score, score gap, entity coverage, temporal alignment, title similarity) are computed. Articles below the 0.25 confidence threshold exit early with `exit_reason: "NO_RELEVANT_ARTICLES"`; otherwise, metrics and optional `low_confidence_warning` flag are attached to the response.

### Verification Pipeline (4 Stages, runs if articles found)

1. **Claim-Article Mapping**: Maps extracted claims to relevant retrieved articles
2. **Stance Classification**: NLI-based classification for each claim-article pair:
   - SUPPORTS: Article supports the claim
   - REFUTES: Article contradicts the claim
   - NOT_ENOUGH_INFO: Article doesn't provide sufficient evidence
3. **Verdict Aggregation**: Combines claim verdicts into overall assessment:
   - FULLY_SUPPORTED: All claims supported
   - PARTIALLY_SUPPORTED: Mixed support/refutation
   - REFUTED: Most/all claims refuted
   - NOT_ENOUGH_INFO: Insufficient evidence overall
4. **Explanation Generation**: Creates Vietnamese explanation with confidence scores

### Response Handling

- **Success**: Returns articles + full verification result + timing breakdown
- **No Articles Found**: Returns `NOT_ENOUGH_INFO` verdict with `exit_reason: "NO_RELEVANT_ARTICLES"`
- **Low Confidence Warning**: If confidence tier is LOW/MEDIUM but above the gate, returns articles with `low_confidence_warning=true` plus a cautionary message
- **Cache**: Stores retrieval payload (articles, timings, query_count) in Redis with 24-hour TTL

## Response Structure

### POST /api/v1/verify Response

The verification endpoint returns a comprehensive response with retrieval and verification results:

```json
{
  "articles": [
    {
      "article_id": "uuid",
      "title": "Article Title",
      "source_name": "News Source",
      "published_at": "2025-01-15T10:30:00Z",
      "url": "https://...",
      "relevance_score": 8.5,
      "chunk_count": 5,
      "relevant_chunks": [
        {
          "chunk_id": "uuid",
          "chunk_index": 0,
          "chunk_text": "Article excerpt...",
          "score": 9.0
        }
      ]
    }
  ],
  "verification": {
    "verdict": "FULLY_SUPPORTED",
    "confidence": 0.92,
    "confidence_tier": "HIGH",
    "explanation": "Tất cả tuyên bố được xác nhận bởi nguồn tin đáng tin cậy...",
    "claim_verdicts": [
      {
        "claim_text": "Extracted claim",
        "verdict": "SUPPORTED",
        "confidence": 0.95,
        "supporting_evidence": [
          {
            "claim_text": "...",
            "article_id": "...",
            "article_title": "...",
            "stance": "SUPPORTS",
            "confidence": 0.95,
            "evidence_spans": [
              {
                "text": "Quote from article",
                "reasoning": "Why this supports the claim"
              }
            ]
          }
        ],
        "refuting_evidence": []
      }
    ],
    "total_claims": 3,
    "supported_claims": 3,
    "refuted_claims": 0,
    "sources_used": ["News Source 1", "News Source 2"],
    "confidence_metrics": {
      "overall_confidence": 0.92,
      "confidence_tier": "HIGH",
      "evidence_quality": 0.88,
      "source_agreement": 0.95,
      "claim_coverage": 1.0,
      "stance_confidence": 0.90,
      "temporal_relevance": 0.85
    }
  },
  "confidence_metrics": {
    "overall_confidence": 0.85,
    "confidence_tier": "HIGH",
    "top_article_score": 8.5,
    "score_gap_ratio": 0.78,
    "entity_coverage_ratio": 1.0,
    "temporal_alignment": true,
    "spatial_alignment": true,
    "title_similarity": 0.92,
    "total_qualifying_chunks": 15,
    "article_count": 3
  },
  "total_time_ms": 3500,
  "stage_timings": {
    "query_extraction": 250,
    "embedding": 450,
    "hybrid_search": 650,
    "fusion": 180,
    "reranking": 850,
    "aggregation": 220,
    "article_reranking": 380,
    "confidence_scoring": 320,
    "claim_article_mapping": 200,
    "stance_classification": 950,
    "verdict_aggregation": 180,
    "explanation_generation": 280,
    "verification_total": 1610
  },
  "query_count": 3,
  "cache_hit": false,
  "early_exit": false,
  "exit_reason": null,
  "message": null
}
```

### Health Check Responses

**GET /api/v1/health Response**:
```json
{
  "status": "healthy",
  "api": "running",
  "database": "connected",
  "pgvector": "available (v0.7.0)",
  "last_crawled_at": "2025-01-20T15:30:00Z"
}
```

**GET /api/v1/health/simple Response**:
```json
{
  "status": "ok"
}
```

## Technology

- **FastAPI**: Python web framework
- **Pydantic**: Request/response validation
- **SQLAlchemy**: Database access
- **Redis**: Result caching

## Configuration

### Server Configuration
- API runs on port **8000** (configurable via environment)
- Base path: `/api/v1`
- CORS enabled for all origins (configurable)
- Request body size limit: 10,000 characters for post text

### Documentation
- OpenAPI (Swagger) docs automatically available at `/api/v1/docs`
- ReDoc documentation at `/api/v1/redoc`
- Interactive API testing available in Swagger UI

### Retrieval Pipeline Settings (from config.yaml)
- **Query Extraction**:
  - Enabled: true
  - Maximum claims: 10
  - Minimum factual confidence threshold: 2 (1=opinion, 2=vague, 3=verifiable)
  - Similarity filter: enabled with `similarity_threshold` 0.9 to drop redundant claims
- **Reranking**:
  - Enabled: true
  - Chunk reranking: `score_threshold` 5 (0-10 scale) with entity match ratio ≥ 0.6, 4 parallel workers, 15s timeout
  - Article-level reranking: enabled (`score_threshold` 7.0, max 15 articles, 8 workers, 5s timeout)
- **Aggregation**:
  - Maximum articles returned: 10 with chunk metadata included
  - Minimum chunk score: 5.0 (0-10 scale)
- **Confidence Scoring**:
  - Enabled: true
  - Minimum confidence threshold: 0.25 (25%)
- **Caching**:
  - Enabled: true (Redis, `retrieval:` prefix + SHA256 hash)
  - TTL: 24 hours

### Verification Pipeline Settings (from config.yaml)
- **Stance Classification**:
  - Minimum confidence: 0.6 (60%), 4 workers, 10s timeout
- **Verdict Aggregation**:
  - Minimum evidence per claim: 1
  - Conflict resolution: conservative mode
  - Verdict mode: worst-case evaluation
- **Confidence Scoring**:
  - Weights: evidence_quality 0.30, source_agreement 0.25, stance_confidence 0.25, claim_coverage 0.15, temporal_relevance 0.05
  - Thresholds: HIGH ≥ 0.75, MEDIUM ≥ 0.50, LOW ≥ 0.25
- **Explanation Generation**:
  - Language: vi (Vietnamese), max length 500 characters

## Request & Response Details

### POST /api/v1/verify - Request Validation

**Request Schema** (VerificationRequest):
```python
{
  "text": str,           # Required: 10-10,000 characters
  "cache_bypass": bool   # Optional: Force bypass Redis cache (default: False)
}
```

**Validation Rules**:
- `text` is required and must be between 10-10,000 characters
- `cache_bypass` is optional boolean (defaults to False)
- Invalid text length returns HTTP 422 with validation error
- Invalid JSON structure returns HTTP 422

### Error Handling

**HTTP Status Codes**:
- **200 OK**: Successful verification (regardless of verdict)
- **422 Unprocessable Entity**: Request validation failed or JSON parsing error
- **500 Internal Server Error**: System error (database, LLM service, etc.)

**Error Response Format**:
```json
{
  "detail": "Error message describing what went wrong"
}
```

**Common Error Scenarios**:
1. **Database Unavailable**: Returns 500 with connection error
2. **OpenAI API Failure**: Returns 500, logged for debugging
3. **Redis Cache Failure**: Continues without cache, doesn't block verification
4. **No Claims Extracted**: Returns NOT_ENOUGH_INFO verdict
5. **No Relevant Articles**: Returns NOT_ENOUGH_INFO with exit_reason

## Special Features

### Early Exit Conditions

The API may exit early in these scenarios:

1. **Low Factual Confidence** (`exit_reason: "LOW_CONFIDENCE"`)
   - Post doesn't contain verifiable claims
   - Typical for opinions or non-factual posts

2. **No Relevant Articles** (`exit_reason: "NO_RELEVANT_ARTICLES"`)
   - No articles found after retrieval pipeline
   - Triggered when multi-signal confidence < 0.25; returns NOT_ENOUGH_INFO verdict

### Cache Behavior

- **Cache Hit**: Reuses cached retrieval payload (articles, total_time_ms, stage_timings, query_count) keyed by `retrieval:{sha256(text)}`. Verification always runs, but without cached claims (claims are NOT cached), verification results may be limited.
- **Cache Miss**: Runs full pipeline and stores retrieval output (articles, timings, query_count) with 24-hour TTL. Claims, confidence metrics, and other metadata are NOT cached.
- **Cache Bypass**: Ignores cache and always runs full pipeline (set `cache_bypass=true`)
- **Partial Failures**: Cache failures don't block verification

### Performance Characteristics

**Typical Response Times**:
- **Cache Hit**: 1,000-2,000ms (verification still runs)
- **Cache Miss (Fresh)**: 2,500-4,500ms
- **Breakdown**:
  - Query Extraction: 200-300ms
  - Embedding Generation: 300-600ms
  - Hybrid Search: 500-1,000ms
  - Reranking & Aggregation: 1,000-1,500ms
  - Verification Pipeline: 1,000-2,000ms
