"""
Article Aggregation Service

Aggregates chunk-level scores to article-level results.
Uses maximum chunk score to measure article relevance.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List
from uuid import UUID

from app.config.settings import settings
from app.core.logging import get_logger
from app.services.repository import ArticleRepository
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
    relevance_score: float  # Maximum chunk score (0-10 scale)
    url: str
    relevant_chunks: List[ChunkDetail]
    chunk_count: int
    content: str | None = None  # Full article content for verification

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
            "url": self.url,
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

    Strategy: Maximum Score
    - Only consider chunks with score >= threshold
    - Use maximum chunk score as article relevance score
    - Articles with the best matching chunk rank higher
    """

    def __init__(self, db=None):
        self.max_articles = settings.retrieval.aggregation.max_articles
        self.include_chunks = settings.retrieval.aggregation.include_chunks
        self.min_chunk_score = settings.retrieval.aggregation.min_chunk_score
        self.db = db
        self.article_repository = ArticleRepository()

    async def aggregate_to_articles(
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

        # Group chunks by article and track max score
        # Format: {article_id: {"max_score": float, "chunks": [ChunkDetail, ...], "metadata": {...}}}
        article_data: Dict[UUID, Dict] = defaultdict(
            lambda: {"max_score": 0.0, "chunks": [], "metadata": {}}
        )

        for chunk in chunks:
            article_id = chunk.article_id

            # Track maximum score
            if chunk.score > article_data[article_id]["max_score"]:
                article_data[article_id]["max_score"] = chunk.score

            # Add chunk detail
            chunk_detail = ChunkDetail(
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.chunk_index,
                chunk_text=chunk.chunk_text,
                score=chunk.score,
            )
            article_data[article_id]["chunks"].append(chunk_detail)

            # Store metadata (from first chunk encountered)
            if not article_data[article_id]["metadata"]:
                article_data[article_id]["metadata"] = {
                    "title": chunk.article_title or "Unknown Title",
                    "source_name": chunk.source_name or "Unknown Source",
                    "published_at": None,  # We don't have this in ChunkSearchResult
                }

        # Fetch article URLs and content from the database if a session is available
        article_metadata = {}
        if self.db and article_data:
            article_metadata = await self.article_repository.get_metadata_by_ids(
                self.db, list(article_data.keys())
            )

        # Article filtering threshold (loaded from config)
        MIN_CHUNK_SCORE = self.min_chunk_score

        # Build ArticleResult objects with filtering
        articles = []
        filtered_count = 0
        for article_id, data in article_data.items():
            chunks = data["chunks"]
            max_score = data["max_score"]
            chunk_count = len(chunks)

            # Validation: check max chunk score threshold
            if max_score < MIN_CHUNK_SCORE:
                filtered_count += 1
                logger.debug(
                    f"Filtered article {article_id}: "
                    f"max={max_score:.2f} (min={MIN_CHUNK_SCORE})"
                )
                continue

            metadata = article_metadata.get(article_id, {})
            article_result = ArticleResult(
                article_id=article_id,
                title=data["metadata"]["title"],
                source_name=data["metadata"]["source_name"],
                published_at=metadata.get(
                    "published_at", data["metadata"]["published_at"]
                ),
                relevance_score=max_score,  # Use maximum chunk score
                url=metadata.get("url", ""),  # Empty string if not found
                relevant_chunks=data["chunks"] if self.include_chunks else [],
                chunk_count=chunk_count,
                content=metadata.get(
                    "content"
                ),  # Full article content for verification
            )
            articles.append(article_result)

        if filtered_count > 0:
            logger.info(
                f"Max score filtering: {filtered_count} articles removed "
                f"(max_score < {MIN_CHUNK_SCORE})"
            )

        # Sort by relevance score (descending)
        articles.sort(key=lambda x: x.relevance_score, reverse=True)

        # Limit to max_articles
        articles = articles[: self.max_articles]

        logger.info(f"Aggregated {len(chunks)} chunks → {len(articles)} articles")

        return articles
