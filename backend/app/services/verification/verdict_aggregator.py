"""
Verdict Aggregator Service

Aggregates stance classification results into claim-level and
overall verdicts with confidence scoring.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List

from app.config.settings import settings
from app.core.logging import get_logger
from app.services.verification.stance_classifier import StanceResult

logger = get_logger(__name__)


@dataclass
class ClaimVerdict:
    """Aggregated verdict for a single claim"""

    claim_text: str
    verdict: str  # SUPPORTED, REFUTED, NOT_ENOUGH_INFO
    confidence: float
    supporting_evidence: List[StanceResult] = field(default_factory=list)
    refuting_evidence: List[StanceResult] = field(default_factory=list)


@dataclass
class ConfidenceMetrics:
    """Metrics for confidence calculation"""

    overall_confidence: float
    confidence_tier: str  # HIGH, MEDIUM, LOW, NONE
    evidence_quality: float
    source_agreement: float
    claim_coverage: float
    stance_confidence: float
    temporal_relevance: float


@dataclass
class OverallVerdict:
    """Overall verification verdict"""

    verdict: str  # FULLY_SUPPORTED, PARTIALLY_SUPPORTED, REFUTED, NOT_ENOUGH_INFO
    confidence: float
    confidence_tier: str
    claim_verdicts: List[ClaimVerdict]
    confidence_metrics: ConfidenceMetrics
    sources_used: List[str]
    total_claims: int
    supported_claims: int
    refuted_claims: int


class VerdictAggregator:
    """
    Aggregates stance results into claim and overall verdicts.

    Implements conservative conflict handling and worst-case aggregation
    as specified in the design.
    """

    def __init__(self):
        self.min_evidence = settings.verification.aggregation.min_evidence_per_claim
        self.conflict_mode = settings.verification.aggregation.conflict_mode
        self.verdict_mode = settings.verification.verdict.mode
        self.weights = settings.verification.confidence_scoring.weights
        self.thresholds = settings.verification.confidence_scoring.thresholds

    def aggregate_verdicts(
        self,
        stance_results: List[StanceResult],
        claims: List[str],
    ) -> OverallVerdict:
        """
        Aggregate stance results into claim verdicts and overall verdict.

        Args:
            stance_results: List of stance classification results
            claims: Original list of claims

        Returns:
            OverallVerdict with all aggregated results
        """
        logger.info(
            f"Aggregating {len(stance_results)} stances for {len(claims)} claims"
        )

        # Group stance results by claim
        claim_stances: Dict[str, List[StanceResult]] = {}
        for claim in claims:
            claim_stances[claim] = []

        for result in stance_results:
            if result.claim_text in claim_stances:
                claim_stances[result.claim_text].append(result)

        # Aggregate verdicts for each claim
        claim_verdicts = []
        for claim in claims:
            stances = claim_stances.get(claim, [])
            verdict = self._aggregate_claim_verdict(claim, stances)
            claim_verdicts.append(verdict)

        # Compute overall verdict
        overall_verdict = self._compute_overall_verdict(claim_verdicts)

        # Calculate confidence metrics
        confidence_metrics = self._calculate_confidence_metrics(
            stance_results, claim_verdicts
        )

        # Collect sources used
        sources_used = list(set(r.source_name for r in stance_results))

        # Count verdicts
        supported = sum(1 for v in claim_verdicts if v.verdict == "SUPPORTED")
        refuted = sum(1 for v in claim_verdicts if v.verdict == "REFUTED")

        logger.info(
            f"Verdict aggregation complete: {overall_verdict} "
            f"(supported={supported}, refuted={refuted}, total={len(claims)})"
        )

        return OverallVerdict(
            verdict=overall_verdict,
            confidence=confidence_metrics.overall_confidence,
            confidence_tier=confidence_metrics.confidence_tier,
            claim_verdicts=claim_verdicts,
            confidence_metrics=confidence_metrics,
            sources_used=sources_used,
            total_claims=len(claims),
            supported_claims=supported,
            refuted_claims=refuted,
        )

    def _aggregate_claim_verdict(
        self, claim: str, stances: List[StanceResult]
    ) -> ClaimVerdict:
        """
        Aggregate stances for a single claim into a verdict.

        Args:
            claim: The claim text
            stances: List of stance results for this claim

        Returns:
            ClaimVerdict for this claim
        """
        if not stances:
            return ClaimVerdict(
                claim_text=claim,
                verdict="NOT_ENOUGH_INFO",
                confidence=0.0,
                supporting_evidence=[],
                refuting_evidence=[],
            )

        # Separate by stance type
        supports = [s for s in stances if s.stance == "SUPPORTS"]
        refutes = [s for s in stances if s.stance == "REFUTES"]

        # Conservative conflict handling: if both support and refute exist, return NEI
        if supports and refutes:
            logger.debug(
                f"Claim '{claim[:30]}...' has conflicting evidence: "
                f"{len(supports)} supports, {len(refutes)} refutes"
            )
            # Average confidence from all stances
            avg_confidence = sum(s.confidence for s in stances) / len(stances)
            return ClaimVerdict(
                claim_text=claim,
                verdict="NOT_ENOUGH_INFO",
                confidence=avg_confidence * 0.5,  # Reduce confidence due to conflict
                supporting_evidence=supports,
                refuting_evidence=refutes,
            )

        # If any refutation exists (worst case for claim level)
        if refutes:
            avg_confidence = sum(s.confidence for s in refutes) / len(refutes)
            return ClaimVerdict(
                claim_text=claim,
                verdict="REFUTED",
                confidence=avg_confidence,
                supporting_evidence=[],
                refuting_evidence=refutes,
            )

        # If at least 1 support exists (updated requirement)
        if len(supports) >= self.min_evidence:
            avg_confidence = sum(s.confidence for s in supports) / len(supports)
            return ClaimVerdict(
                claim_text=claim,
                verdict="SUPPORTED",
                confidence=avg_confidence,
                supporting_evidence=supports,
                refuting_evidence=[],
            )

        # Not enough evidence
        avg_confidence = (
            sum(s.confidence for s in stances) / len(stances) if stances else 0.0
        )
        return ClaimVerdict(
            claim_text=claim,
            verdict="NOT_ENOUGH_INFO",
            confidence=avg_confidence
            * 0.7,  # Reduce confidence for insufficient evidence
            supporting_evidence=supports,
            refuting_evidence=[],
        )

    def _compute_overall_verdict(self, claim_verdicts: List[ClaimVerdict]) -> str:
        """
        Compute overall verdict from claim verdicts.

        Uses worst-case logic: any refuted claim = REFUTED overall.

        Args:
            claim_verdicts: List of claim verdicts

        Returns:
            Overall verdict string
        """
        if not claim_verdicts:
            return "NOT_ENOUGH_INFO"

        refuted = [v for v in claim_verdicts if v.verdict == "REFUTED"]
        supported = [v for v in claim_verdicts if v.verdict == "SUPPORTED"]
        nei = [v for v in claim_verdicts if v.verdict == "NOT_ENOUGH_INFO"]

        total = len(claim_verdicts)

        # Worst case: any refuted claim = REFUTED overall
        if refuted:
            return "REFUTED"

        # All claims supported = FULLY_SUPPORTED
        if len(supported) == total:
            return "FULLY_SUPPORTED"

        # Mix of supported and NEI = PARTIALLY_SUPPORTED
        if supported and nei:
            return "PARTIALLY_SUPPORTED"

        # All NEI
        return "NOT_ENOUGH_INFO"

    def _calculate_confidence_metrics(
        self,
        stance_results: List[StanceResult],
        claim_verdicts: List[ClaimVerdict],
    ) -> ConfidenceMetrics:
        """
        Calculate multi-signal confidence metrics.

        Args:
            stance_results: All stance classification results
            claim_verdicts: All claim verdicts

        Returns:
            ConfidenceMetrics with all signals
        """
        if not stance_results or not claim_verdicts:
            return ConfidenceMetrics(
                overall_confidence=0.0,
                confidence_tier="NONE",
                evidence_quality=0.0,
                source_agreement=0.0,
                claim_coverage=0.0,
                stance_confidence=0.0,
                temporal_relevance=0.0,
            )

        # Signal 1: Evidence Quality (30%) - average stance confidence
        # (Previously used similarity score, now using LLM confidence as quality indicator)
        evidence_quality = sum(s.confidence for s in stance_results) / len(
            stance_results
        )

        # Signal 2: Source Agreement (25%) - percentage of sources agreeing
        source_agreement = self._calculate_source_agreement(stance_results)

        # Signal 3: Claim Coverage (15%) - percentage of claims fully supported
        supported_claims = sum(1 for v in claim_verdicts if v.verdict == "SUPPORTED")
        claim_coverage = (
            supported_claims / len(claim_verdicts) if claim_verdicts else 0.0
        )

        # Signal 4: Stance Confidence (25%) - average LLM confidence
        stance_confidence = sum(s.confidence for s in stance_results) / len(
            stance_results
        )

        # Signal 5: Temporal Relevance (5%) - recency of articles
        temporal_relevance = self._calculate_temporal_relevance(stance_results)

        # Calculate weighted overall confidence
        overall_confidence = (
            self.weights.evidence_quality * evidence_quality
            + self.weights.source_agreement * source_agreement
            + self.weights.claim_coverage * claim_coverage
            + self.weights.stance_confidence * stance_confidence
            + self.weights.temporal_relevance * temporal_relevance
        )

        # Determine confidence tier
        if overall_confidence >= self.thresholds.high:
            confidence_tier = "HIGH"
        elif overall_confidence >= self.thresholds.medium:
            confidence_tier = "MEDIUM"
        elif overall_confidence >= self.thresholds.low:
            confidence_tier = "LOW"
        else:
            confidence_tier = "NONE"

        return ConfidenceMetrics(
            overall_confidence=overall_confidence,
            confidence_tier=confidence_tier,
            evidence_quality=evidence_quality,
            source_agreement=source_agreement,
            claim_coverage=claim_coverage,
            stance_confidence=stance_confidence,
            temporal_relevance=temporal_relevance,
        )

    def _calculate_source_agreement(self, stance_results: List[StanceResult]) -> float:
        """
        Calculate the percentage of sources that agree on the verdict.

        Args:
            stance_results: All stance results

        Returns:
            Agreement ratio (0-1)
        """
        if not stance_results:
            return 0.0

        # Count stances
        supports = sum(1 for s in stance_results if s.stance == "SUPPORTS")
        refutes = sum(1 for s in stance_results if s.stance == "REFUTES")
        total = len(stance_results)

        # Agreement is the ratio of the majority stance
        max_stance = max(supports, refutes)
        return max_stance / total if total > 0 else 0.0

    def _calculate_temporal_relevance(
        self, stance_results: List[StanceResult]
    ) -> float:
        """
        Calculate temporal relevance based on article recency.

        More recent articles get higher scores.

        Args:
            stance_results: All stance results

        Returns:
            Temporal relevance score (0-1)
        """
        if not stance_results:
            return 0.0

        now = datetime.now(timezone.utc)
        recency_scores = []

        for result in stance_results:
            if result.published_at:
                # Make published_at timezone-aware if it isn't
                pub_date = result.published_at
                if pub_date.tzinfo is None:
                    pub_date = pub_date.replace(tzinfo=timezone.utc)

                # Calculate days ago
                days_ago = (now - pub_date).days

                # Score: 1.0 for today, decays over 30 days
                if days_ago <= 0:
                    score = 1.0
                elif days_ago >= 30:
                    score = 0.1  # Minimum score for old articles
                else:
                    score = 1.0 - (days_ago / 30) * 0.9
                recency_scores.append(score)
            else:
                recency_scores.append(0.5)  # Default for unknown date

        return sum(recency_scores) / len(recency_scores) if recency_scores else 0.5
