"""
Verification API Endpoints

Provides endpoints for verifying Facebook posts using the retrieval pipeline.
"""

import time
from typing import Dict
from uuid import UUID, uuid5

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


def _parse_or_generate_uuid(value: str) -> UUID:
    """
    Parse UUID from string or generate a deterministic UUID from invalid string.

    Args:
        value: String to parse as UUID

    Returns:
        UUID object
    """
    if not value:
        return UUID(int=0)

    try:
        return UUID(value)
    except (ValueError, TypeError):
        # Generate deterministic UUID from string hash
        # Using DNS namespace for consistency
        return uuid5(UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8"), value)


def _verification_result_to_dict(verification_result) -> Dict:
    """
    Convert VerificationResultSchema to JSON-serializable dictionary.

    Handles datetime serialization and nested objects.
    """
    if not verification_result:
        return None

    return {
        "verdict": verification_result.verdict.value,
        "confidence": verification_result.confidence,
        "confidence_tier": verification_result.confidence_tier,
        "explanation": verification_result.explanation,
        "claim_verdicts": [
            {
                "claim_text": cv.claim_text,
                "verdict": cv.verdict.value,
                "confidence": cv.confidence,
                "supporting_evidence": [
                    {
                        "claim_text": e.claim_text,
                        "article_id": e.article_id,
                        "article_title": e.article_title,
                        "article_url": e.article_url,
                        "source_name": e.source_name,
                        "published_at": e.published_at,
                        "stance": e.stance.value,
                        "confidence": e.confidence,
                        "evidence_spans": [
                            {"text": span.text, "reasoning": span.reasoning}
                            for span in e.evidence_spans
                        ],
                        "overall_reasoning": e.overall_reasoning,
                    }
                    for e in cv.supporting_evidence
                ],
                "refuting_evidence": [
                    {
                        "claim_text": e.claim_text,
                        "article_id": e.article_id,
                        "article_title": e.article_title,
                        "article_url": e.article_url,
                        "source_name": e.source_name,
                        "published_at": e.published_at,
                        "stance": e.stance.value,
                        "confidence": e.confidence,
                        "evidence_spans": [
                            {"text": span.text, "reasoning": span.reasoning}
                            for span in e.evidence_spans
                        ],
                        "overall_reasoning": e.overall_reasoning,
                    }
                    for e in cv.refuting_evidence
                ],
            }
            for cv in verification_result.claim_verdicts
        ],
        "total_claims": verification_result.total_claims,
        "supported_claims": verification_result.supported_claims,
        "refuted_claims": verification_result.refuted_claims,
        "sources_used": verification_result.sources_used,
        "confidence_metrics": {
            "overall_confidence": verification_result.confidence_metrics.overall_confidence,
            "confidence_tier": verification_result.confidence_metrics.confidence_tier,
            "evidence_quality": verification_result.confidence_metrics.evidence_quality,
            "source_agreement": verification_result.confidence_metrics.source_agreement,
            "claim_coverage": verification_result.confidence_metrics.claim_coverage,
            "temporal_relevance": verification_result.confidence_metrics.temporal_relevance,
        }
        if verification_result.confidence_metrics
        else None,
    }


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
        request_start_time = time.time()

        # Initialize cache
        cache = RetrievalCache()

        # Check cache first (unless cache_bypass is True)
        if not request.cache_bypass:
            cached_result = await cache.get(request.text)
            if cached_result:
                logger.info("Returning cached result")
                # Calculate total time from request start (includes cache lookup only)
                total_elapsed_ms = int((time.time() - request_start_time) * 1000)

                # Reconstruct verification result from cache if available
                cached_verification_dict = cached_result.get("verification_result")
                if cached_verification_dict:
                    # Convert cached dict back to VerificationResultSchema
                    from app.schemas.verification import (
                        VerificationResultSchema,
                        OverallVerdictType,
                        ClaimVerdictSchema,
                        ClaimVerdictType,
                        StanceResultSchema,
                        StanceType,
                        EvidenceSpan,
                        VerificationConfidenceMetricsSchema,
                    )

                    # Reconstruct confidence metrics
                    confidence_metrics = (
                        VerificationConfidenceMetricsSchema(
                            **cached_verification_dict["confidence_metrics"]
                        )
                        if cached_verification_dict.get("confidence_metrics")
                        else None
                    )

                    # Reconstruct claim verdicts
                    claim_verdicts = [
                        ClaimVerdictSchema(
                            claim_text=cv["claim_text"],
                            verdict=ClaimVerdictType(cv["verdict"]),
                            confidence=cv["confidence"],
                            supporting_evidence=[
                                StanceResultSchema(
                                    claim_text=e["claim_text"],
                                    article_id=e["article_id"],
                                    article_title=e["article_title"],
                                    article_url=e["article_url"],
                                    source_name=e["source_name"],
                                    published_at=e.get("published_at"),
                                    stance=StanceType(e["stance"]),
                                    confidence=e["confidence"],
                                    evidence_spans=[
                                        EvidenceSpan(
                                            text=span["text"],
                                            reasoning=span["reasoning"],
                                        )
                                        for span in e.get("evidence_spans", [])
                                    ],
                                    overall_reasoning=e.get("overall_reasoning", ""),
                                )
                                for e in cv.get("supporting_evidence", [])
                            ],
                            refuting_evidence=[
                                StanceResultSchema(
                                    claim_text=e["claim_text"],
                                    article_id=e["article_id"],
                                    article_title=e["article_title"],
                                    article_url=e["article_url"],
                                    source_name=e["source_name"],
                                    published_at=e.get("published_at"),
                                    stance=StanceType(e["stance"]),
                                    confidence=e["confidence"],
                                    evidence_spans=[
                                        EvidenceSpan(
                                            text=span["text"],
                                            reasoning=span["reasoning"],
                                        )
                                        for span in e.get("evidence_spans", [])
                                    ],
                                    overall_reasoning=e.get("overall_reasoning", ""),
                                )
                                for e in cv.get("refuting_evidence", [])
                            ],
                        )
                        for cv in cached_verification_dict.get("claim_verdicts", [])
                    ]

                    verification_result = VerificationResultSchema(
                        verdict=OverallVerdictType(cached_verification_dict["verdict"]),
                        confidence=cached_verification_dict["confidence"],
                        confidence_tier=cached_verification_dict["confidence_tier"],
                        explanation=cached_verification_dict["explanation"],
                        claim_verdicts=claim_verdicts,
                        total_claims=cached_verification_dict["total_claims"],
                        supported_claims=cached_verification_dict["supported_claims"],
                        refuted_claims=cached_verification_dict["refuted_claims"],
                        sources_used=cached_verification_dict.get("sources_used", []),
                        confidence_metrics=confidence_metrics,
                    )
                else:
                    # Fallback: no cached verification, return None
                    verification_result = None

                return VerificationResponse(
                    articles=cached_result.get("articles", []),
                    total_time_ms=total_elapsed_ms,
                    stage_timings=cached_result.get("stage_timings", {}),
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

        # Convert ArticleResult objects to dicts
        articles_dict = [article.to_dict() for article in result["articles"]]

        # Run verification pipeline
        verification_service = VerificationService()
        verification_result, verification_timings = await verification_service.verify(
            post_text=request.text,
            claims=result.get("claims", []),
            articles=result["articles"],
        )

        # Serialize verification result for caching
        verification_result_dict = _verification_result_to_dict(verification_result)

        # Cache the result (including all retrieval and verification metadata)
        await cache.set(
            post_text=request.text,
            articles=result["articles"],
            total_time_ms=result["total_time_ms"],
            stage_timings=result["stage_timings"],
            query_count=result["query_count"],
            claims=result.get("claims", []),
            factual_confidence=result.get("factual_confidence"),
            retrieval_confidence=result.get("retrieval_confidence"),
            confidence_metrics=result.get("confidence_metrics"),
            low_confidence_warning=result.get("low_confidence_warning", False),
            early_exit=result.get("early_exit", False),
            exit_reason=result.get("exit_reason"),
            message=result.get("message"),
            verification_result=verification_result_dict,
        )

        # Merge stage timings
        stage_timings = result["stage_timings"]
        stage_timings.update(verification_timings)

        # Calculate total time from request start (includes retrieval + verification)
        total_elapsed_ms = int((time.time() - request_start_time) * 1000)

        # Return response with verification result
        return VerificationResponse(
            articles=articles_dict,
            total_time_ms=total_elapsed_ms,
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
