"""
Vector Similarity Search Service

Provides vector-based semantic search using pgvector and cosine similarity.
"""

from typing import List

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.logging import get_logger
from app.models.article_chunk import ArticleChunk
from app.services.retrieval.bm25_search_service import ChunkSearchResult

logger = get_logger(__name__)


class VectorSearchService:
    """
    Vector similarity search using pgvector.

    Uses cosine similarity (default) to find semantically similar chunks.
    Leverages IVFFlat index for fast approximate nearest neighbor search.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.top_k = settings.retrieval.vector_search.top_k
        self.similarity_metric = settings.retrieval.vector_search.similarity_metric

    async def search(
        self, query_embedding: List[float], top_k: int | None = None
    ) -> List[ChunkSearchResult]:
        """
        Search for chunks using vector similarity.

        Args:
            query_embedding: Query vector (1536 dimensions for text-embedding-3-small)
            top_k: Number of results to return (defaults to config value)

        Returns:
            List of ChunkSearchResult ordered by similarity (highest first)
        """
        if top_k is None:
            top_k = self.top_k

        # Choose distance operator based on similarity metric
        if self.similarity_metric == "cosine":
            # Cosine distance: <=> operator (lower is more similar)
            # Convert to similarity score: 1 - distance
            distance_col = ArticleChunk.embedding.cosine_distance(query_embedding)
            similarity_col = (1 - distance_col).label("score")
        elif self.similarity_metric == "l2":
            # L2 distance: <-> operator
            distance_col = ArticleChunk.embedding.l2_distance(query_embedding)
            # Convert distance to similarity score (inverse, normalized)
            similarity_col = (1 / (1 + distance_col)).label("score")
        elif self.similarity_metric == "inner_product":
            # Inner product: <#> operator (negative, so higher is more similar)
            similarity_col = (
                -ArticleChunk.embedding.max_inner_product(query_embedding)
            ).label("score")
        else:
            # Default to cosine
            distance_col = ArticleChunk.embedding.cosine_distance(query_embedding)
            similarity_col = (1 - distance_col).label("score")

        # Build the query
        stmt = (
            select(
                ArticleChunk.id,
                ArticleChunk.chunk_text,
                ArticleChunk.chunk_index,
                ArticleChunk.article_id,
                ArticleChunk.article_title,
                ArticleChunk.source_name,
                similarity_col,
            )
            .order_by(text("score DESC"))
            .limit(top_k)
        )

        result = await self.session.execute(stmt)
        rows = result.all()

        results = [
            ChunkSearchResult(
                chunk_id=row.id,
                chunk_text=row.chunk_text,
                chunk_index=row.chunk_index,
                article_id=row.article_id,
                article_title=row.article_title,
                source_name=row.source_name,
                score=float(row.score),
            )
            for row in rows
        ]

        logger.info(
            f"Vector search ({self.similarity_metric}) returned {len(results)} results"
        )

        return results
