"""
Unit tests for VerdictAggregator service.

Tests the claim verdict aggregation and overall verdict computation logic.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.services.verification.stance_classifier import EvidenceSpan, StanceResult
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
            article_id=uuid4(),
            article_title="Test Article",
            article_url="https://example.com/article",
            source_name="VNExpress",
            published_at=datetime.now(timezone.utc),
            stance="SUPPORTS",
            confidence=0.9,
            evidence_spans=[
                EvidenceSpan(text="key quote", reasoning="This supports the claim")
            ],
            overall_reasoning="This article supports the claim",
        )

    @pytest.fixture
    def sample_refute_stance(self):
        """Create a sample refuting stance result"""
        return StanceResult(
            claim_text="Test claim",
            article_id=uuid4(),
            article_title="Refuting Article",
            article_url="https://example.com/refute",
            source_name="Tuoi Tre",
            published_at=datetime.now(timezone.utc),
            stance="REFUTES",
            confidence=0.85,
            evidence_spans=[
                EvidenceSpan(text="refuting quote", reasoning="This refutes the claim")
            ],
            overall_reasoning="This article refutes the claim",
        )

    @pytest.fixture
    def sample_nei_stance(self):
        """Create a sample NOT_ENOUGH_INFO stance result"""
        return StanceResult(
            claim_text="Test claim",
            article_id=uuid4(),
            article_title="Neutral Article",
            article_url="https://example.com/neutral",
            source_name="Thanh Nien",
            published_at=datetime.now(timezone.utc),
            stance="NOT_ENOUGH_INFO",
            confidence=0.5,
            evidence_spans=[
                EvidenceSpan(text="neutral quote", reasoning="Not enough info")
            ],
            overall_reasoning="Not enough information to determine stance",
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
        assert result.claim_verdicts[0].reason == "CONFLICTING_SOURCES"
        # Overall should be NEI
        assert result.verdict == "NOT_ENOUGH_INFO"
        assert result.reason == "CONFLICTING_SOURCES"
        assert result.confidence is None
        assert result.confidence_metrics is None

    def test_aggregate_worst_case_any_refuted(self, aggregator):
        """Test worst-case logic: any refuted claim = overall REFUTED"""
        claims = ["Claim 1", "Claim 2"]

        # First claim supported, second claim refuted
        stances = [
            StanceResult(
                claim_text="Claim 1",
                article_id=uuid4(),
                article_title="Supporting Article",
                article_url="https://example.com/support",
                source_name="VNExpress",
                published_at=datetime.now(timezone.utc),
                stance="SUPPORTS",
                confidence=0.9,
                evidence_spans=[EvidenceSpan(text="quote", reasoning="supports")],
                overall_reasoning="supports",
            ),
            StanceResult(
                claim_text="Claim 2",
                article_id=uuid4(),
                article_title="Refuting Article",
                article_url="https://example.com/refute",
                source_name="Tuoi Tre",
                published_at=datetime.now(timezone.utc),
                stance="REFUTES",
                confidence=0.8,
                evidence_spans=[EvidenceSpan(text="quote", reasoning="refutes")],
                overall_reasoning="refutes",
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
                article_id=uuid4(),
                article_title="Supporting Article 1",
                article_url="https://example.com/support1",
                source_name="VNExpress",
                published_at=datetime.now(timezone.utc),
                stance="SUPPORTS",
                confidence=0.9,
                evidence_spans=[EvidenceSpan(text="quote", reasoning="supports")],
                overall_reasoning="supports",
            ),
            StanceResult(
                claim_text="Claim 2",
                article_id=uuid4(),
                article_title="Supporting Article 2",
                article_url="https://example.com/support2",
                source_name="Tuoi Tre",
                published_at=datetime.now(timezone.utc),
                stance="SUPPORTS",
                confidence=0.85,
                evidence_spans=[EvidenceSpan(text="quote", reasoning="supports")],
                overall_reasoning="supports",
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
                article_id=uuid4(),
                article_title="Supporting Article",
                article_url="https://example.com/support",
                source_name="VNExpress",
                published_at=datetime.now(timezone.utc),
                stance="SUPPORTS",
                confidence=0.9,
                evidence_spans=[EvidenceSpan(text="quote", reasoning="supports")],
                overall_reasoning="supports",
            ),
            StanceResult(
                claim_text="Claim 2",
                article_id=uuid4(),
                article_title="Neutral Article",
                article_url="https://example.com/neutral",
                source_name="Tuoi Tre",
                published_at=datetime.now(timezone.utc),
                stance="NOT_ENOUGH_INFO",
                confidence=0.5,
                evidence_spans=[EvidenceSpan(text="quote", reasoning="nei")],
                overall_reasoning="nei",
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
        assert result.reason == "NO_RELEVANT_ARTICLES"
        assert result.confidence is None
        assert result.confidence_metrics is None
        assert result.claim_verdicts[0].verdict == "NOT_ENOUGH_INFO"
        assert result.claim_verdicts[0].reason == "NO_RELEVANT_ARTICLES"

    def test_aggregate_empty_claims(self, aggregator):
        """Test aggregation with empty claims list"""
        claims = []
        stances = []

        result = aggregator.aggregate_verdicts(stances, claims)

        assert result.verdict == "NOT_ENOUGH_INFO"
        assert result.reason == "NO_FACTUAL_CLAIMS"
        assert result.confidence is None
        assert result.confidence_metrics is None
        assert len(result.claim_verdicts) == 0

    def test_confidence_metrics_calculated(self, aggregator, sample_support_stance):
        """Test that confidence metrics are properly calculated"""
        claims = ["Test claim"]
        stances = [sample_support_stance]

        result = aggregator.aggregate_verdicts(stances, claims)

        # Check confidence metrics exist and are reasonable
        metrics = result.confidence_metrics
        assert metrics is not None
        assert metrics.overall_confidence >= 0.0
        assert metrics.overall_confidence <= 1.0
        assert metrics.evidence_quality >= 0.0
        assert metrics.source_agreement >= 0.0
        assert metrics.source_quantity >= 0.0
        assert metrics.temporal_relevance >= 0.0

    def test_high_confidence_stances(self, aggregator):
        """Test that high-confidence stances produce high overall confidence"""
        claims = ["Claim 1"]

        # Create multiple high-confidence supporting stances
        stances = [
            StanceResult(
                claim_text="Claim 1",
                article_id=uuid4(),
                article_title="Article 1",
                article_url="https://example.com/article1",
                source_name="VNExpress",
                published_at=datetime.now(timezone.utc),
                stance="SUPPORTS",
                confidence=0.95,
                evidence_spans=[EvidenceSpan(text="quote", reasoning="supports")],
                overall_reasoning="supports",
            ),
            StanceResult(
                claim_text="Claim 1",
                article_id=uuid4(),
                article_title="Article 2",
                article_url="https://example.com/article2",
                source_name="Tuoi Tre",
                published_at=datetime.now(timezone.utc),
                stance="SUPPORTS",
                confidence=0.92,
                evidence_spans=[EvidenceSpan(text="quote", reasoning="supports")],
                overall_reasoning="supports",
            ),
        ]

        result = aggregator.aggregate_verdicts(stances, claims)

        # With high confidence and multiple sources, should get high overall confidence
        assert result.confidence >= 0.7

    def test_sources_used_collected(self, aggregator):
        """Test that sources are properly collected"""
        claims = ["Claim 1", "Claim 2"]

        stances = [
            StanceResult(
                claim_text="Claim 1",
                article_id=uuid4(),
                article_title="Article 1",
                article_url="https://example.com/article1",
                source_name="VNExpress",
                published_at=datetime.now(timezone.utc),
                stance="SUPPORTS",
                confidence=0.9,
                evidence_spans=[EvidenceSpan(text="quote", reasoning="supports")],
                overall_reasoning="supports",
            ),
            StanceResult(
                claim_text="Claim 2",
                article_id=uuid4(),
                article_title="Article 2",
                article_url="https://example.com/article2",
                source_name="Tuoi Tre",
                published_at=datetime.now(timezone.utc),
                stance="SUPPORTS",
                confidence=0.85,
                evidence_spans=[EvidenceSpan(text="quote", reasoning="supports")],
                overall_reasoning="supports",
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
                article_id=uuid4(),
                article_title="Recent Article",
                article_url="https://example.com/recent",
                source_name="VNExpress",
                published_at=datetime.now(timezone.utc),  # Today
                stance="SUPPORTS",
                confidence=0.9,
                evidence_spans=[EvidenceSpan(text="quote", reasoning="supports")],
                overall_reasoning="supports",
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
                article_id=uuid4(),
                article_title="Article 1",
                article_url="https://example.com/article1",
                source_name="VNExpress",
                published_at=datetime.now(timezone.utc),
                stance="SUPPORTS",
                confidence=0.9,
                evidence_spans=[EvidenceSpan(text="quote", reasoning="supports")],
                overall_reasoning="supports",
            ),
            StanceResult(
                claim_text="Test claim",
                article_id=uuid4(),
                article_title="Article 2",
                article_url="https://example.com/article2",
                source_name="Tuoi Tre",
                published_at=datetime.now(timezone.utc),
                stance="SUPPORTS",
                confidence=0.85,
                evidence_spans=[EvidenceSpan(text="quote", reasoning="supports")],
                overall_reasoning="supports",
            ),
        ]

        result = aggregator.aggregate_verdicts(stances, claims)

        assert result.verdict == "FULLY_SUPPORTED"
        assert len(result.claim_verdicts[0].supporting_evidence) == 2

    def test_source_agreement_verdict_aware(self, aggregator):
        """Test source agreement is verdict-aware (for FULLY_SUPPORTED verdict)"""
        claims = ["Test claim"]

        # All sources agree (SUPPORTS)
        stances = [
            StanceResult(
                claim_text="Test claim",
                article_id=uuid4(),
                article_title="Article 1",
                article_url="https://example.com/article1",
                source_name="VNExpress",
                published_at=datetime.now(timezone.utc),
                stance="SUPPORTS",
                confidence=0.9,
                evidence_spans=[EvidenceSpan(text="quote", reasoning="supports")],
                overall_reasoning="supports",
            ),
            StanceResult(
                claim_text="Test claim",
                article_id=uuid4(),
                article_title="Article 2",
                article_url="https://example.com/article2",
                source_name="Tuoi Tre",
                published_at=datetime.now(timezone.utc),
                stance="SUPPORTS",
                confidence=0.85,
                evidence_spans=[EvidenceSpan(text="quote", reasoning="supports")],
                overall_reasoning="supports",
            ),
            StanceResult(
                claim_text="Test claim",
                article_id=uuid4(),
                article_title="Article 3",
                article_url="https://example.com/article3",
                source_name="Dan Tri",
                published_at=datetime.now(timezone.utc),
                stance="SUPPORTS",
                confidence=0.8,
                evidence_spans=[EvidenceSpan(text="quote", reasoning="supports")],
                overall_reasoning="supports",
            ),
        ]

        result = aggregator.aggregate_verdicts(stances, claims)

        # For FULLY_SUPPORTED verdict, source agreement should be 1.0 (all SUPPORTS)
        assert result.verdict == "FULLY_SUPPORTED"
        assert result.confidence_metrics.source_agreement == 1.0

    def test_conflicting_evidence_returns_nei_no_metrics(self, aggregator):
        """Test that conflicting evidence returns NOT_ENOUGH_INFO with no confidence metrics"""
        claims = ["Test claim"]

        # Mix of supports and refutes = conflict
        stances = [
            StanceResult(
                claim_text="Test claim",
                article_id=uuid4(),
                article_title="Supporting Article",
                article_url="https://example.com/support",
                source_name="VNExpress",
                published_at=datetime.now(timezone.utc),
                stance="SUPPORTS",
                confidence=0.9,
                evidence_spans=[EvidenceSpan(text="quote", reasoning="supports")],
                overall_reasoning="supports",
            ),
            StanceResult(
                claim_text="Test claim",
                article_id=uuid4(),
                article_title="Refuting Article",
                article_url="https://example.com/refute",
                source_name="Tuoi Tre",
                published_at=datetime.now(timezone.utc),
                stance="REFUTES",
                confidence=0.85,
                evidence_spans=[EvidenceSpan(text="quote", reasoning="refutes")],
                overall_reasoning="refutes",
            ),
        ]

        result = aggregator.aggregate_verdicts(stances, claims)

        # Should return NOT_ENOUGH_INFO with reason and no confidence metrics
        assert result.verdict == "NOT_ENOUGH_INFO"
        assert result.reason == "CONFLICTING_SOURCES"
        assert result.confidence is None
        assert result.confidence_metrics is None
