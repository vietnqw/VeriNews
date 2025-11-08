# VeriNews Test Suite

Comprehensive testing framework for the hybrid retrieval pipeline.

## Overview

This test suite provides extensive coverage for all retrieval pipeline components including:
- Vietnamese text processing (BM25 tokenization)
- Vector and keyword search services
- Reciprocal Rank Fusion (RRF)
- LLM-based query extraction and reranking
- Article aggregation
- Caching layer
- API endpoints

## Test Structure

```
tests/
├── unit/                     # Isolated component tests
│   ├── services/
│   │   ├── retrieval/        # Retrieval pipeline services
│   │   ├── cache/            # Redis caching
│   │   └── content/          # Embedding generation
│   ├── models/               # Database models
│   └── api/                  # API endpoints
├── integration/              # Service interaction tests
├── performance/              # Load and latency benchmarks
├── fixtures/                 # Test data and mocks
└── conftest.py              # Shared pytest fixtures
```

## Running Tests

### All Tests
```bash
pytest tests/
```

### Specific Test Categories
```bash
# Unit tests only
pytest tests/unit/ -m unit

# Integration tests only
pytest tests/integration/ -m integration

# Performance tests only
pytest tests/performance/ -m performance
```

### Specific Services
```bash
# Vietnamese processor tests
pytest tests/unit/services/retrieval/test_vietnamese_processor.py

# RRF fusion tests
pytest tests/unit/services/retrieval/test_fusion_service.py
```

### With Coverage Report
```bash
pytest tests/ --cov=app --cov-report=html
# View: open htmlcov/index.html
```

### Fast Tests (skip slow)
```bash
pytest tests/ -m "not slow"
```

## Test Markers

Tests are marked with custom markers for easy filtering:

- `@pytest.mark.unit` - Unit tests (isolated components)
- `@pytest.mark.integration` - Integration tests (service interactions)
- `@pytest.mark.performance` - Performance benchmarks
- `@pytest.mark.slow` - Tests taking >1 second
- `@pytest.mark.requires_db` - Requires PostgreSQL database
- `@pytest.mark.requires_redis` - Requires Redis
- `@pytest.mark.requires_openai` - Requires OpenAI API (mocked)

## Test Fixtures

### Database Fixtures
- `async_db_session` - Async SQLAlchemy session (in-memory SQLite)
- `sync_db_session` - Sync SQLAlchemy session

### Mock Services
- `mock_redis` - FakeRedis instance
- `mock_openai_embeddings` - Mock OpenAI embeddings API
- `mock_openai_completions` - Mock OpenAI completions API
- `mock_openai_client` - Complete mock OpenAI client

### Test Data
- `sample_vietnamese_post` - Sample Facebook post
- `sample_clean_query` - Cleaned query
- `sample_claims` - Extracted claims
- `sample_embedding` - 1536-dim embedding vector
- `sample_chunk_text` - Article chunk text

## Writing New Tests

### Unit Test Example
```python
import pytest

@pytest.mark.unit
@pytest.mark.asyncio
class TestMyService:
    async def test_feature(self, async_db_session):
        """Test description."""
        # Arrange
        service = MyService(async_db_session)

        # Act
        result = await service.do_something()

        # Assert
        assert result is not None
```

### Integration Test Example
```python
import pytest

@pytest.mark.integration
@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_full_pipeline(async_db_session, mock_openai_client):
    """Test end-to-end pipeline."""
    orchestrator = RetrievalOrchestrator(async_db_session)
    result = await orchestrator.retrieve("Test post")
    assert len(result["articles"]) > 0
```

## Coverage Goals

- **Overall**: >80% code coverage
- **Critical services**: >90% coverage
  - Vietnamese processor
  - RRF fusion
  - Query extraction
  - Reranking
  - Vector search
  - BM25 search

## Current Status

**Test Suite**: 127 tests passing | Coverage: 52% | Duration: 3.52s

### ✅ Implemented Tests (Phases 1-4)

**Test Infrastructure**
- Pytest configuration with async support
- Shared fixtures (conftest.py)
- Mock services (OpenAI, Redis, Database)
- Test data factories (Faker with Vietnamese locale)
- PostgreSQL + pgvector integration testing
- Async engine management for integration tests

**Unit Tests (98 tests)**

**Vietnamese Processor** (14 tests)
- Compound word tokenization ("công ty" → "công_ty")
- Special characters handling
- Mixed language support (Vietnamese + English)
- Edge cases (empty, whitespace, Unicode, very long text)
- Configuration toggle

**RRF Fusion Service** (10 tests)
- Single/multiple list fusion
- Overlapping chunks (same chunk in multiple lists)
- Different k parameter values
- Mathematical correctness verification
- Empty lists handling
- Score monotonicity
- Metadata preservation

**Article Aggregation Service** (14 tests)
- Chunk-to-article aggregation with score summation
- Relevance threshold filtering
- Max articles limit enforcement
- Empty inputs and edge cases
- Article metadata preservation
- Chunk inclusion/exclusion toggle
- Serialization (to_dict) functionality

**Retrieval Cache Service** (18 tests)
- SHA256 hash-based cache key generation
- Redis get/set operations (using FakeRedis)
- Cache hit/miss scenarios
- Disabled cache behavior
- Cache clearing (clear_all)
- ArticleResult serialization/deserialization
- Unicode text handling (Vietnamese characters)
- Special characters and emojis
- Very long text caching
- Empty articles list edge case

**Query Extraction Service** (13 tests)
- LLM-based clean query extraction
- Claims extraction from Facebook posts
- Max claims limit enforcement
- Empty/whitespace claim filtering
- JSON parsing error handling
- LLM exception fallback behavior
- Vietnamese Unicode character support
- Whitespace stripping
- Prompt validation (includes post text, JSON format)

**Reranker Service** (15 tests)
- LLM-based chunk reranking
- Batch processing optimization (5 chunks per API call)
- Score normalization to 0-1 range
- Top-n result limiting
- JSON parsing error handling
- LLM exception fallback
- Mismatched score count handling
- Chunk metadata preservation
- Descending score ordering
- Batch size configuration
- Vietnamese text support

**Hybrid Retrieval Service** (14 tests)
- Vector + BM25 search coordination
- Single query hybrid search (both enabled)
- Vector-only and BM25-only modes
- Both searches disabled handling
- Top-k parameter passing
- Multi-query search (N queries → 2N result lists)
- Empty queries handling
- Result list ordering verification
- Result preservation across queries
- Vietnamese text support
- Empty results handling
- Search exception propagation

**Retrieval Orchestrator** (10 tests)
- Full 6-stage pipeline execution
- Query extraction disabled mode
- Reranking disabled mode
- Stage timing measurement accuracy
- Empty fusion results handling
- Batch embedding generation with correct queries
- Multi-query hybrid search coordination
- Reranking top 100 chunks limit
- Vietnamese text handling
- Service orchestration order verification

**Integration Tests (29 tests)**

**BM25 Search Service** (9 tests)
- PostgreSQL full-text search with ts_rank_cd
- Vietnamese tokenization in actual database
- Batch indexing and reindexing
- Relevance ranking
- Top-k limiting
- Empty results handling
- Search result completeness

**Vector Search Service** (10 tests)
- pgvector similarity search with cosine distance
- IVFFlat index usage for fast ANN search
- Top-k result limiting
- Similarity score range validation (0-1)
- Search result completeness
- Empty database handling
- Different query embeddings produce different rankings
- Vector dimension handling (1536)
- Normalized vs unnormalized embeddings
- Zero vector handling
- Monotonic score ordering

### 🚧 Pending Tests (Phases 4-6)

**Hybrid Search Services**
- Hybrid retrieval service (vector + BM25 coordination)
- Multi-query execution (clean_query + claims)
- Sequential vs concurrent operations

**Pipeline Orchestration**
- Retrieval orchestrator (full 6-stage pipeline)
- Performance metrics tracking
- Error handling across stages

**Content Services**
- Chunking service (paragraph-level splitting)
- Embedding service (OpenAI integration)

**API Layer**
- Verification API endpoint
- Health check API endpoint

**End-to-End Integration Tests**
- Full pipeline E2E (Facebook post → articles)
- Cache hit/miss scenarios
- Real OpenAI API calls (mocked)

**Performance Tests**
- Pipeline latency benchmarks
- Concurrent request handling
- Large-scale data tests (10k+ chunks)
- Cache hit rate optimization

## CI/CD Integration

Tests run automatically on:
- Every commit (unit tests)
- Pull requests (unit + integration)
- Main branch merge (full suite + performance)

### GitHub Actions Workflow
```yaml
- name: Run tests
  run: |
    pytest tests/ --cov=app --cov-report=xml

- name: Upload coverage
  uses: codecov/codecov-action@v3
```

## Troubleshooting

### Tests Failing Locally

**Import errors:**
```bash
# Ensure you're in the backend directory
cd VeriNews/backend

# Sync dependencies
uv sync

# Run tests with PYTHONPATH
PYTHONPATH=. pytest tests/
```

**Database errors:**
```bash
# Tests use in-memory SQLite by default
# No PostgreSQL required for unit tests
```

**Redis errors:**
```bash
# Tests use FakeRedis by default
# No Redis server required
```

### Slow Tests

```bash
# Skip slow tests
pytest tests/ -m "not slow"

# Run only fast tests
pytest tests/unit/ --durations=10
```

## Contributing

When adding new tests:
1. Follow the existing structure
2. Use appropriate markers
3. Write descriptive test names
4. Include docstrings
5. Aim for >80% coverage of new code
6. Run tests locally before committing

## Resources

- [Pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [Coverage.py](https://coverage.readthedocs.io/)
- [FakeRedis](https://github.com/cunla/fakeredis-py)
