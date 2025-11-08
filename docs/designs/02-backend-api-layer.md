# Backend: API Layer

## Overview

The API Layer serves as the entry point for all client requests to the VeriNews backend. It provides a RESTful HTTP interface that handles verification requests from browser extensions, manages authentication, enforces rate limits, and orchestrates the verification workflow.

## Purpose

Provide a secure, scalable, and well-documented interface for:
- Processing verification requests from browser extensions
- Managing user authentication and authorization
- Enforcing rate limits and usage quotas
- Coordinating backend services to generate verification results
- Delivering structured responses to clients

## Key Responsibilities

1. **Request Handling**
   - Accept and validate incoming verification requests
   - Parse and sanitize post content (text, images, metadata)
   - Handle various content types and formats
   - Return structured verification responses

2. **Authentication & Authorization**
   - Verify API keys or JWT tokens
   - Manage user sessions and permissions
   - Implement role-based access control (RBAC)
   - Protect sensitive endpoints

3. **Rate Limiting & Throttling**
   - Enforce per-user or per-IP rate limits
   - Prevent abuse and DDoS attacks
   - Implement sliding window or token bucket algorithms
   - Return appropriate HTTP status codes (429 Too Many Requests)

4. **Workflow Orchestration**
   - Coordinate retrieval, AI/ML, and caching services
   - Manage asynchronous task execution
   - Handle service failures gracefully
   - Aggregate results from multiple services

5. **Response Formatting**
   - Structure verification results consistently
   - Include metadata (request ID, timestamps, processing time)
   - Support multiple response formats (JSON, XML if needed)
   - Implement pagination for list endpoints

6. **Error Handling**
   - Catch and log exceptions
   - Return user-friendly error messages
   - Provide actionable error codes
   - Implement circuit breakers for failing services

7. **Monitoring & Logging**
   - Log all requests with timing information
   - Track error rates and response times
   - Expose health check endpoints
   - Integrate with monitoring tools (Prometheus, Grafana)

## API Endpoints

### Core Endpoints

#### POST /api/v1/verify
**Purpose**: Submit a social media post for verification

**Request Body**:
```
{
  "post_text": "Full text content of the post",
  "post_images": ["url1", "url2"],  // Optional
  "post_metadata": {
    "platform": "facebook",
    "author": "username",
    "timestamp": "2024-01-15T10:30:00Z",
    "url": "https://..."
  }
}
```

**Response**:
```
{
  "request_id": "uuid",
  "status": "completed",
  "verdict": "verified" | "misleading" | "unverified",
  "credibility_score": 85,
  "explanation": "Brief explanation of the verdict",
  "evidence": {
    "matched_articles": [...],
    "claims": [...],
    "image_analysis": {...}
  },
  "processing_time_ms": 1250,
  "cached": false
}
```

**Status Codes**:
- 200: Verification completed successfully
- 202: Verification accepted, processing (async)
- 400: Invalid request (missing fields, malformed data)
- 401: Authentication required
- 429: Rate limit exceeded
- 500: Internal server error

#### GET /api/v1/verify/{request_id}
**Purpose**: Retrieve verification results for a previous request (async support)

**Response**: Same as POST /verify

#### GET /api/v1/health
**Purpose**: Health check for monitoring

**Response**:
```
{
  "status": "healthy",
  "api": "running",
  "database": "connected",
  "redis": "connected",
  "pgvector": "available (v0.8.1)",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### GET /api/v1/health/simple
**Purpose**: Simple health check (200 OK or 503 Service Unavailable)

### Management Endpoints

#### GET /api/v1/sources
**Purpose**: List trusted news sources

**Response**:
```
{
  "sources": [
    {
      "id": "uuid",
      "name": "BBC News",
      "url": "https://bbc.com",
      "credibility_rating": "high",
      "article_count": 15000
    }
  ]
}
```

#### GET /api/v1/stats
**Purpose**: Retrieve API usage statistics (authenticated)

**Response**:
```
{
  "total_verifications": 10500,
  "verifications_today": 150,
  "rate_limit_remaining": 850,
  "rate_limit_reset": "2024-01-15T11:00:00Z"
}
```

### Admin Endpoints (Future)

- POST /api/v1/admin/sources - Add trusted sources
- DELETE /api/v1/admin/sources/{id} - Remove sources
- POST /api/v1/admin/crawl - Trigger manual crawl
- GET /api/v1/admin/metrics - System metrics dashboard

## Authentication Mechanisms

### API Key Authentication (Phase 1)
- Simple API key passed in header: `X-API-Key: <key>`
- Keys stored securely in database (hashed)
- Per-key rate limits and quotas
- Easy to implement and use

**Flow**:
1. User requests API key via registration endpoint
2. Backend generates and returns key (shown once)
3. User includes key in all requests
4. Backend validates key and checks limits

### JWT Token Authentication (Phase 2)
- More secure, includes expiration and claims
- Supports refresh tokens
- Better for user-specific features

**Flow**:
1. User logs in with credentials
2. Backend returns JWT access token + refresh token
3. Client includes token in Authorization header
4. Backend validates signature and expiration
5. Client refreshes token when expired

### OAuth 2.0 (Phase 3 - Optional)
- For third-party integrations
- Delegation of access without sharing credentials
- Standard protocol for authorization

## Rate Limiting Strategy

### Tiered Limits
- **Free Tier**: 100 requests/day, 10 requests/minute
- **Basic Tier**: 1,000 requests/day, 50 requests/minute
- **Premium Tier**: 10,000 requests/day, 200 requests/minute
- **Enterprise**: Custom limits

### Implementation
- Redis-based sliding window algorithm
- Track requests per API key or IP address
- Return rate limit info in headers:
  - `X-RateLimit-Limit`: Maximum requests allowed
  - `X-RateLimit-Remaining`: Requests remaining
  - `X-RateLimit-Reset`: Timestamp when limit resets

### Handling Exceeded Limits
- Return 429 Too Many Requests
- Include Retry-After header with wait time
- Log repeated violations for abuse detection

## Request Validation

### Input Sanitization
- Remove potentially harmful characters
- Limit text length (e.g., 10,000 characters max)
- Validate URLs and image formats
- Check for SQL injection patterns

### Schema Validation
- Use Pydantic models for request/response validation
- Enforce required fields
- Validate data types and formats
- Provide clear validation error messages

### Content Filtering
- Block obviously spam or non-news content
- Detect and reject bot-generated requests
- Implement CAPTCHA for suspicious activity (optional)

## Workflow Orchestration

### Synchronous Verification Flow
**Best for**: Simple requests, low latency requirements

1. Receive verification request
2. Validate and authenticate
3. Check cache for existing results
4. If not cached:
   - Call Retrieval System
   - Call AI/ML Services (in parallel where possible)
   - Aggregate results
5. Store in cache
6. Return response

### Asynchronous Verification Flow
**Best for**: Complex requests, high load scenarios

1. Receive verification request
2. Validate and authenticate
3. Queue verification task (Celery/Redis)
4. Return 202 Accepted with request_id
5. Client polls GET /verify/{request_id}
6. Return 200 with results when ready

**Benefits**:
- Better scalability under load
- Prevents request timeouts
- Enables background processing
- Supports webhook notifications (future)

## Error Handling

### Error Response Format
```
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Post text is required",
    "details": {
      "field": "post_text",
      "reason": "missing_required_field"
    },
    "request_id": "uuid",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### Error Codes
- `INVALID_REQUEST`: Malformed or missing required fields
- `AUTHENTICATION_FAILED`: Invalid or missing API key
- `RATE_LIMIT_EXCEEDED`: Too many requests
- `SERVICE_UNAVAILABLE`: Backend service temporarily down
- `INTERNAL_ERROR`: Unexpected server error
- `CONTENT_TOO_LARGE`: Post text exceeds limit

### Circuit Breaker Pattern
- Monitor failure rates for downstream services
- Open circuit after threshold (e.g., 50% failures over 1 min)
- Return fallback response or cached data
- Automatically retry after cooldown period

## Security Considerations

### Input Security
- Sanitize all user inputs
- Prevent injection attacks (SQL, NoSQL, XSS)
- Validate file uploads (images)
- Limit request payload size

### API Security
- Enforce HTTPS only (TLS 1.2+)
- Implement CORS policies for browser extensions
- Use secure headers (HSTS, CSP, X-Content-Type-Options)
- Rotate API keys periodically

### DDoS Protection
- Rate limiting per IP and per API key
- Implement request queuing
- Use CDN/WAF for protection (Cloudflare)
- Monitor for anomalous traffic patterns

### Data Privacy
- Don't log sensitive user data
- Anonymize verification requests
- Comply with GDPR/privacy regulations
- Provide data deletion endpoints

## Performance Optimization

### Response Time Goals
- Cache hit: < 50ms
- Simple verification: < 2 seconds
- Complex verification: < 5 seconds
- Health check: < 10ms

### Optimization Strategies
- Aggressive caching of results
- Database query optimization
- Connection pooling
- Async I/O for external calls
- Result streaming for large responses
- CDN for static content

### Load Balancing
- Horizontal scaling with multiple API instances
- Round-robin or least-connections load balancing
- Session affinity for stateful operations
- Health checks to remove unhealthy instances

## Monitoring & Observability

### Key Metrics
- Request rate (requests/second)
- Response time (p50, p95, p99)
- Error rate (% of 4xx and 5xx responses)
- Cache hit rate
- Active connections
- Queue depth (for async processing)

### Logging
- Structured JSON logs
- Include correlation IDs for request tracing
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Sensitive data redaction

### Alerting
- High error rate (> 5%)
- Slow response times (p95 > 5s)
- Service unavailability
- Rate limit violations spike
- Database connection failures

## API Documentation

### Auto-generated Docs
- Swagger/OpenAPI specification
- Interactive API explorer (Swagger UI)
- ReDoc for beautiful documentation
- Automatically updated from code

### Documentation Includes
- Endpoint descriptions and examples
- Request/response schemas
- Authentication requirements
- Error codes and handling
- Rate limiting policies
- Code samples in multiple languages

## Versioning Strategy

### API Versioning
- URL-based versioning: `/api/v1/`, `/api/v2/`
- Maintain backward compatibility
- Deprecation notices with sunset dates
- Clear migration guides between versions

### Version Lifecycle
- **Active**: Current version, receives all updates
- **Deprecated**: Old version, security patches only
- **Sunset**: Version removal date announced
- **Removed**: No longer available

## Future Enhancements

1. **WebSocket Support**
   - Real-time verification updates
   - Push notifications for async results
   - Reduced polling overhead

2. **GraphQL API**
   - Flexible query language
   - Reduce over-fetching
   - Single request for complex data

3. **Batch Verification**
   - Verify multiple posts in one request
   - Improved efficiency for power users
   - Parallel processing

4. **Webhook Notifications**
   - Callback URLs for async results
   - Event-driven architecture
   - Reduce client polling

5. **API Analytics Dashboard**
   - Usage trends and patterns
   - Performance metrics
   - User behavior insights
