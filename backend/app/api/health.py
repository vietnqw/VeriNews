"""
Health Check Endpoints

Provides system health and status information.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.core.logging import get_logger


router = APIRouter()
logger = get_logger(__name__)


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint

    Checks:
    - API is running
    - Database connectivity
    - pgvector extension availability

    Returns:
        dict: Health status information
    """
    health_status = {
        "status": "healthy",
        "api": "running",
        "database": "disconnected",
        "pgvector": "unavailable",
    }

    try:
        # Test database connection
        result = await db.execute(text("SELECT 1"))
        result.scalar()
        health_status["database"] = "connected"

        # Check pgvector extension
        result = await db.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        )
        vector_version = result.scalar()
        if vector_version:
            health_status["pgvector"] = f"available (v{vector_version})"

        logger.debug("Health check passed")
        return health_status

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        health_status["status"] = "unhealthy"
        health_status["error"] = str(e)
        return health_status


@router.get("/health/simple")
async def simple_health_check():
    """
    Simple health check without database dependency

    Returns:
        dict: Basic health status
    """
    return {"status": "ok"}
