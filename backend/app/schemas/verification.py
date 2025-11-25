"""
Verification API Schemas

Pydantic models for verification request/response.
"""

from enum import Enum
from typing import Dict, List

from pydantic import BaseModel, Field


class StanceType(str, Enum):
    """Stance classification types for NLI"""

    SUPPORTS = "SUPPORTS"
    REFUTES = "REFUTES"
    NOT_ENOUGH_INFO = "NOT_ENOUGH_INFO"


class ClaimVerdictType(str, Enum):
    """Verdict types for individual claims"""

    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    NOT_ENOUGH_INFO = "NOT_ENOUGH_INFO"


class OverallVerdictType(str, Enum):
    """Overall verdict types for the entire post"""

    FULLY_SUPPORTED = "FULLY_SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    REFUTED = "REFUTED"
    NOT_ENOUGH_INFO = "NOT_ENOUGH_INFO"


class NotEnoughInfoReason(str, Enum):
    """Reason categories for NOT_ENOUGH_INFO verdicts"""

    NO_FACTUAL_CLAIMS = "NO_FACTUAL_CLAIMS"
    NO_RELEVANT_ARTICLES = "NO_RELEVANT_ARTICLES"
    CONFLICTING_SOURCES = "CONFLICTING_SOURCES"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class EvidenceSpan(BaseModel):
    """Extracted evidence span from article"""

    text: str = Field(description="Exact quote from article")
    reasoning: str = Field(description="Why this text supports/refutes the claim")


class StanceResultSchema(BaseModel):
    """Result of stance classification for a claim-article pair"""

    claim_text: str = Field(description="The claim being verified")
    article_id: str = Field(description="ID of the article")
    article_title: str = Field(description="Title of the article")
    article_url: str = Field(description="URL of the article")
    source_name: str = Field(description="Name of the news source")
    published_at: str | None = Field(description="Publication date of the article")
    stance: StanceType = Field(
        description="Classified stance: SUPPORTS, REFUTES, or NOT_ENOUGH_INFO"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="LLM confidence in stance classification"
    )
    evidence_spans: List[EvidenceSpan] = Field(
        default_factory=list,
        description="Exact text spans extracted from article as evidence",
    )
    overall_reasoning: str = Field(
        description="Comprehensive explanation for the stance classification"
    )


class ClaimVerdictSchema(BaseModel):
    """Aggregated verdict for a single claim"""

    claim_text: str = Field(description="The claim being verified")
    verdict: ClaimVerdictType = Field(description="Verdict for this claim")
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence in this verdict (null for NOT_ENOUGH_INFO)",
    )
    reason: NotEnoughInfoReason | None = Field(
        default=None, description="Reason category for NOT_ENOUGH_INFO verdicts"
    )
    supporting_evidence: List[StanceResultSchema] = Field(
        default_factory=list, description="Evidence that supports the claim"
    )
    refuting_evidence: List[StanceResultSchema] = Field(
        default_factory=list, description="Evidence that refutes the claim"
    )


class VerificationConfidenceMetricsSchema(BaseModel):
    """Confidence metrics specific to verification"""

    overall_confidence: float = Field(
        ge=0.0, le=1.0, description="Overall verification confidence (0-1)"
    )
    evidence_quality: float = Field(
        ge=0.0,
        le=1.0,
        description="Average LLM confidence in stance classifications (45% weight)",
    )
    source_agreement: float = Field(
        ge=0.0,
        le=1.0,
        description="Percentage of sources agreeing on verdict (30% weight, verdict-aware)",
    )
    source_quantity: float = Field(
        ge=0.0, le=1.0, description="Number of unique sources normalized (15% weight)"
    )
    temporal_relevance: float = Field(
        ge=0.0, le=1.0, description="Recency score of articles (10% weight)"
    )


class VerificationResultSchema(BaseModel):
    """Complete verification result"""

    verdict: OverallVerdictType = Field(description="Overall verdict for the post")
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Overall confidence score (null for NOT_ENOUGH_INFO)",
    )
    reason: NotEnoughInfoReason | None = Field(
        default=None, description="Reason category for NOT_ENOUGH_INFO verdicts"
    )
    explanation: str = Field(description="Human-readable explanation in Vietnamese")
    claim_verdicts: List[ClaimVerdictSchema] = Field(
        description="Per-claim verification results"
    )
    total_claims: int = Field(description="Total number of claims extracted")
    supported_claims: int = Field(description="Number of supported claims")
    refuted_claims: int = Field(description="Number of refuted claims")
    sources_used: List[str] = Field(
        description="List of news sources used for verification"
    )
    confidence_metrics: VerificationConfidenceMetricsSchema | None = Field(
        default=None,
        description="Detailed confidence breakdown (null for NOT_ENOUGH_INFO)",
    )


class ChunkDetailSchema(BaseModel):
    """Detail of a relevant chunk"""

    chunk_id: str
    chunk_index: int
    chunk_text: str
    score: float


class ArticleResultSchema(BaseModel):
    """Article-level retrieval result"""

    article_id: str
    title: str
    source_name: str
    published_at: str | None
    relevance_score: float  # Maximum chunk score (0-10 scale)
    url: str
    chunk_count: int
    relevant_chunks: List[ChunkDetailSchema]


class VerificationRequest(BaseModel):
    """Request to verify a Facebook post"""

    text: str = Field(
        ..., min_length=10, max_length=10000, description="Facebook post text to verify"
    )
    cache_bypass: bool = Field(
        default=False, description="If True, bypass cache and force re-verification"
    )


class ConfidenceMetricsSchema(BaseModel):
    """Confidence metrics for retrieval quality"""

    overall_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Overall confidence score (0-1) that articles match query",
    )
    confidence_tier: str = Field(
        description="Confidence tier: HIGH, MEDIUM, LOW, or NONE"
    )
    top_article_score: float = Field(description="Relevance score of best article")
    score_gap_ratio: float = Field(description="Gap between #1 and #2 articles (0-1)")
    entity_coverage_ratio: float = Field(
        description="Percentage of query entities found in top article (0-1)"
    )
    temporal_alignment: bool = Field(
        description="Do temporal entities (dates) align with query?"
    )
    spatial_alignment: bool = Field(
        description="Do spatial entities (locations) align with query?"
    )
    title_similarity: float = Field(
        description="Cosine similarity between query and article title (0-1)"
    )
    total_qualifying_chunks: int = Field(
        description="Total number of relevant chunks across articles"
    )
    article_count: int = Field(description="Number of articles returned")


class VerificationResponse(BaseModel):
    """Response from verification endpoint"""

    articles: List[Dict]  # List of article dicts from ArticleResult.to_dict()
    total_time_ms: int
    stage_timings: Dict[str, float]
    query_count: int
    verification: VerificationResultSchema | None = Field(
        default=None, description="Verification result with verdict and evidence"
    )
    cache_hit: bool
    factual_confidence: int | None = Field(
        default=None,
        ge=1,
        le=3,
        description="LLM-assessed confidence that post contains verifiable facts (1-3 scale: 1=Opinion, 2=Vague, 3=Verifiable)",
    )
    retrieval_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence that returned articles are relevant to the query (0-1 scale)",
    )
    confidence_metrics: ConfidenceMetricsSchema | None = Field(
        default=None,
        description="Detailed confidence breakdown with multi-signal analysis",
    )
    low_confidence_warning: bool = Field(
        default=False,
        description="True if articles returned but confidence is low (user should be cautious)",
    )
    early_exit: bool = Field(
        default=False,
        description="True if pipeline exited early (e.g., low confidence)",
    )
    exit_reason: str | None = Field(
        default=None,
        description="Reason for early exit (e.g., 'LOW_CONFIDENCE', 'NO_RELEVANT_ARTICLES')",
    )
    message: str | None = Field(
        default=None, description="Human-readable message explaining result"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "articles": [
                    {
                        "article_id": "123e4567-e89b-12d3-a456-426614174000",
                        "title": "VinTech công bố dự án nhà máy mới",
                        "source_name": "VnExpress",
                        "published_at": "2024-01-15T10:30:00",
                        "relevance_score": 8.15,
                        "url": "https://vnexpress.net/vintech-cong-bo-du-an-nha-may-moi-123456.html",
                        "chunk_count": 3,
                        "relevant_chunks": [],
                    }
                ],
                "total_time_ms": 3500,
                "stage_timings": {
                    "query_extraction": 450.2,
                    "embedding": 320.5,
                    "hybrid_search": 890.3,
                    "fusion": 12.1,
                    "reranking": 1650.8,
                    "aggregation": 8.3,
                },
                "query_count": 3,
                "verification": {
                    "verdict": "FULLY_SUPPORTED",
                    "confidence": 0.85,
                    "reason": None,
                    "explanation": "Tất cả luận điểm được xác nhận bởi nguồn tin đáng tin cậy",
                    "claim_verdicts": [
                        {
                            "claim_text": "VinTech công bố dự án nhà máy mới",
                            "verdict": "SUPPORTED",
                            "confidence": 0.9,
                            "reason": None,
                            "supporting_evidence": [],
                            "refuting_evidence": [],
                        }
                    ],
                    "total_claims": 1,
                    "supported_claims": 1,
                    "refuted_claims": 0,
                    "sources_used": ["VnExpress"],
                    "confidence_metrics": {
                        "overall_confidence": 0.85,
                        "evidence_quality": 0.88,
                        "source_agreement": 1.0,
                        "source_quantity": 0.2,
                        "temporal_relevance": 0.7,
                    },
                },
                "cache_hit": False,
                "factual_confidence": 3,
                "early_exit": False,
                "exit_reason": None,
                "message": None,
            }
        }
