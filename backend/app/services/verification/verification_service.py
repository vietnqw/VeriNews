"""
Verification Service

Main orchestrator for the verification pipeline that verifies
Facebook posts against retrieved news articles using NLI techniques.
"""

import time
from typing import Dict, List

from app.config.settings import settings
from app.core.logging import get_logger
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
from app.services.retrieval.article_aggregation_service import ArticleResult
from app.services.verification.claim_article_mapper import ClaimArticleMapper
from app.services.verification.explanation_generator import ExplanationGenerator
from app.services.verification.stance_classifier import StanceClassifier
from app.services.verification.verdict_aggregator import VerdictAggregator

logger = get_logger(__name__)


class VerificationService:
    """
    Main orchestrator for the verification pipeline.

    Coordinates the following stages:
    1. Claim-Article Mapping
    2. Stance Classification (NLI)
    3. Verdict Aggregation
    4. Explanation Generation
    """

    def __init__(self):
        self.enabled = settings.verification.enabled
        self.claim_article_mapper = ClaimArticleMapper()
        self.stance_classifier = StanceClassifier()
        self.verdict_aggregator = VerdictAggregator()
        self.explanation_generator = ExplanationGenerator()

    async def verify(
        self,
        post_text: str,
        claims: List[str],
        articles: List[ArticleResult],
    ) -> tuple[VerificationResultSchema | None, Dict[str, float]]:
        """
        Verify a Facebook post against retrieved articles.

        Args:
            post_text: Original Facebook post text
            claims: List of extracted claims from the post
            articles: List of retrieved articles with chunks

        Returns:
            Tuple of (VerificationResultSchema, stage_timings_dict)
            Returns None for result if verification is disabled or no data
        """
        stage_timings: Dict[str, float] = {}

        if not self.enabled:
            logger.info("Verification service is disabled")
            return None, stage_timings

        if not claims:
            logger.warning("No claims to verify")
            return self._create_no_claims_result(), stage_timings

        if not articles:
            logger.warning("No articles to verify against")
            return self._create_no_articles_result(claims), stage_timings

        logger.info(
            f"Starting verification: {len(claims)} claims, {len(articles)} articles"
        )

        total_start = time.time()

        # Stage 1: Claim-Article Mapping
        start = time.time()
        claim_article_mappings = await self.claim_article_mapper.map_claims_to_articles(
            claims, articles
        )
        stage_timings["claim_article_mapping"] = (time.time() - start) * 1000

        # Check if we have any articles with content
        total_articles = sum(len(m.articles) for m in claim_article_mappings)
        if total_articles == 0:
            logger.warning("No articles with content found for verification")
            return self._create_no_evidence_result(claims), stage_timings

        # Stage 2: Stance Classification
        start = time.time()
        stance_results = await self.stance_classifier.classify_stances(
            claim_article_mappings
        )
        stage_timings["stance_classification"] = (time.time() - start) * 1000

        # Stage 3: Verdict Aggregation
        start = time.time()
        overall_verdict = self.verdict_aggregator.aggregate_verdicts(
            stance_results, claims
        )
        stage_timings["verdict_aggregation"] = (time.time() - start) * 1000

        # Stage 4: Explanation Generation
        start = time.time()
        explanation = await self.explanation_generator.generate_explanation(
            overall_verdict, post_text
        )
        stage_timings["explanation_generation"] = (time.time() - start) * 1000

        total_time = (time.time() - total_start) * 1000
        stage_timings["verification_total"] = total_time

        logger.info(
            f"Verification complete: {overall_verdict.verdict} "
            f"(confidence: {overall_verdict.confidence:.2f}) in {total_time:.0f}ms"
        )

        # Convert to schema
        result = self._convert_to_schema(overall_verdict, explanation)

        return result, stage_timings

    def _convert_to_schema(
        self,
        verdict: "VerdictAggregator.OverallVerdict",
        explanation: str,
    ) -> VerificationResultSchema:
        """
        Convert internal verdict to Pydantic schema.

        Args:
            verdict: Internal verdict object
            explanation: Generated explanation

        Returns:
            VerificationResultSchema
        """
        # Convert claim verdicts
        claim_verdict_schemas = []
        for cv in verdict.claim_verdicts:
            # Convert supporting evidence
            supporting = [
                StanceResultSchema(
                    claim_text=e.claim_text,
                    article_id=str(e.article_id),
                    article_title=e.article_title,
                    article_url=e.article_url,
                    source_name=e.source_name,
                    published_at=e.published_at.isoformat() if e.published_at else None,
                    stance=StanceType(e.stance),
                    confidence=e.confidence,
                    evidence_spans=[
                        EvidenceSpan(text=span.text, reasoning=span.reasoning)
                        for span in e.evidence_spans
                    ],
                    overall_reasoning=e.overall_reasoning,
                )
                for e in cv.supporting_evidence
            ]

            # Convert refuting evidence
            refuting = [
                StanceResultSchema(
                    claim_text=e.claim_text,
                    article_id=str(e.article_id),
                    article_title=e.article_title,
                    article_url=e.article_url,
                    source_name=e.source_name,
                    published_at=e.published_at.isoformat() if e.published_at else None,
                    stance=StanceType(e.stance),
                    confidence=e.confidence,
                    evidence_spans=[
                        EvidenceSpan(text=span.text, reasoning=span.reasoning)
                        for span in e.evidence_spans
                    ],
                    overall_reasoning=e.overall_reasoning,
                )
                for e in cv.refuting_evidence
            ]

            claim_verdict_schemas.append(
                ClaimVerdictSchema(
                    claim_text=cv.claim_text,
                    verdict=ClaimVerdictType(cv.verdict),
                    confidence=cv.confidence,
                    supporting_evidence=supporting,
                    refuting_evidence=refuting,
                )
            )

        # Convert confidence metrics
        metrics = verdict.confidence_metrics
        confidence_metrics_schema = VerificationConfidenceMetricsSchema(
            overall_confidence=metrics.overall_confidence,
            confidence_tier=metrics.confidence_tier,
            evidence_quality=metrics.evidence_quality,
            source_agreement=metrics.source_agreement,
            claim_coverage=metrics.claim_coverage,
            temporal_relevance=metrics.temporal_relevance,
        )

        # Map verdict to enum
        verdict_map = {
            "FULLY_SUPPORTED": OverallVerdictType.FULLY_SUPPORTED,
            "PARTIALLY_SUPPORTED": OverallVerdictType.PARTIALLY_SUPPORTED,
            "REFUTED": OverallVerdictType.REFUTED,
            "NOT_ENOUGH_INFO": OverallVerdictType.NOT_ENOUGH_INFO,
        }

        return VerificationResultSchema(
            verdict=verdict_map.get(
                verdict.verdict, OverallVerdictType.NOT_ENOUGH_INFO
            ),
            confidence=verdict.confidence,
            confidence_tier=verdict.confidence_tier,
            explanation=explanation,
            claim_verdicts=claim_verdict_schemas,
            total_claims=verdict.total_claims,
            supported_claims=verdict.supported_claims,
            refuted_claims=verdict.refuted_claims,
            sources_used=verdict.sources_used,
            confidence_metrics=confidence_metrics_schema,
        )

    def _create_no_claims_result(self) -> VerificationResultSchema:
        """Create result when no claims were extracted."""
        return VerificationResultSchema(
            verdict=OverallVerdictType.NOT_ENOUGH_INFO,
            confidence=0.0,
            confidence_tier="NONE",
            explanation=(
                "Không thể xác minh bài đăng này vì không tìm thấy luận điểm cụ thể "
                "nào cần kiểm chứng."
            ),
            claim_verdicts=[],
            total_claims=0,
            supported_claims=0,
            refuted_claims=0,
            sources_used=[],
            confidence_metrics=VerificationConfidenceMetricsSchema(
                overall_confidence=0.0,
                confidence_tier="NONE",
                evidence_quality=0.0,
                source_agreement=0.0,
                claim_coverage=0.0,
                temporal_relevance=0.0,
            ),
        )

    def _create_no_articles_result(self, claims: List[str]) -> VerificationResultSchema:
        """Create result when no articles were retrieved."""
        return VerificationResultSchema(
            verdict=OverallVerdictType.NOT_ENOUGH_INFO,
            confidence=0.0,
            confidence_tier="NONE",
            explanation=(
                "Không tìm thấy bài viết nào từ các nguồn tin đáng tin cậy liên quan "
                "đến nội dung bài đăng này."
            ),
            claim_verdicts=[
                ClaimVerdictSchema(
                    claim_text=claim,
                    verdict=ClaimVerdictType.NOT_ENOUGH_INFO,
                    confidence=0.0,
                    supporting_evidence=[],
                    refuting_evidence=[],
                )
                for claim in claims
            ],
            total_claims=len(claims),
            supported_claims=0,
            refuted_claims=0,
            sources_used=[],
            confidence_metrics=VerificationConfidenceMetricsSchema(
                overall_confidence=0.0,
                confidence_tier="NONE",
                evidence_quality=0.0,
                source_agreement=0.0,
                claim_coverage=0.0,
                temporal_relevance=0.0,
            ),
        )

    def _create_no_evidence_result(self, claims: List[str]) -> VerificationResultSchema:
        """Create result when no evidence was found for claims."""
        return VerificationResultSchema(
            verdict=OverallVerdictType.NOT_ENOUGH_INFO,
            confidence=0.0,
            confidence_tier="NONE",
            explanation=(
                "Không tìm thấy bằng chứng cụ thể từ các nguồn tin để xác minh "
                "các luận điểm trong bài đăng này."
            ),
            claim_verdicts=[
                ClaimVerdictSchema(
                    claim_text=claim,
                    verdict=ClaimVerdictType.NOT_ENOUGH_INFO,
                    confidence=0.0,
                    supporting_evidence=[],
                    refuting_evidence=[],
                )
                for claim in claims
            ],
            total_claims=len(claims),
            supported_claims=0,
            refuted_claims=0,
            sources_used=[],
            confidence_metrics=VerificationConfidenceMetricsSchema(
                overall_confidence=0.0,
                confidence_tier="NONE",
                evidence_quality=0.0,
                source_agreement=0.0,
                claim_coverage=0.0,
                temporal_relevance=0.0,
            ),
        )
