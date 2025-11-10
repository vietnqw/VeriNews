# VeriNews Test Suite

Comprehensive testing for the hybrid retrieval pipeline.

## Overview

Test coverage for all components:
- Vietnamese text processing and BM25 search
- Vector search with pgvector
- Reciprocal Rank Fusion (RRF)
- LLM-based query extraction and reranking
- Article aggregation and caching
- API endpoints

**Current Status**: 127 tests passing | 52% coverage | 3.52s duration

## Test Structure

```
tests/
├── unit/                  # Isolated component tests
│   ├── api/               # API endpoints
│   ├── services/          # Business logic
│   │   ├── retrieval/     # Retrieval pipeline
│   │   ├── cache/         # Redis caching
│   │   ├── content/       # Chunking, embeddings
│   │   ├── crawler/       # RSS, scraping
│   │   └── repository/    # Data access
├── integration/           # Service interaction tests
├── performance/           # Load and latency benchmarks
└── conftest.py           # Shared fixtures
```

## Running Tests

### Quick Commands

```bash
# All tests
pytest tests/

# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# With coverage report
pytest tests/ --cov=app --cov-report=html

# Skip slow tests
pytest tests/ -m "not slow"
```

### Test Markers

Filter tests using markers:

```bash
# Unit tests
pytest -m unit

# Integration tests requiring database
pytest -m "integration and requires_db"

# Fast tests only
pytest -m "not slow"
```

Available markers:
- `unit` - Isolated component tests
- `integration` - Service interaction tests
- `performance` - Performance benchmarks
- `slow` - Tests taking >1 second
- `requires_db` - Requires PostgreSQL
- `requires_redis` - Requires Redis
- `requires_openai` - Requires OpenAI API (mocked)

## Key Fixtures

### Database
- `async_db_session` - Async SQLAlchemy session (in-memory SQLite)
- `sync_db_session` - Sync SQLAlchemy session

### Mock Services
- `mock_redis` - FakeRedis instance
- `mock_openai_embeddings` - Mock embeddings API
- `mock_openai_completions` - Mock completions API
- `mock_openai_client` - Complete OpenAI client mock

### Test Data
- `sample_vietnamese_post` - Sample Facebook post
- `sample_clean_query` - Cleaned query
- `sample_claims` - Extracted claims
- `sample_embedding` - 1536-dim embedding vector

## Writing Tests

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

## Test Coverage

Current coverage by component:

**Retrieval Services** (High Priority)
- Vietnamese Processor: 100%
- RRF Fusion: 100%
- Query Extraction: 95%
- Reranker: 95%
- Hybrid Retrieval: 90%
- Orchestrator: 85%

**Content Services**
- Chunking: 85%
- Embedding: 80%

**Crawler Services**
- RSS Service: 90%
- Scraper: 85%

**Repository Layer**
- News Source: 95%
- RSS Feed: 95%

**API Layer**
- Health: 100%
- Verification: 75%

**Coverage Goals**: >80% overall, >90% for critical services

## Running Specific Tests

```bash
# Vietnamese processor tests
pytest tests/unit/services/retrieval/test_vietnamese_processor.py

# RRF fusion tests
pytest tests/unit/services/retrieval/test_fusion_service.py

# Orchestrator tests
pytest tests/unit/services/retrieval/test_retrieval_orchestrator.py

# API tests
pytest tests/unit/api/

# Integration tests
pytest tests/integration/services/retrieval/
```

## Troubleshooting

### Import Errors

```bash
# Ensure you're in backend directory
cd backend

# Sync dependencies
uv sync

# Run with PYTHONPATH
PYTHONPATH=. pytest tests/
```

### Slow Tests

```bash
# Skip slow tests
pytest tests/ -m "not slow"

# Show slowest tests
pytest tests/ --durations=10
```

### Database/Redis Errors

Tests use in-memory SQLite and FakeRedis by default. No external services required for unit tests.

## CI/CD

Tests run automatically on:
- Every commit (unit tests)
- Pull requests (unit + integration)
- Main branch (full suite + performance)

## Contributing

When adding tests:
1. Follow existing structure and naming conventions
2. Use appropriate markers (`@pytest.mark.unit`, etc.)
3. Write descriptive test names and docstrings
4. Aim for >80% coverage of new code
5. Run tests locally before committing

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [Coverage.py](https://coverage.readthedocs.io/)
