# Backend Improvements for Full Extension Functionality

This document lists backend changes needed to unlock full extension features.

## Priority: HIGH

### 1. Add `claims` to VerificationResponse

**Location**: `VeriNews/backend/app/schemas/verification.py`

**Current State**: Claims are extracted and stored in `VerificationRequest.claims` but not returned in API response.

**Required Change**:
```python
class VerificationResponse(BaseModel):
    articles: List[ArticleResultSchema]
    total_time_ms: int
    stage_timings: Dict[str, float]
    query_count: int
    verification: DummyVerificationResult
    cache_hit: bool
    claims: List[str] = []  # ADD THIS FIELD
```

**Implementation**:
```python
# In verification.py endpoint
verification_request = await verification_service.get_by_id(
    db, verification_request_id
)

return VerificationResponse(
    articles=article_results,
    # ... other fields ...
    claims=verification_request.claims or [],  # ADD THIS
    cache_hit=cached_result is not None,
)
```

**Impact**: Enables claims display section in extension UI.

---

## Priority: MEDIUM

### 2. Add `url` Field to Article Model

**Location**:
- `VeriNews/backend/app/models/article.py`
- `VeriNews/backend/app/schemas/verification.py`

**Current State**: Articles have no URL field. Extension uses `article_id` as fallback.

**Required Changes**:

**Models** (`app/models/article.py`):
```python
class Article(Base):
    __tablename__ = "articles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rss_feed_id = Column(UUID(as_uuid=True), ForeignKey("rss_feeds.id"))
    url = Column(String, unique=True, nullable=False, index=True)  # ADD THIS
    title = Column(String, nullable=False)
    # ... rest of fields
```

**Migration**:
```bash
cd VeriNews/backend
uv run alembic revision --autogenerate -m "Add url field to articles table"
uv run alembic upgrade head
```

**Schema** (`app/schemas/verification.py`):
```python
class ArticleResultSchema(BaseModel):
    article_id: UUID
    title: str
    source_name: str
    published_at: datetime
    relevance_score: float
    chunk_count: int
    url: str  # ADD THIS FIELD
    relevant_chunks: List[ChunkDetailSchema] = []
```

**Service Updates** (`app/services/retrieval/article_aggregation_service.py`):
- Query article URL when building results
- Add to ArticleResultSchema construction

**Impact**: Enables clickable links to original articles in extension.

---

## Priority: MEDIUM

### 3. Add Normalized Similarity Score

**Location**: `VeriNews/backend/app/schemas/verification.py`

**Current State**: `relevance_score` is summed chunk scores (e.g., 2.45). Extension normalizes to 0-1.

**Options**:

**Option A**: Add separate normalized field
```python
class ArticleResultSchema(BaseModel):
    # ... existing fields ...
    relevance_score: float  # Keep raw score
    similarity_score: float  # Add normalized 0-1 score
```

**Option B**: Normalize in aggregation service
```python
# In article_aggregation_service.py
max_score = max(article_scores.values()) if article_scores else 1.0
normalized_scores = {
    article_id: score / max_score
    for article_id, score in article_scores.items()
}
```

**Recommendation**: Option A - keeps raw score for debugging, adds normalized for UI.

**Impact**: More accurate similarity percentages in extension UI.

---

## Priority: LOW (Future Enhancement)

### 4. Implement Full Verification Logic

**Location**: Create new service `app/services/verification/verdict_service.py`

**Current State**: Returns hardcoded `{"verdict": "NOT_IMPLEMENTED", "confidence": 0.0}`

**Required**: LLM-based verdict generation using retrieved articles.

**Proposed Flow**:
1. Take top N retrieved articles (from retrieval result)
2. Extract relevant chunks
3. Use LLM prompt to determine verdict:
   - **VERIFIED**: Claims supported by multiple trusted sources
   - **FALSE**: Claims contradicted by sources
   - **MISLEADING**: Partially true but missing context
   - **OUT_OF_CONTEXT**: True information used incorrectly
   - **UNVERIFIED**: Insufficient information
4. Generate confidence score (0-1)
5. Provide reasoning

**Schema Update**:
```python
class VerificationResult(BaseModel):
    verdict: Literal["VERIFIED", "FALSE", "MISLEADING", "OUT_OF_CONTEXT", "UNVERIFIED"]
    confidence: float  # 0-1
    reasoning: str
    per_criterion_scores: Dict[str, float] = {}  # Optional
```

**Impact**: Full fact-checking functionality with color-coded verdicts.

---

## Priority: LOW (Future Enhancement)

### 5. Add Per-Criterion Scoring

**Location**: `app/services/verification/scoring_service.py` (new)

**Criteria to Implement**:
- `content_similarity`: Overall semantic similarity (0-1)
- `support_ratio`: % of claims supported by evidence
- `contradiction_ratio`: % of claims contradicted
- `not_mentioned_ratio`: % of claims not found in sources

**Implementation**: LLM-based claim-by-claim verification against retrieved articles.

**Impact**: Detailed scoring breakdown in extension UI.

---

## Priority: LOW (Future Enhancement)

### 6. Add Contextual Judgment

**Location**: `app/services/verification/context_service.py` (new)

**Purpose**: Detect if information is taken out of context.

**Schema**:
```python
class ContextualJudgment(BaseModel):
    is_out_of_context: bool
    reasoning: str
    original_context: str = ""
```

**Implementation**: Compare post framing vs. article context using LLM.

**Impact**: Out-of-context warnings in extension UI.

---

## Migration Order

When implementing these changes:

1. ✅ **Phase 1**: Add `claims` to response (quick win, no migration)
2. ✅ **Phase 2**: Add `url` field to Article (requires migration)
3. ✅ **Phase 3**: Add normalized similarity score (quick, no migration)
4. 🔄 **Phase 4+**: Implement verification logic (major feature, iterative)

---

## Testing Checklist

After each backend change:

- [ ] Update API documentation (Swagger auto-updates)
- [ ] Test endpoint manually: `curl -X POST http://localhost:8000/api/v1/verify -H "Content-Type: application/json" -d '{"text": "Test post"}'`
- [ ] Verify extension receives new fields correctly
- [ ] Check extension console for errors
- [ ] Test with various post types (short, long, Vietnamese, etc.)
- [ ] Verify backward compatibility with old frontend code

---

## Notes

- Extension is built to handle missing fields gracefully
- Changes can be implemented incrementally
- Adapter layer in extension (`api.js`) will automatically use new fields when available
- No extension code changes needed when backend is updated (except to remove adapter workarounds)
