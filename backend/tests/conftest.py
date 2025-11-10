"""
Pytest configuration and shared fixtures for VeriNews test suite.

This module provides fixtures for:
- Database sessions (async and sync)
- Mock external services (OpenAI, Redis)
- Test data factories
- Common test utilities
"""

import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
import fakeredis.aioredis
from faker import Faker
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.config.settings import settings

# Initialize Faker for test data generation
fake = Faker(["vi_VN"])  # Vietnamese locale


# ==================== Database Fixtures ====================


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the entire test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide an async database session for tests.

    Uses an in-memory SQLite database that is created and torn down
    for each test function to ensure test isolation.
    """
    # Create async engine with in-memory SQLite
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()

    # Drop all tables and dispose engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="function")
def sync_db_session() -> Generator[Session, None, None]:
    """
    Provide a sync database session for tests that don't require async.

    Uses an in-memory SQLite database.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    yield session

    session.rollback()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


# ==================== Mock External Services ====================


@pytest.fixture
def mock_redis():
    """Provide a fake Redis client for testing."""
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture
def mock_openai_embeddings():
    """
    Mock OpenAI embeddings API responses.

    Returns a mock that provides realistic embedding vectors (1536 dimensions).
    """
    mock = AsyncMock()

    # Mock embedding response
    mock_embedding = [0.1] * 1536  # Dummy 1536-dimensional vector

    mock.embeddings.create = AsyncMock(
        return_value=MagicMock(
            data=[MagicMock(embedding=mock_embedding)],
            model="text-embedding-3-small",
            usage=MagicMock(prompt_tokens=10, total_tokens=10),
        )
    )

    return mock


@pytest.fixture
def mock_openai_completions():
    """
    Mock OpenAI chat completions API responses.

    Returns a mock that provides realistic JSON-mode completions.
    """
    mock = AsyncMock()

    # Mock completion response with JSON
    def create_completion(**kwargs):
        # Extract model and messages to generate appropriate response
        messages = kwargs.get("messages", [])

        # Default JSON response for query extraction
        json_content = '{"clean_query": "Test query", "claims": ["Claim 1", "Claim 2"]}'

        # Check if it's a reranking request (contains "scores")
        if messages and "scores" in str(messages).lower():
            json_content = '{"scores": [0.9, 0.8, 0.7, 0.6, 0.5]}'

        return MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(content=json_content),
                    finish_reason="stop",
                )
            ],
            model=kwargs.get("model", "gpt-4o-mini"),
            usage=MagicMock(
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
            ),
        )

    mock.chat.completions.create = AsyncMock(side_effect=create_completion)

    return mock


@pytest.fixture
def mock_openai_client(mock_openai_embeddings, mock_openai_completions):
    """Provide a complete mock OpenAI client."""
    mock = MagicMock()
    mock.embeddings = mock_openai_embeddings.embeddings
    mock.chat = mock_openai_completions.chat
    return mock


# ==================== Test Data Factories ====================


@pytest.fixture
def sample_vietnamese_post():
    """Generate a sample Vietnamese Facebook post."""
    return "VinTech xây nhà máy 5 tỷ USD ở Hà Nội!!! Tuyệt vời 🎉🎉"


@pytest.fixture
def sample_clean_query():
    """Generate a cleaned query."""
    return "VinTech xây dựng nhà máy trị giá 5 tỷ USD tại Hà Nội"


@pytest.fixture
def sample_claims():
    """Generate sample extracted claims."""
    return [
        "VinTech xây dựng nhà máy tại Hà Nội",
        "Nhà máy có giá trị 5 tỷ USD",
        "Nhà máy được xây dựng năm 2024",
    ]


@pytest.fixture
def sample_embedding():
    """Generate a sample embedding vector (1536 dimensions)."""
    return [0.1 * i for i in range(1536)]


@pytest.fixture
def sample_chunk_text():
    """Generate sample article chunk text."""
    return """
    VinGroup công bố kế hoạch xây dựng nhà máy sản xuất chip bán dẫn
    tại Hà Nội với tổng vốn đầu tư 5 tỷ USD. Dự án dự kiến khởi công
    vào quý 2/2024 và hoàn thành vào năm 2026.
    """


# ==================== Configuration Fixtures ====================


@pytest.fixture
def test_settings():
    """Provide test-specific settings."""
    return settings


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests."""
    from app.services.ai.factory import AIServiceFactory

    AIServiceFactory.clear_cache()
    yield


# ==================== Utility Fixtures ====================


@pytest.fixture
def assert_timing():
    """Utility to assert execution time is within acceptable bounds."""
    import time

    class TimingAssertion:
        def __init__(self):
            self.start_time = None

        def start(self):
            self.start_time = time.time()

        def assert_less_than(self, max_seconds: float, message: str = ""):
            elapsed = time.time() - self.start_time
            assert elapsed < max_seconds, (
                f"{message} (took {elapsed:.2f}s, max {max_seconds}s)"
            )

    return TimingAssertion()


# ==================== Integration Test Fixtures (PostgreSQL + Redis) ====================


@pytest.fixture(scope="session")
async def postgres_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide an async database session connected to PostgreSQL (Docker).

    This fixture connects to the actual PostgreSQL database running in Docker
    and is used for integration tests that require PostgreSQL-specific features
    like pgvector, tsvector, etc.

    Requires Docker services to be running:
        docker compose -f docker/docker-compose.yml up -d
    """
    from app.config.database import engine

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()

    # Clean up: drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="session")
def postgres_tables_setup():
    """
    Create PostgreSQL tables once per test session (synchronous).

    This runs before any async tests to avoid event loop issues.
    """
    from sqlalchemy import create_engine as sync_create_engine
    from app.config.settings import settings

    # Use synchronous engine for table creation
    sync_engine = sync_create_engine(settings.POSTGRES_URL_SYNC)

    # Create all tables
    Base.metadata.create_all(sync_engine)

    yield

    # Cleanup: drop all tables after all tests
    Base.metadata.drop_all(sync_engine)
    sync_engine.dispose()


@pytest.fixture(scope="function")
async def postgres_session(postgres_tables_setup) -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a PostgreSQL session for individual integration tests.

    Creates a fresh async engine per test to avoid event loop issues.
    Tables are created once per session (sync), this just provides
    a clean session for each test and cleans up data afterwards.
    """
    from sqlalchemy import text
    from app.config.settings import settings

    # Create a new async engine for this test (avoids event loop issues)
    test_engine = create_async_engine(
        url=settings.POSTGRES_URL,
        echo=False,
        pool_pre_ping=True,
    )

    # Create session
    async_session_maker = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        yield session

        # Cleanup: delete all data after test
        try:
            await session.execute(text("TRUNCATE TABLE article_chunks CASCADE"))
            await session.execute(text("TRUNCATE TABLE articles CASCADE"))
            await session.execute(text("TRUNCATE TABLE rss_feeds CASCADE"))
            await session.execute(text("TRUNCATE TABLE news_sources CASCADE"))
            await session.commit()
        except Exception:
            await session.rollback()

    # Dispose engine after test
    await test_engine.dispose()


@pytest.fixture(scope="function")
async def real_redis():
    """
    Provide a connection to actual Redis (Docker).

    This fixture connects to the real Redis instance running in Docker
    for integration tests that need actual Redis behavior.

    Requires Docker services to be running:
        docker compose -f docker/docker-compose.yml up -d
    """
    import redis.asyncio as redis

    client = await redis.from_url(
        f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}",
        encoding="utf-8",
        decode_responses=True,
    )

    yield client

    # Cleanup: flush all keys created during test
    await client.flushall()
    await client.close()


# ==================== Markers ====================


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test (requires Docker)"
    )
    config.addinivalue_line("markers", "performance: mark test as a performance test")
    config.addinivalue_line(
        "markers", "requires_postgres: mark test as requiring PostgreSQL"
    )
    config.addinivalue_line("markers", "requires_redis: mark test as requiring Redis")
    config.addinivalue_line(
        "markers", "requires_openai: mark test as requiring OpenAI API"
    )
