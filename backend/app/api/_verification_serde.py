"""
Serialization helpers for the verification endpoint.

Both the standard and streaming handlers cache a verification result and build a
`VerificationResponse` from either a cache hit or a fresh pipeline run. These
helpers centralize that (previously duplicated ~200 lines) so the two code paths
cannot drift apart.

The verification result is a Pydantic model, so caching is just ``model_dump`` and
reconstruction is just model construction (Pydantic v2 coerces enum values and
nested dicts) — no hand-written field-by-field mapping is needed.
"""

from typing import Optional

from app.schemas.verification import (
    ConfidenceMetricsSchema,
    VerificationResponse,
    VerificationResultSchema,
)


def verification_result_to_cache_dict(
    result: Optional[VerificationResultSchema],
) -> Optional[dict]:
    """Serialize a verification result to a JSON-safe dict for caching."""
    return result.model_dump(mode="json") if result else None


def verification_result_from_cache_dict(
    data: Optional[dict],
) -> Optional[VerificationResultSchema]:
    """Reconstruct a verification result from its cached dict."""
    return VerificationResultSchema(**data) if data else None


def _confidence_metrics(data: Optional[dict]) -> Optional[ConfidenceMetricsSchema]:
    return ConfidenceMetricsSchema(**data) if data else None


def build_cache_hit_response(
    cached_result: dict, elapsed_ms: int
) -> VerificationResponse:
    """Build the response returned for a cache hit."""
    return VerificationResponse(
        articles=cached_result.get("articles", []),
        total_time_ms=elapsed_ms,
        stage_timings=cached_result.get("stage_timings", {}),
        query_count=cached_result.get("query_count", 0),
        verification=verification_result_from_cache_dict(
            cached_result.get("verification_result")
        ),
        cache_hit=True,
        factual_confidence=cached_result.get("factual_confidence"),
        retrieval_confidence=cached_result.get("retrieval_confidence"),
        confidence_metrics=_confidence_metrics(cached_result.get("confidence_metrics")),
        low_confidence_warning=cached_result.get("low_confidence_warning", False),
        early_exit=cached_result.get("early_exit", False),
        exit_reason=cached_result.get("exit_reason"),
        message=cached_result.get("message"),
    )


def build_fresh_response(
    result: dict,
    articles_dict: list,
    verification_result: Optional[VerificationResultSchema],
    stage_timings: dict,
    elapsed_ms: int,
) -> VerificationResponse:
    """Build the response returned for a freshly computed (uncached) result."""
    return VerificationResponse(
        articles=articles_dict,
        total_time_ms=elapsed_ms,
        stage_timings=stage_timings,
        query_count=result["query_count"],
        verification=verification_result,
        cache_hit=False,
        factual_confidence=result.get("factual_confidence"),
        retrieval_confidence=result.get("retrieval_confidence"),
        confidence_metrics=_confidence_metrics(result.get("confidence_metrics")),
        low_confidence_warning=result.get("low_confidence_warning", False),
        early_exit=result.get("early_exit", False),
        exit_reason=result.get("exit_reason"),
        message=result.get("message"),
    )
