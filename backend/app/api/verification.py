"""
Verification API Endpoints

Provides endpoints for verifying Facebook posts using the retrieval pipeline.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.core.logging import get_logger
from app.schemas.verification import (
    ConfidenceMetricsSchema,
    VerificationRequest,
    VerificationResponse,
)
from app.services.cache.retrieval_cache import RetrievalCache
from app.services.retrieval.retrieval_orchestrator import RetrievalOrchestrator
from app.services.verification.verification_service import VerificationService

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

        # Check cache first (unless cache_bypass is True)
        if not request.cache_bypass:
            cached_result = await cache.get(request.text)
            if cached_result:
                logger.info("Returning cached result")
                # For cached results, we still need to run verification
                # since verification results are not cached
                verification_service = VerificationService()
                (
                    verification_result,
                    verification_timings,
                ) = await verification_service.verify(
                    post_text=request.text,
                    claims=cached_result.get("claims", []),
                    articles=cached_result.get("articles", []),
                )

                # Merge timings
                stage_timings = cached_result.get("stage_timings", {})
                stage_timings.update(verification_timings)

                return VerificationResponse(
                    articles=[
                        a.to_dict() if hasattr(a, "to_dict") else a
                        for a in cached_result.get("articles", [])
                    ],
                    total_time_ms=cached_result.get("total_time_ms", 0),
                    stage_timings=stage_timings,
                    query_count=cached_result.get("query_count", 0),
                    verification=verification_result,
                    cache_hit=True,
                    factual_confidence=cached_result.get("factual_confidence"),
                    retrieval_confidence=cached_result.get("retrieval_confidence"),
                    confidence_metrics=ConfidenceMetricsSchema(
                        **cached_result["confidence_metrics"]
                    )
                    if cached_result.get("confidence_metrics")
                    else None,
                    low_confidence_warning=cached_result.get(
                        "low_confidence_warning", False
                    ),
                    early_exit=cached_result.get("early_exit", False),
                    exit_reason=cached_result.get("exit_reason"),
                    message=cached_result.get("message"),
                )
        else:
            logger.info("Cache bypass requested, forcing re-verification")

        # Run retrieval pipeline
        orchestrator = RetrievalOrchestrator(db)
        result = await orchestrator.retrieve(request.text)

        # Cache the result (including claims)
        await cache.set(
            post_text=request.text,
            articles=result["articles"],
            total_time_ms=result["total_time_ms"],
            stage_timings=result["stage_timings"],
            query_count=result["query_count"],
        )

        # Convert ArticleResult objects to dicts
        articles_dict = [article.to_dict() for article in result["articles"]]

        # Run verification pipeline
        verification_service = VerificationService()
        verification_result, verification_timings = await verification_service.verify(
            post_text=request.text,
            claims=result.get("claims", []),
            articles=result["articles"],
        )

        # Merge stage timings
        stage_timings = result["stage_timings"]
        stage_timings.update(verification_timings)

        # Return response with verification result
        return VerificationResponse(
            articles=articles_dict,
            total_time_ms=result["total_time_ms"],
            stage_timings=stage_timings,
            query_count=result["query_count"],
            verification=verification_result,
            cache_hit=False,
            factual_confidence=result.get("factual_confidence"),
            retrieval_confidence=result.get("retrieval_confidence"),
            confidence_metrics=ConfidenceMetricsSchema(**result["confidence_metrics"])
            if result.get("confidence_metrics")
            else None,
            low_confidence_warning=result.get("low_confidence_warning", False),
            early_exit=result.get("early_exit", False),
            exit_reason=result.get("exit_reason"),
            message=result.get("message"),
        )

    except Exception as e:
        logger.error(f"Error during verification: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Verification failed: {str(e)}"
        ) from e
