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
    confidence: float | None  # None for NOT_ENOUGH_INFO
    reason: str | None = None  # Reason for NOT_ENOUGH_INFO
    supporting_evidence: List[StanceResult] = field(default_factory=list)
    refuting_evidence: List[StanceResult] = field(default_factory=list)


@dataclass
class ConfidenceMetrics:
    """Metrics for confidence calculation"""

    overall_confidence: float
    evidence_quality: float
    source_agreement: float
    source_quantity: float
    temporal_relevance: float


@dataclass
class OverallVerdict:
    """Overall verification verdict"""

    verdict: str  # FULLY_SUPPORTED, PARTIALLY_SUPPORTED, REFUTED, NOT_ENOUGH_INFO
    confidence: float | None  # None for NOT_ENOUGH_INFO
    reason: str | None = None  # Reason for NOT_ENOUGH_INFO
    claim_verdicts: List[ClaimVerdict] = field(default_factory=list)
    confidence_metrics: ConfidenceMetrics | None = None  # None for NOT_ENOUGH_INFO
    sources_used: List[str] = field(default_factory=list)
    total_claims: int = 0
    supported_claims: int = 0
    refuted_claims: int = 0


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

        # Compute overall verdict and reason (if NOT_ENOUGH_INFO)
        overall_verdict, reason = self._compute_overall_verdict(claim_verdicts)

        # Calculate confidence metrics (None for NOT_ENOUGH_INFO)
        confidence_metrics = self._calculate_confidence_metrics(
            stance_results, claim_verdicts, overall_verdict
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
            confidence=confidence_metrics.overall_confidence
            if confidence_metrics
            else None,
            reason=reason,
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
                confidence=None,
                reason="NO_RELEVANT_ARTICLES",
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
            return ClaimVerdict(
                claim_text=claim,
                verdict="NOT_ENOUGH_INFO",
                confidence=None,
                reason="CONFLICTING_SOURCES",
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
        return ClaimVerdict(
            claim_text=claim,
            verdict="NOT_ENOUGH_INFO",
            confidence=None,
            reason="INSUFFICIENT_EVIDENCE",
            supporting_evidence=supports,
            refuting_evidence=[],
        )

    def _compute_overall_verdict(
        self, claim_verdicts: List[ClaimVerdict]
    ) -> tuple[str, str | None]:
        """
        Compute overall verdict from claim verdicts.

        Uses worst-case logic: any refuted claim = REFUTED overall.

        Args:
            claim_verdicts: List of claim verdicts

        Returns:
            Tuple of (verdict, reason) where reason is only set for NOT_ENOUGH_INFO
        """
        if not claim_verdicts:
            return "NOT_ENOUGH_INFO", "NO_FACTUAL_CLAIMS"

        refuted = [v for v in claim_verdicts if v.verdict == "REFUTED"]
        supported = [v for v in claim_verdicts if v.verdict == "SUPPORTED"]
        nei = [v for v in claim_verdicts if v.verdict == "NOT_ENOUGH_INFO"]

        total = len(claim_verdicts)

        # Worst case: any refuted claim = REFUTED overall
        if refuted:
            return "REFUTED", None

        # All claims supported = FULLY_SUPPORTED
        if len(supported) == total:
            return "FULLY_SUPPORTED", None

        # Mix of supported and NEI = PARTIALLY_SUPPORTED
        if supported and nei:
            return "PARTIALLY_SUPPORTED", None

        # All NEI - determine reason
        reason = self._determine_nei_reason(claim_verdicts)
        return "NOT_ENOUGH_INFO", reason

    def _determine_nei_reason(self, claim_verdicts: List[ClaimVerdict]) -> str:
        """
        Determine the reason for NOT_ENOUGH_INFO verdict.

        Args:
            claim_verdicts: List of claim verdicts

        Returns:
            Reason code string
        """
        if not claim_verdicts:
            return "NO_FACTUAL_CLAIMS"

        # Check if any claim has evidence
        has_any_evidence = any(
            v.supporting_evidence or v.refuting_evidence for v in claim_verdicts
        )

        if not has_any_evidence:
            return "NO_RELEVANT_ARTICLES"

        # Check for conflicting sources
        has_conflicts = any(
            v.supporting_evidence and v.refuting_evidence for v in claim_verdicts
        )

        if has_conflicts:
            return "CONFLICTING_SOURCES"

        return "INSUFFICIENT_EVIDENCE"

    def _calculate_confidence_metrics(
        self,
        stance_results: List[StanceResult],
        claim_verdicts: List[ClaimVerdict],
        overall_verdict: str,
    ) -> ConfidenceMetrics | None:
        """
        Calculate multi-signal confidence metrics.

        Args:
            stance_results: All stance classification results
            claim_verdicts: All claim verdicts
            overall_verdict: The overall verdict string

        Returns:
            ConfidenceMetrics with all signals, or None for NOT_ENOUGH_INFO
        """
        # Return None for NOT_ENOUGH_INFO verdicts
        if overall_verdict == "NOT_ENOUGH_INFO":
            return None

        if not stance_results or not claim_verdicts:
            return None

        # Signal 1: Evidence Quality (45%) - average LLM confidence in stance classification
        evidence_quality = sum(s.confidence for s in stance_results) / len(
            stance_results
        )

        # Signal 2: Source Agreement (30%) - verdict-aware agreement
        source_agreement = self._calculate_source_agreement(
            stance_results, overall_verdict
        )

        # Signal 3: Source Quantity (15%) - number of unique sources
        source_quantity = self._calculate_source_quantity(stance_results)

        # Signal 4: Temporal Relevance (10%) - recency of articles
        temporal_relevance = self._calculate_temporal_relevance(stance_results)

        # Calculate weighted overall confidence
        overall_confidence = (
            self.weights.evidence_quality * evidence_quality
            + self.weights.source_agreement * source_agreement
            + self.weights.source_quantity * source_quantity
            + self.weights.temporal_relevance * temporal_relevance
        )

        return ConfidenceMetrics(
            overall_confidence=overall_confidence,
            evidence_quality=evidence_quality,
            source_agreement=source_agreement,
            source_quantity=source_quantity,
            temporal_relevance=temporal_relevance,
        )

    def _calculate_source_agreement(
        self, stance_results: List[StanceResult], overall_verdict: str
    ) -> float:
        """
        Calculate the percentage of sources that agree on the verdict.
        Verdict-aware: counts SUPPORTS for SUPPORTED/FULLY_SUPPORTED,
        REFUTES for REFUTED, and max for PARTIALLY_SUPPORTED.

        Args:
            stance_results: All stance results
            overall_verdict: The overall verdict

        Returns:
            Agreement ratio (0-1)
        """
        if not stance_results:
            return 0.0

        # Count stances
        supports = sum(1 for s in stance_results if s.stance == "SUPPORTS")
        refutes = sum(1 for s in stance_results if s.stance == "REFUTES")
        total = len(stance_results)

        if overall_verdict in ["FULLY_SUPPORTED", "SUPPORTED"]:
            return supports / total if total > 0 else 0.0
        elif overall_verdict == "REFUTED":
            return refutes / total if total > 0 else 0.0
        else:  # PARTIALLY_SUPPORTED
            max_stance = max(supports, refutes)
            return max_stance / total if total > 0 else 0.0

    def _calculate_source_quantity(self, stance_results: List[StanceResult]) -> float:
        """
        Calculate source quantity score.
        More unique sources = higher confidence.

        Args:
            stance_results: All stance results

        Returns:
            Source quantity score (0.2 per source, max 1.0)
        """
        if not stance_results:
            return 0.0

        unique_sources = len(set(r.source_name for r in stance_results))
        # 1 source = 0.2, 2 = 0.4, 3 = 0.6, 4 = 0.8, 5+ = 1.0
        return min(unique_sources * 0.2, 1.0)

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
