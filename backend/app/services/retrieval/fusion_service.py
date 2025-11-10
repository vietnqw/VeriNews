"""
Result Fusion Service

Implements Reciprocal Rank Fusion (RRF) for combining multiple ranked result lists.
"""

from collections import defaultdict
from typing import Dict, List
from uuid import UUID

from app.config.settings import settings
from app.core.logging import get_logger
from app.services.retrieval.bm25_search_service import ChunkSearchResult

logger = get_logger(__name__)


class FusionService:
    """
    Result fusion using Reciprocal Rank Fusion (RRF).

    RRF is a simple yet effective method for combining multiple ranked lists.
    It's rank-based (not score-based), so it works well even when different
    retrieval methods use incomparable scoring functions.

    Formula: RRF(chunk) = sum over all lists: 1 / (k + rank(chunk in list))
    where k is a constant (typically 60).
    """

    def __init__(self):
        self.rrf_k = settings.retrieval.fusion.rrf_k

    def reciprocal_rank_fusion(
        self,
        result_lists: List[List[ChunkSearchResult]],
        k: int | None = None,
    ) -> List[ChunkSearchResult]:
        """
        Apply Reciprocal Rank Fusion to merge multiple ranked lists.

        Args:
            result_lists: List of ranked result lists (each from a different search)
            k: RRF constant (defaults to config value, typically 60)

        Returns:
            Single merged list of ChunkSearchResult, sorted by RRF score (highest first)
        """
        if k is None:
            k = self.rrf_k

        # Collect RRF scores for each unique chunk
        # Format: {chunk_id: rrf_score}
        rrf_scores: Dict[UUID, float] = defaultdict(float)

        # Also keep track of chunk objects and their best individual score
        # Format: {chunk_id: (chunk_object, max_individual_score)}
        chunk_objects: Dict[UUID, tuple[ChunkSearchResult, float]] = {}

        # Process each result list
        for list_idx, result_list in enumerate(result_lists):
            for rank, chunk_result in enumerate(result_list, start=1):
                chunk_id = chunk_result.chunk_id

                # Calculate RRF contribution from this list
                rrf_contribution = 1.0 / (k + rank)
                rrf_scores[chunk_id] += rrf_contribution

                # Keep track of chunk object and best individual score
                if chunk_id not in chunk_objects:
                    chunk_objects[chunk_id] = (chunk_result, chunk_result.score)
                else:
                    # Keep the chunk object with the higher individual score
                    _, current_best_score = chunk_objects[chunk_id]
                    if chunk_result.score > current_best_score:
                        chunk_objects[chunk_id] = (chunk_result, chunk_result.score)

        # Create final result list with RRF scores
        fused_results = []
        for chunk_id, rrf_score in rrf_scores.items():
            chunk_result, _ = chunk_objects[chunk_id]

            # Create a new ChunkSearchResult with RRF score
            fused_chunk = ChunkSearchResult(
                chunk_id=chunk_result.chunk_id,
                chunk_text=chunk_result.chunk_text,
                chunk_index=chunk_result.chunk_index,
                article_id=chunk_result.article_id,
                article_title=chunk_result.article_title,
                source_name=chunk_result.source_name,
                score=rrf_score,  # Replace original score with RRF score
            )
            fused_results.append(fused_chunk)

        # Sort by RRF score (descending)
        fused_results.sort(key=lambda x: x.score, reverse=True)

        logger.info(
            f"RRF fusion: {len(result_lists)} lists → {len(fused_results)} unique chunks (k={k})"
        )

        return fused_results
