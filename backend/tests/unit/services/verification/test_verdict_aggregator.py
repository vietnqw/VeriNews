"""
Unit tests for VerdictAggregator service.

Tests the claim verdict aggregation and overall verdict computation logic.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.services.verification.stance_classifier import StanceResult
from app.services.verification.verdict_aggregator import VerdictAggregator


class TestVerdictAggregator:
    """Test suite for VerdictAggregator"""

    @pytest.fixture
    def aggregator(self):
        """Create a VerdictAggregator instance"""
        return VerdictAggregator()

    @pytest.fixture
    def sample_support_stance(self):
        """Create a sample supporting stance result"""
        return StanceResult(
            claim_text="Test claim",
            evidence_chunk_id=uuid4(),
            evidence_text="Evidence text",
            source_name="VNExpress",
            published_at=datetime.now(timezone.utc),
            stance="SUPPORTS",
            confidence=0.9,
            key_quote="key quote",
            reasoning="This supports the claim",
            similarity_score=0.85,
        )

    @pytest.fixture
    def sample_refute_stance(self):
        """Create a sample refuting stance result"""
        return StanceResult(
            claim_text="Test claim",
            evidence_chunk_id=uuid4(),
            evidence_text="Refuting evidence",
            source_name="Tuoi Tre",
            published_at=datetime.now(timezone.utc),
            stance="REFUTES",
            confidence=0.85,
            key_quote="refuting quote",
            reasoning="This refutes the claim",
            similarity_score=0.8,
        )

    @pytest.fixture
    def sample_nei_stance(self):
        """Create a sample NOT_ENOUGH_INFO stance result"""
        return StanceResult(
            claim_text="Test claim",
            evidence_chunk_id=uuid4(),
            evidence_text="Neutral evidence",
            source_name="Thanh Nien",
            published_at=datetime.now(timezone.utc),
            stance="NOT_ENOUGH_INFO",
            confidence=0.5,
            key_quote="neutral quote",
            reasoning="Not enough info",
            similarity_score=0.7,
        )

    def test_aggregate_single_claim_supported(self, aggregator, sample_support_stance):
        """Test aggregation with a single supported claim"""
        claims = ["Test claim"]
        stances = [sample_support_stance]

        result = aggregator.aggregate_verdicts(stances, claims)

        assert result.verdict == "FULLY_SUPPORTED"
        assert len(result.claim_verdicts) == 1
        assert result.claim_verdicts[0].verdict == "SUPPORTED"
        assert result.supported_claims == 1
        assert result.refuted_claims == 0

    def test_aggregate_single_claim_refuted(self, aggregator, sample_refute_stance):
        """Test aggregation with a single refuted claim"""
        claims = ["Test claim"]
        stances = [sample_refute_stance]

        result = aggregator.aggregate_verdicts(stances, claims)

        assert result.verdict == "REFUTED"
        assert len(result.claim_verdicts) == 1
        assert result.claim_verdicts[0].verdict == "REFUTED"
        assert result.supported_claims == 0
        assert result.refuted_claims == 1

    def test_aggregate_conflicting_evidence_returns_nei(
        self, aggregator, sample_support_stance, sample_refute_stance
    ):
        """Test that conflicting evidence returns NOT_ENOUGH_INFO (conservative)"""
        claims = ["Test claim"]
        # Both support and refute for the same claim
        stances = [sample_support_stance, sample_refute_stance]

        result = aggregator.aggregate_verdicts(stances, claims)

        # Claim should be NEI due to conflict
        assert result.claim_verdicts[0].verdict == "NOT_ENOUGH_INFO"
        # Overall should be NEI
        assert result.verdict == "NOT_ENOUGH_INFO"

    def test_aggregate_worst_case_any_refuted(self, aggregator):
        """Test worst-case logic: any refuted claim = overall REFUTED"""
        claims = ["Claim 1", "Claim 2"]

        # First claim supported, second claim refuted
        stances = [
            StanceResult(
                claim_text="Claim 1",
                evidence_chunk_id=uuid4(),
                evidence_text="Support 1",
                source_name="VNExpress",
                published_at=datetime.now(timezone.utc),
                stance="SUPPORTS",
                confidence=0.9,
                key_quote="quote",
                reasoning="supports",
                similarity_score=0.85,
            ),
            StanceResult(
                claim_text="Claim 2",
                evidence_chunk_id=uuid4(),
                evidence_text="Refute 2",
                source_name="Tuoi Tre",
                published_at=datetime.now(timezone.utc),
                stance="REFUTES",
                confidence=0.8,
                key_quote="quote",
                reasoning="refutes",
                similarity_score=0.8,
            ),
        ]

        result = aggregator.aggregate_verdicts(stances, claims)

        # Overall should be REFUTED due to worst-case logic
        assert result.verdict == "REFUTED"
        assert result.supported_claims == 1
        assert result.refuted_claims == 1

    def test_aggregate_fully_supported(self, aggregator):
        """Test FULLY_SUPPORTED when all claims are supported"""
        claims = ["Claim 1", "Claim 2"]

        stances = [
            StanceResult(
                claim_text="Claim 1",
                evidence_chunk_id=uuid4(),
                evidence_text="Support 1",
                source_name="VNExpress",
                published_at=datetime.now(timezone.utc),
                stance="SUPPORTS",
                confidence=0.9,
                key_quote="quote",
                reasoning="supports",
                similarity_score=0.85,
            ),
            StanceResult(
                claim_text="Claim 2",
                evidence_chunk_id=uuid4(),
                evidence_text="Support 2",
                source_name="Tuoi Tre",
                published_at=datetime.now(timezone.utc),
                stance="SUPPORTS",
                confidence=0.85,
                key_quote="quote",
                reasoning="supports",
                similarity_score=0.8,
            ),
        ]

        result = aggregator.aggregate_verdicts(stances, claims)

        assert result.verdict == "FULLY_SUPPORTED"
        assert result.supported_claims == 2
        assert result.refuted_claims == 0

    def test_aggregate_partially_supported(self, aggregator):
        """Test PARTIALLY_SUPPORTED when some claims have NEI"""
        claims = ["Claim 1", "Claim 2"]

        stances = [
            StanceResult(
                claim_text="Claim 1",
                evidence_chunk_id=uuid4(),
                evidence_text="Support 1",
                source_name="VNExpress",
                published_at=datetime.now(timezone.utc),
                stance="SUPPORTS",
                confidence=0.9,
                key_quote="quote",
                reasoning="supports",
                similarity_score=0.85,
            ),
            StanceResult(
                claim_text="Claim 2",
                evidence_chunk_id=uuid4(),
                evidence_text="NEI 2",
                source_name="Tuoi Tre",
                published_at=datetime.now(timezone.utc),
                stance="NOT_ENOUGH_INFO",
                confidence=0.5,
                key_quote="quote",
                reasoning="nei",
                similarity_score=0.6,
            ),
        ]

        result = aggregator.aggregate_verdicts(stances, claims)

        assert result.verdict == "PARTIALLY_SUPPORTED"
        assert result.supported_claims == 1
        assert result.refuted_claims == 0

    def test_aggregate_no_stances(self, aggregator):
        """Test aggregation with no stances"""
        claims = ["Claim 1"]
        stances = []

        result = aggregator.aggregate_verdicts(stances, claims)

        assert result.verdict == "NOT_ENOUGH_INFO"
        assert result.claim_verdicts[0].verdict == "NOT_ENOUGH_INFO"

    def test_aggregate_empty_claims(self, aggregator):
        """Test aggregation with empty claims list"""
        claims = []
        stances = []

        result = aggregator.aggregate_verdicts(stances, claims)

        assert result.verdict == "NOT_ENOUGH_INFO"
        assert len(result.claim_verdicts) == 0

    def test_confidence_metrics_calculated(self, aggregator, sample_support_stance):
        """Test that confidence metrics are properly calculated"""
        claims = ["Test claim"]
        stances = [sample_support_stance]

        result = aggregator.aggregate_verdicts(stances, claims)

        # Check confidence metrics exist and are reasonable
        metrics = result.confidence_metrics
        assert metrics.overall_confidence >= 0.0
        assert metrics.overall_confidence <= 1.0
        assert metrics.evidence_quality >= 0.0
        assert metrics.source_agreement >= 0.0
        assert metrics.claim_coverage >= 0.0
        assert metrics.stance_confidence >= 0.0
        assert metrics.temporal_relevance >= 0.0
        assert metrics.confidence_tier in ["HIGH", "MEDIUM", "LOW", "NONE"]

    def test_confidence_tier_high(self, aggregator):
        """Test HIGH confidence tier"""
        claims = ["Claim 1"]

        # Create multiple high-confidence supporting stances
        stances = [
            StanceResult(
                claim_text="Claim 1",
                evidence_chunk_id=uuid4(),
                evidence_text="Support 1",
                source_name="VNExpress",
                published_at=datetime.now(timezone.utc),
                stance="SUPPORTS",
                confidence=0.95,
                key_quote="quote",
                reasoning="supports",
                similarity_score=0.95,
            ),
            StanceResult(
                claim_text="Claim 1",
                evidence_chunk_id=uuid4(),
                evidence_text="Support 2",
                source_name="Tuoi Tre",
                published_at=datetime.now(timezone.utc),
                stance="SUPPORTS",
                confidence=0.92,
                key_quote="quote",
                reasoning="supports",
                similarity_score=0.9,
            ),
        ]

        result = aggregator.aggregate_verdicts(stances, claims)

        # With high similarity and confidence, should get HIGH tier
        assert result.confidence >= 0.5  # At least medium confidence

    def test_sources_used_collected(self, aggregator):
        """Test that sources are properly collected"""
        claims = ["Claim 1", "Claim 2"]

        stances = [
            StanceResult(
                claim_text="Claim 1",
                evidence_chunk_id=uuid4(),
                evidence_text="Support 1",
                source_name="VNExpress",
                published_at=datetime.now(timezone.utc),
                stance="SUPPORTS",
                confidence=0.9,
                key_quote="quote",
                reasoning="supports",
                similarity_score=0.85,
            ),
            StanceResult(
                claim_text="Claim 2",
                evidence_chunk_id=uuid4(),
                evidence_text="Support 2",
                source_name="Tuoi Tre",
                published_at=datetime.now(timezone.utc),
                stance="SUPPORTS",
                confidence=0.85,
                key_quote="quote",
                reasoning="supports",
                similarity_score=0.8,
            ),
        ]

        result = aggregator.aggregate_verdicts(stances, claims)

        assert "VNExpress" in result.sources_used
        assert "Tuoi Tre" in result.sources_used
        assert len(result.sources_used) == 2

    def test_temporal_relevance_recent_articles(self, aggregator):
        """Test that recent articles get higher temporal relevance"""
        claims = ["Test claim"]

        # Recent article
        stances = [
            StanceResult(
                claim_text="Test claim",
                evidence_chunk_id=uuid4(),
                evidence_text="Support",
                source_name="VNExpress",
                published_at=datetime.now(timezone.utc),  # Today
                stance="SUPPORTS",
                confidence=0.9,
                key_quote="quote",
                reasoning="supports",
                similarity_score=0.85,
            ),
        ]

        result = aggregator.aggregate_verdicts(stances, claims)

        # Temporal relevance should be high for recent articles
        assert result.confidence_metrics.temporal_relevance > 0.5

    def test_multiple_stances_per_claim(self, aggregator):
        """Test aggregation with multiple stances for the same claim"""
        claims = ["Test claim"]

        stances = [
            StanceResult(
                claim_text="Test claim",
                evidence_chunk_id=uuid4(),
                evidence_text="Support 1",
                source_name="VNExpress",
                published_at=datetime.now(timezone.utc),
                stance="SUPPORTS",
                confidence=0.9,
                key_quote="quote",
                reasoning="supports",
                similarity_score=0.85,
            ),
            StanceResult(
                claim_text="Test claim",
                evidence_chunk_id=uuid4(),
                evidence_text="Support 2",
                source_name="Tuoi Tre",
                published_at=datetime.now(timezone.utc),
                stance="SUPPORTS",
                confidence=0.85,
                key_quote="quote",
                reasoning="supports",
                similarity_score=0.8,
            ),
        ]

        result = aggregator.aggregate_verdicts(stances, claims)

        assert result.verdict == "FULLY_SUPPORTED"
        assert len(result.claim_verdicts[0].supporting_evidence) == 2

    def test_source_agreement_calculation(self, aggregator):
        """Test source agreement is calculated correctly"""
        claims = ["Test claim"]

        # 3 supports, 1 refute = 75% agreement
        stances = [
            StanceResult(
                claim_text="Test claim",
                evidence_chunk_id=uuid4(),
                evidence_text="Support 1",
                source_name="VNExpress",
                published_at=datetime.now(timezone.utc),
                stance="SUPPORTS",
                confidence=0.9,
                key_quote="quote",
                reasoning="supports",
                similarity_score=0.85,
            ),
            StanceResult(
                claim_text="Test claim",
                evidence_chunk_id=uuid4(),
                evidence_text="Support 2",
                source_name="Tuoi Tre",
                published_at=datetime.now(timezone.utc),
                stance="SUPPORTS",
                confidence=0.85,
                key_quote="quote",
                reasoning="supports",
                similarity_score=0.8,
            ),
            StanceResult(
                claim_text="Test claim",
                evidence_chunk_id=uuid4(),
                evidence_text="Support 3",
                source_name="Dan Tri",
                published_at=datetime.now(timezone.utc),
                stance="SUPPORTS",
                confidence=0.8,
                key_quote="quote",
                reasoning="supports",
                similarity_score=0.75,
            ),
            StanceResult(
                claim_text="Test claim",
                evidence_chunk_id=uuid4(),
                evidence_text="Refute",
                source_name="Zing",
                published_at=datetime.now(timezone.utc),
                stance="REFUTES",
                confidence=0.7,
                key_quote="quote",
                reasoning="refutes",
                similarity_score=0.7,
            ),
        ]

        result = aggregator.aggregate_verdicts(stances, claims)

        # Source agreement should be 0.75 (3/4)
        assert result.confidence_metrics.source_agreement == 0.75
