"""
Unit tests for verification serialization helpers.

The standard and streaming endpoints share these helpers to cache a verification
result and rebuild it on a cache hit. The key guarantee is a lossless round-trip
(serialize -> cache dict -> reconstruct) so the two endpoints cannot drift.
"""

import pytest

from app.api._verification_serde import (
    build_cache_hit_response,
    build_fresh_response,
    verification_result_from_cache_dict,
    verification_result_to_cache_dict,
)
from app.schemas.verification import (
    ClaimVerdictSchema,
    ClaimVerdictType,
    EvidenceSpan,
    OverallVerdictType,
    StanceResultSchema,
    StanceType,
    VerificationConfidenceMetricsSchema,
    VerificationResultSchema,
)


def _full_result() -> VerificationResultSchema:
    """A verification result exercising nested evidence + enums + metrics."""
    evidence = StanceResultSchema(
        claim_text="VinTech xây nhà máy",
        article_id="123e4567-e89b-12d3-a456-426614174000",
        article_title="VinTech công bố nhà máy",
        article_url="https://vnexpress.net/a",
        source_name="VnExpress",
        published_at="2024-01-15T10:00:00",
        stance=StanceType.SUPPORTS,
        confidence=0.9,
        evidence_spans=[EvidenceSpan(text="trích dẫn", reasoning="lý do")],
        overall_reasoning="ủng hộ",
    )
    return VerificationResultSchema(
        verdict=OverallVerdictType.FULLY_SUPPORTED,
        confidence=0.85,
        reason=None,
        explanation="Tất cả luận điểm được xác nhận",
        claim_verdicts=[
            ClaimVerdictSchema(
                claim_text="VinTech xây nhà máy",
                verdict=ClaimVerdictType.SUPPORTED,
                confidence=0.9,
                supporting_evidence=[evidence],
                refuting_evidence=[],
            )
        ],
        total_claims=1,
        supported_claims=1,
        refuted_claims=0,
        sources_used=["VnExpress"],
        confidence_metrics=VerificationConfidenceMetricsSchema(
            overall_confidence=0.85,
            evidence_quality=0.88,
            source_agreement=1.0,
            source_quantity=0.2,
            temporal_relevance=0.7,
        ),
    )


@pytest.mark.unit
class TestVerificationResultRoundTrip:
    def test_round_trip_preserves_all_fields(self):
        original = _full_result()
        rebuilt = verification_result_from_cache_dict(
            verification_result_to_cache_dict(original)
        )
        # Model equality covers verdict enum, nested evidence spans, and metrics.
        assert rebuilt == original

    def test_enums_serialize_to_values(self):
        cache_dict = verification_result_to_cache_dict(_full_result())
        assert cache_dict["verdict"] == "FULLY_SUPPORTED"
        assert cache_dict["claim_verdicts"][0]["verdict"] == "SUPPORTED"
        assert (
            cache_dict["claim_verdicts"][0]["supporting_evidence"][0]["stance"]
            == "SUPPORTS"
        )

    def test_none_result_round_trips_to_none(self):
        assert verification_result_to_cache_dict(None) is None
        assert verification_result_from_cache_dict(None) is None


@pytest.mark.unit
class TestResponseBuilders:
    def test_cache_hit_response_marks_cache_hit_and_rebuilds_verification(self):
        cached = {
            "articles": [{"article_id": "x", "title": "t"}],
            "stage_timings": {"query_extraction": 1.0},
            "query_count": 2,
            "verification_result": verification_result_to_cache_dict(_full_result()),
            "factual_confidence": 3,
            "retrieval_confidence": 0.7,
            "confidence_metrics": None,
            "low_confidence_warning": False,
        }
        resp = build_cache_hit_response(cached, elapsed_ms=12)
        assert resp.cache_hit is True
        assert resp.total_time_ms == 12
        assert resp.query_count == 2
        assert resp.verification.verdict == OverallVerdictType.FULLY_SUPPORTED

    def test_fresh_response_marks_not_cache_hit(self):
        result = {
            "query_count": 1,
            "factual_confidence": 3,
            "retrieval_confidence": 0.5,
            "confidence_metrics": None,
            "low_confidence_warning": False,
            "early_exit": False,
            "exit_reason": None,
            "message": None,
        }
        resp = build_fresh_response(
            result,
            articles_dict=[],
            verification_result=_full_result(),
            stage_timings={"query_extraction": 1.0},
            elapsed_ms=99,
        )
        assert resp.cache_hit is False
        assert resp.total_time_ms == 99
        assert resp.verification.supported_claims == 1
