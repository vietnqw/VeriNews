"""
Verification API Endpoints

Provides endpoints for verifying Facebook posts using the retrieval pipeline.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.core.logging import get_logger
from app.schemas.verification import (
    DummyVerificationResult,
    VerificationRequest,
    VerificationResponse,
)
from app.services.cache.retrieval_cache import RetrievalCache
from app.services.retrieval.retrieval_orchestrator import RetrievalOrchestrator

logger = get_logger(__name__)

router = APIRouter(prefix="/verify", tags=["verification"])


@router.post("", response_model=VerificationResponse)
async def verify_post(
    request: VerificationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify a Facebook post by retrieving relevant articles.

    This endpoint runs the full two-stage hybrid retrieval pipeline:
    1. Query extraction (clean query + claims)
    2. Batch embedding generation
    3. Multi-query hybrid search (vector + BM25)
    4. Reciprocal Rank Fusion
    5. LLM-based reranking
    6. Article aggregation

    Returns relevant articles with timing breakdowns.
    Verification logic returns dummy result for now.

    Args:
        request: VerificationRequest with post text
        db: Database session (dependency injection)

    Returns:
        VerificationResponse with articles, timings, and dummy verification
    """
    try:
        logger.info(f"Verification request received: {request.text[:100]}...")

        # Initialize cache
        cache = RetrievalCache()

        # Check cache first
        cached_result = await cache.get(request.text)
        if cached_result:
            logger.info("Returning cached result")
            return VerificationResponse(
                **cached_result,
                verification=DummyVerificationResult(),
                cache_hit=True,
            )

        # Run retrieval pipeline
        orchestrator = RetrievalOrchestrator(db)
        result = await orchestrator.retrieve(request.text)

        # Cache the result
        await cache.set(
            post_text=request.text,
            articles=result["articles"],
            total_time_ms=result["total_time_ms"],
            stage_timings=result["stage_timings"],
            query_count=result["query_count"],
        )

        # Convert ArticleResult objects to dicts
        articles_dict = [article.to_dict() for article in result["articles"]]

        # Return response with dummy verification
        return VerificationResponse(
            articles=articles_dict,
            total_time_ms=result["total_time_ms"],
            stage_timings=result["stage_timings"],
            query_count=result["query_count"],
            verification=DummyVerificationResult(),
            cache_hit=False,
        )

    except Exception as e:
        logger.error(f"Error during verification: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Verification failed: {str(e)}"
        ) from e
