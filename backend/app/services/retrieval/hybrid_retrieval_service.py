"""
Hybrid Retrieval Service

Combines vector similarity search and BM25 keyword search for multi-query retrieval.
"""

from typing import List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.logging import get_logger
from app.services.retrieval.bm25_search_service import (
    BM25SearchService,
    ChunkSearchResult,
)
from app.services.retrieval.vector_search_service import VectorSearchService

logger = get_logger(__name__)


class HybridRetrievalService:
    """
    Hybrid retrieval combining vector and BM25 search.

    Runs both search methods in parallel for each query and returns both result sets.
    Results are later fused using Reciprocal Rank Fusion (RRF).
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.vector_service = VectorSearchService(session)
        self.bm25_service = BM25SearchService(session)
        self.enable_bm25 = settings.retrieval.hybrid.enable_bm25
        self.enable_vector = settings.retrieval.hybrid.enable_vector

    async def search_single_query(
        self,
        query_text: str,
        query_embedding: List[float],
        top_k: int | None = None,
    ) -> Tuple[List[ChunkSearchResult], List[ChunkSearchResult]]:
        """
        Run hybrid search (vector + BM25) for a single query.

        Args:
            query_text: Text query for BM25 search
            query_embedding: Vector embedding for semantic search
            top_k: Number of results per search method

        Returns:
            Tuple of (vector_results, bm25_results)
        """
        tasks = []

        # Add vector search task if enabled
        if self.enable_vector:
            tasks.append(self.vector_service.search(query_embedding, top_k))
        else:
            tasks.append(self._empty_results())

        # Add BM25 search task if enabled
        if self.enable_bm25:
            tasks.append(self.bm25_service.search(query_text, top_k))
        else:
            tasks.append(self._empty_results())

        # Run searches sequentially to avoid SQLAlchemy session concurrency issues
        # (both services share the same AsyncSession which doesn't support concurrent operations)
        vector_results = await tasks[0] if tasks else []
        bm25_results = await tasks[1] if len(tasks) > 1 else []

        logger.info(
            f"Hybrid search for query: vector={len(vector_results)}, bm25={len(bm25_results)}"
        )

        return vector_results, bm25_results

    async def search_multi_query(
        self,
        queries: List[Tuple[str, List[float]]],
        top_k: int | None = None,
    ) -> List[List[ChunkSearchResult]]:
        """
        Run hybrid search for multiple queries.

        Each query produces 2 result lists (vector + BM25), so N queries produce 2N lists.

        Args:
            queries: List of (query_text, query_embedding) tuples
            top_k: Number of results per search method

        Returns:
            List of result lists (2N lists for N queries)
        """
        all_result_lists = []

        # Run hybrid search for each query
        for query_text, query_embedding in queries:
            vector_results, bm25_results = await self.search_single_query(
                query_text, query_embedding, top_k
            )

            # Add both result lists
            all_result_lists.append(vector_results)
            all_result_lists.append(bm25_results)

        logger.info(
            f"Multi-query hybrid search: {len(queries)} queries → {len(all_result_lists)} result lists"
        )

        return all_result_lists

    async def _empty_results(self) -> List[ChunkSearchResult]:
        """Return empty results list (for disabled search methods)"""
        return []
