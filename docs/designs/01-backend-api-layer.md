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

**GET /api/v1/health/simple**
- Simple ping endpoint
- Returns 200 OK if system is up

### Verification Endpoint

**POST /api/v1/verify**
- Accepts a social media post (text)
- Runs the full retrieval pipeline to find relevant articles
- Returns list of matching articles with relevance scores
- Includes timing information for each stage
- Uses Redis caching for faster repeat queries

**Note**: The actual verification (credibility scoring, verdict generation) is not yet implemented. Currently returns a dummy verification result. The article retrieval works fully.

## How It Works

1. User sends POST request with post text
2. API checks Redis cache for previous results
3. If not cached, runs the 6-stage retrieval pipeline:
   - Extract clean query and claims from post
   - Generate embeddings
   - Search using vector + keyword methods
   - Combine results with RRF fusion
   - Rerank using AI
   - Aggregate chunks into articles
4. Stores result in cache
5. Returns articles with timing data

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
