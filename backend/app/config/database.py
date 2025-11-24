"""
Database Configuration Module

Provides async database engine, session management, and dependency injection for FastAPI.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.logging import get_logger
from app.config.settings import settings


logger = get_logger(__name__)


# Create async engine (main database connection pool)
# Note: For async I/O-bound apps, fewer connections are needed since
# the event loop handles concurrency while waiting for external APIs (OpenAI).
# Most request time is spent on OpenAI calls, not DB queries.
engine = create_async_engine(
    url=settings.POSTGRES_URL,
    echo=False,  # Set to True for SQL query logging
    pool_pre_ping=True,  # Verify connections before using them
    pool_size=3,  # Base connections per worker (async apps need fewer)
    max_overflow=2,  # Small overflow buffer for burst traffic
)

# Create session factory to manage database sessions
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Don't expire objects after commit
    autoflush=False,  # Manual control over flushing
    autocommit=False,  # Manual control over commits
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a database session

    Yields:
        AsyncSession: Database session for use in route handlers

    Example:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            logger.error(f"Database error occurred: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize database connection (optional startup check)

    This can be called during application startup to verify database connectivity.
    """
    try:
        async with engine.begin():
            logger.info("Database connection established successfully")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise


async def close_db() -> None:
    """
    Close database connections (called during application shutdown)
    """
    await engine.dispose()
    logger.info("Database connections closed")
