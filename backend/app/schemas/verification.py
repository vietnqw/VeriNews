"""
Verification API Schemas

Pydantic models for verification request/response.
"""

from typing import Dict, List

from pydantic import BaseModel, Field


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
    relevance_score: float
    similarity_score: float
    url: str
    chunk_count: int
    relevant_chunks: List[ChunkDetailSchema]


class VerificationRequest(BaseModel):
    """Request to verify a Facebook post"""

    text: str = Field(
        ..., min_length=10, max_length=10000, description="Facebook post text to verify"
    )


class DummyVerificationResult(BaseModel):
    """Dummy verification result (placeholder for future implementation)"""

    verdict: str = "NOT_IMPLEMENTED"
    confidence: float = 0.0
    reasoning: str = "Verification logic not implemented yet"


class VerificationResponse(BaseModel):
    """Response from verification endpoint"""

    articles: List[Dict]  # List of article dicts from ArticleResult.to_dict()
    total_time_ms: int
    stage_timings: Dict[str, float]
    query_count: int
    verification: DummyVerificationResult
    cache_hit: bool

    class Config:
        json_schema_extra = {
            "example": {
                "articles": [
                    {
                        "article_id": "123e4567-e89b-12d3-a456-426614174000",
                        "title": "VinTech công bố dự án nhà máy mới",
                        "source_name": "VnExpress",
                        "published_at": "2024-01-15T10:30:00",
                        "relevance_score": 2.45,
                        "similarity_score": 1.0,
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
                    "verdict": "NOT_IMPLEMENTED",
                    "confidence": 0.0,
                    "reasoning": "Verification logic not implemented yet",
                },
                "cache_hit": False,
            }
        }
