# Backend: API Layer

## What It Is

The API Layer is the HTTP interface that receives requests and returns responses. It's built with FastAPI and provides two main capabilities: health checks and article retrieval.

## What's Implemented

### Health Check Endpoints

**GET /api/v1/health**
- Checks if the system is running
- Tests database connection
- Verifies pgvector extension is available
- Returns status for each component
- Shows last crawled article timestamp

**GET /api/v1/health/simple**
- Simple ping endpoint
- Returns 200 OK if system is up

### Verification Endpoint

**POST /api/v1/verify**
- Accepts a social media post (text) and optional `cache_bypass` flag
- Runs the full retrieval pipeline to find relevant articles
- Returns list of matching articles with relevance scores
- Includes **detailed confidence metrics** and **early exit** status
- Uses Redis caching for faster repeat queries

**Note**: The actual verification (truth-checking logic) is not yet implemented. Currently returns a dummy verification result, but the article retrieval and relevance scoring are fully functional.

## How It Works

1. **Request**: User sends POST request with `text`
2. **Cache Check**: API checks Redis (unless `cache_bypass=true`)
3. **Pipeline Execution**: Runs the 9-stage retrieval pipeline:
   - **Extraction**: Get clean query + claims + entities
   - **Embedding**: Generate vectors for all queries
   - **Search**: Run Hybrid (Vector + BM25) search
   - **Fusion**: Combine results with Reciprocal Rank Fusion
   - **Chunk Reranking**: Score chunks with AI (parallel workers)
   - **Aggregation**: Group chunks into articles
   - **Article Reranking**: Validate full-article relevance
   - **Confidence**: Calculate multi-signal confidence score
   - **Validation**: Gate results based on confidence threshold
4. **Caching**: Stores result in Redis (24h TTL)
5. **Response**: Returns articles + confidence metrics + timing data

## Response Structure

The API returns a rich JSON response:

```json
{
  "articles": [...],
  "confidence_metrics": {
    "overall_confidence": 0.85,
    "confidence_tier": "HIGH",
    "entity_coverage_ratio": 1.0
  },
  "retrieval_confidence": 0.85,
  "factual_confidence": 3,
  "low_confidence_warning": false,
  "early_exit": false,
  "exit_reason": null,
  "message": null,
  "total_time_ms": 1250,
  "stage_timings": {...},
  "cache_hit": false
}
```

## Technology

- **FastAPI**: Python web framework
- **Pydantic**: Request/response validation
- **SQLAlchemy**: Database access
- **Redis**: Result caching

## Configuration

- API runs on port 8000 (configurable)
- Base path: `/api/v1`
- Automatic OpenAPI docs at `/api/v1/docs`
- ReDoc documentation at `/api/v1/redoc`
