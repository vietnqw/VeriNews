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

### Implemented Tests (Phase 1-2)

✅ **Test Infrastructure**
- Pytest configuration
- Shared fixtures (conftest.py)
- Mock services (OpenAI, Redis)
- Test data factories

✅ **Vietnamese Processor** (20 tests)
- Compound word tokenization
- Special characters handling
- Mixed language support
- Edge cases (empty, whitespace, Unicode)
- Configuration toggle

✅ **RRF Fusion Service** (10 tests)
- Single/multiple list fusion
- Overlapping chunks
- Different k values
- Mathematical correctness
- Empty lists handling
- Metadata preservation

### Upcoming Tests (Phases 3-6)

🚧 **Search Services**
- Vector similarity search
- BM25 keyword search
- Hybrid retrieval coordination

🚧 **LLM Services**
- Query extraction
- Batch reranking

🚧 **Integration Tests**
- Full pipeline E2E
- Database integration
- OpenAI API integration
- Redis caching

🚧 **Performance Tests**
- Latency benchmarks
- Throughput tests
- Scalability tests

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
