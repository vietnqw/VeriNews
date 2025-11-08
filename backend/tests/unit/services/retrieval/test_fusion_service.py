"""
Unit tests for Reciprocal Rank Fusion (RRF) service.

Tests the mathematical correctness of the RRF algorithm used to merge
multiple ranked lists from vector and BM25 searches.
"""

import pytest
from uuid import uuid4

from app.services.retrieval.bm25_search_service import ChunkSearchResult
from app.services.retrieval.fusion_service import FusionService


@pytest.mark.unit
class TestFusionService:
    """Test suite for RRF fusion algorithm."""

    @pytest.fixture
    def fusion_service(self):
        """Provide a FusionService instance."""
        return FusionService()

    @pytest.fixture
    def sample_chunk_result(self):
        """Factory for creating ChunkSearchResult instances."""

        def _create_chunk(chunk_id=None, score=0.5, title="Test Article"):
            return ChunkSearchResult(
                chunk_id=chunk_id or uuid4(),
                chunk_text="Sample chunk text",
                chunk_index=0,
                article_id=uuid4(),
                article_title=title,
                source_name="Test Source",
                score=score,
            )

        return _create_chunk

    def test_rrf_single_list(self, fusion_service, sample_chunk_result):
        """Test RRF with a single result list (passthrough)."""
        chunk1 = sample_chunk_result(score=0.9)
        chunk2 = sample_chunk_result(score=0.7)
        chunk3 = sample_chunk_result(score=0.5)

        result_lists = [[chunk1, chunk2, chunk3]]

        fused = fusion_service.reciprocal_rank_fusion(result_lists, k=60)

        # Should maintain order
        assert len(fused) == 3
        assert fused[0].chunk_id == chunk1.chunk_id
        assert fused[1].chunk_id == chunk2.chunk_id
        assert fused[2].chunk_id == chunk3.chunk_id

        # Check RRF scores: 1/(60+rank)
        assert abs(fused[0].score - 1 / (60 + 1)) < 0.001  # rank=1
        assert abs(fused[1].score - 1 / (60 + 2)) < 0.001  # rank=2
        assert abs(fused[2].score - 1 / (60 + 3)) < 0.001  # rank=3

    def test_rrf_two_lists_no_overlap(self, fusion_service, sample_chunk_result):
        """Test RRF with two lists having no common chunks."""
        # List 1
        chunk_a1 = sample_chunk_result(score=0.9)
        chunk_a2 = sample_chunk_result(score=0.8)

        # List 2
        chunk_b1 = sample_chunk_result(score=0.7)
        chunk_b2 = sample_chunk_result(score=0.6)

        result_lists = [
            [chunk_a1, chunk_a2],
            [chunk_b1, chunk_b2],
        ]

        fused = fusion_service.reciprocal_rank_fusion(result_lists, k=60)

        # Should have all 4 chunks
        assert len(fused) == 4

        # Verify RRF scores
        chunk_ids = {chunk.chunk_id for chunk in fused}
        assert chunk_a1.chunk_id in chunk_ids
        assert chunk_a2.chunk_id in chunk_ids
        assert chunk_b1.chunk_id in chunk_ids
        assert chunk_b2.chunk_id in chunk_ids

    def test_rrf_two_lists_with_overlap(self, fusion_service, sample_chunk_result):
        """Test RRF with overlapping chunks (appears in both lists)."""
        # Shared chunk
        shared_chunk_id = uuid4()
        chunk_shared_list1 = sample_chunk_result(chunk_id=shared_chunk_id, score=0.9)
        chunk_shared_list2 = sample_chunk_result(chunk_id=shared_chunk_id, score=0.8)

        # Unique chunks
        chunk_unique1 = sample_chunk_result(score=0.7)
        chunk_unique2 = sample_chunk_result(score=0.6)

        result_lists = [
            [chunk_shared_list1, chunk_unique1],  # rank 1, 2
            [chunk_shared_list2, chunk_unique2],  # rank 1, 2
        ]

        fused = fusion_service.reciprocal_rank_fusion(result_lists, k=60)

        # Should have 3 unique chunks (shared appears once)
        assert len(fused) == 3

        # Shared chunk should have highest score (appears in both lists at rank 1)
        # Score = 1/(60+1) + 1/(60+1) = 2/61
        top_chunk = fused[0]
        assert top_chunk.chunk_id == shared_chunk_id
        expected_score = 1 / (60 + 1) + 1 / (60 + 1)
        assert abs(top_chunk.score - expected_score) < 0.001

    def test_rrf_different_k_values(self, fusion_service, sample_chunk_result):
        """Test RRF with different k parameter values."""
        chunk1 = sample_chunk_result(score=0.9)
        chunk2 = sample_chunk_result(score=0.7)

        result_lists = [[chunk1, chunk2]]

        # Test with k=10
        fused_k10 = fusion_service.reciprocal_rank_fusion(result_lists, k=10)
        assert abs(fused_k10[0].score - 1 / (10 + 1)) < 0.001

        # Test with k=100
        fused_k100 = fusion_service.reciprocal_rank_fusion(result_lists, k=100)
        assert abs(fused_k100[0].score - 1 / (100 + 1)) < 0.001

        # Higher k → lower scores
        assert fused_k10[0].score > fused_k100[0].score

    def test_rrf_empty_lists(self, fusion_service):
        """Test RRF with empty input lists."""
        result_lists = []
        fused = fusion_service.reciprocal_rank_fusion(result_lists, k=60)
        assert len(fused) == 0

    def test_rrf_lists_with_empty_sublists(self, fusion_service, sample_chunk_result):
        """Test RRF with some empty sublists."""
        chunk1 = sample_chunk_result(score=0.9)

        result_lists = [
            [],  # Empty list
            [chunk1],
            [],  # Another empty list
        ]

        fused = fusion_service.reciprocal_rank_fusion(result_lists, k=60)

        assert len(fused) == 1
        assert fused[0].chunk_id == chunk1.chunk_id

    def test_rrf_many_lists(self, fusion_service, sample_chunk_result):
        """Test RRF with many result lists (multi-query scenario)."""
        # Create 8 lists (4 queries * 2 search methods)
        result_lists = []
        all_chunk_ids = set()

        for i in range(8):
            chunk = sample_chunk_result(score=0.5 + i * 0.05)
            result_lists.append([chunk])
            all_chunk_ids.add(chunk.chunk_id)

        fused = fusion_service.reciprocal_rank_fusion(result_lists, k=60)

        # Should have 8 chunks
        assert len(fused) == 8

        # All chunks present
        fused_chunk_ids = {chunk.chunk_id for chunk in fused}
        assert fused_chunk_ids == all_chunk_ids

    def test_rrf_score_monotonicity(self, fusion_service, sample_chunk_result):
        """Test that RRF scores are monotonically decreasing."""
        chunks = [sample_chunk_result(score=0.9 - i * 0.1) for i in range(5)]

        result_lists = [chunks]

        fused = fusion_service.reciprocal_rank_fusion(result_lists, k=60)

        # Scores should decrease monotonically
        for i in range(len(fused) - 1):
            assert fused[i].score >= fused[i + 1].score

    def test_rrf_mathematical_correctness(self, fusion_service, sample_chunk_result):
        """Test exact mathematical calculation of RRF."""
        # Create chunks with known ranks
        chunk_id = uuid4()
        chunk_list1 = sample_chunk_result(chunk_id=chunk_id, score=0.9)
        chunk_list2 = sample_chunk_result(chunk_id=chunk_id, score=0.8)
        chunk_list3 = sample_chunk_result(chunk_id=chunk_id, score=0.7)

        # Chunk appears in 3 lists at ranks 1, 2, 3
        result_lists = [
            [chunk_list1],  # rank 1
            [sample_chunk_result(), chunk_list2],  # rank 2
            [sample_chunk_result(), sample_chunk_result(), chunk_list3],  # rank 3
        ]

        fused = fusion_service.reciprocal_rank_fusion(result_lists, k=60)

        # Find the chunk
        target_chunk = next(c for c in fused if c.chunk_id == chunk_id)

        # Manual calculation: 1/(60+1) + 1/(60+2) + 1/(60+3)
        expected_score = 1 / (60 + 1) + 1 / (60 + 2) + 1 / (60 + 3)
        assert abs(target_chunk.score - expected_score) < 0.0001

    def test_rrf_preserves_chunk_metadata(self, fusion_service, sample_chunk_result):
        """Test that RRF preserves all chunk metadata except score."""
        original_chunk = sample_chunk_result(
            score=0.9,
            title="Original Title",
        )
        original_chunk.chunk_text = "Important chunk text"
        original_chunk.chunk_index = 5
        original_chunk.source_name = "VnExpress"

        result_lists = [[original_chunk]]

        fused = fusion_service.reciprocal_rank_fusion(result_lists, k=60)

        fused_chunk = fused[0]

        # Metadata should be preserved
        assert fused_chunk.chunk_text == "Important chunk text"
        assert fused_chunk.chunk_index == 5
        assert fused_chunk.article_title == "Original Title"
        assert fused_chunk.source_name == "VnExpress"

        # Only score should change
        assert fused_chunk.score != original_chunk.score
