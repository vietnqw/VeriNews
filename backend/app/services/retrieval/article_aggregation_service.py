"""
Article Aggregation Service

Aggregates chunk-level scores to article-level results.
Uses threshold + sum strategy to reward articles with multiple high-quality chunks.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List
from uuid import UUID

from app.config.settings import settings
from app.core.logging import get_logger
from app.services.retrieval.bm25_search_service import ChunkSearchResult

logger = get_logger(__name__)


@dataclass
class ChunkDetail:
    """Details of a relevant chunk within an article"""

    chunk_id: UUID
    chunk_index: int
    chunk_text: str
    score: float


@dataclass
class ArticleResult:
    """Article-level retrieval result"""

    article_id: UUID
    title: str
    source_name: str
    published_at: datetime | None
    relevance_score: float
    relevant_chunks: List[ChunkDetail]
    chunk_count: int

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "article_id": str(self.article_id),
            "title": self.title,
            "source_name": self.source_name,
            "published_at": (
                self.published_at.isoformat() if self.published_at else None
            ),
            "relevance_score": self.relevance_score,
            "chunk_count": self.chunk_count,
            "relevant_chunks": [
                {
                    "chunk_id": str(chunk.chunk_id),
                    "chunk_index": chunk.chunk_index,
                    "chunk_text": chunk.chunk_text,
                    "score": chunk.score,
                }
                for chunk in self.relevant_chunks
            ],
        }


class ArticleAggregationService:
    """
    Aggregates chunk-level retrieval results to article-level.

    Strategy: Threshold + Sum
    - Only consider chunks with score >= threshold
    - Sum scores for all qualifying chunks per article
    - Articles with multiple high-quality chunks rank higher
    """

    def __init__(self):
        self.score_threshold = settings.retrieval.aggregation.score_threshold
        self.max_articles = settings.retrieval.aggregation.max_articles
        self.include_chunks = settings.retrieval.aggregation.include_chunks

    def aggregate_to_articles(
        self, chunks: List[ChunkSearchResult]
    ) -> List[ArticleResult]:
        """
        Aggregate chunks to article-level results.

        Args:
            chunks: List of reranked chunks (typically top 10 from reranking)

        Returns:
            List of ArticleResult, sorted by relevance score (highest first)
        """
        if not chunks:
            return []

        # Group chunks by article and accumulate scores
        # Format: {article_id: {"score": float, "chunks": [ChunkDetail, ...], "metadata": {...}}}
        article_scores: Dict[UUID, Dict] = defaultdict(
            lambda: {"score": 0.0, "chunks": [], "metadata": {}}
        )

        for chunk in chunks:
            # Filter by threshold
            if chunk.score < self.score_threshold:
                logger.debug(
                    f"Skipping chunk {chunk.chunk_id} with score {chunk.score:.4f} (below threshold {self.score_threshold})"
                )
                continue

            article_id = chunk.article_id

            # Accumulate score
            article_scores[article_id]["score"] += chunk.score

            # Add chunk detail
            chunk_detail = ChunkDetail(
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.chunk_index,
                chunk_text=chunk.chunk_text,
                score=chunk.score,
            )
            article_scores[article_id]["chunks"].append(chunk_detail)

            # Store metadata (from first chunk encountered)
            if not article_scores[article_id]["metadata"]:
                article_scores[article_id]["metadata"] = {
                    "title": chunk.article_title or "Unknown Title",
                    "source_name": chunk.source_name or "Unknown Source",
                    "published_at": None,  # We don't have this in ChunkSearchResult
                }

        # Build ArticleResult objects
        articles = []
        for article_id, data in article_scores.items():
            article_result = ArticleResult(
                article_id=article_id,
                title=data["metadata"]["title"],
                source_name=data["metadata"]["source_name"],
                published_at=data["metadata"]["published_at"],
                relevance_score=data["score"],
                relevant_chunks=data["chunks"] if self.include_chunks else [],
                chunk_count=len(data["chunks"]),
            )
            articles.append(article_result)

        # Sort by relevance score (descending)
        articles.sort(key=lambda x: x.relevance_score, reverse=True)

        # Limit to max_articles
        articles = articles[: self.max_articles]

        logger.info(
            f"Aggregated {len(chunks)} chunks → {len(articles)} articles (threshold={self.score_threshold})"
        )

        return articles
