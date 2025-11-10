"""
Unit tests for Hybrid Retrieval Service.

Tests coordination of vector and BM25 search for multi-query retrieval.
Uses mocked search services.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.retrieval.hybrid_retrieval_service import HybridRetrievalService
from app.services.retrieval.bm25_search_service import ChunkSearchResult


@pytest.mark.unit
class TestHybridRetrievalService:
    """Unit tests for hybrid retrieval service."""

    @pytest.fixture
    def mock_session(self):
        """Mock database session."""
        return MagicMock()

    @pytest.fixture
    def sample_chunks(self):
        """Create sample chunk results."""
        chunks = []
        for i in range(5):
            chunk = ChunkSearchResult(
                chunk_id=uuid4(),
                chunk_text=f"Sample chunk {i}",
                chunk_index=i,
                article_id=uuid4(),
                article_title="Test Article",
                source_name="VnExpress",
                score=0.8 - (i * 0.1),
            )
            chunks.append(chunk)
        return chunks

    @pytest.fixture
    def hybrid_service(self, mock_session):
        """Create hybrid retrieval service with mocked dependencies."""
        with (
            patch(
                "app.services.retrieval.hybrid_retrieval_service.VectorSearchService"
            ) as mock_vector,
            patch(
                "app.services.retrieval.hybrid_retrieval_service.BM25SearchService"
            ) as mock_bm25,
        ):
            service = HybridRetrievalService(session=mock_session)
            service.vector_service = mock_vector.return_value
            service.bm25_service = mock_bm25.return_value
            service.enable_vector = True
            service.enable_bm25 = True
            return service

    @pytest.mark.asyncio
    async def test_search_single_query_both_enabled(
        self, hybrid_service, sample_chunks
    ):
        """Test single query search with both vector and BM25 enabled."""
        # Mock search results
        vector_results = sample_chunks[:3]
        bm25_results = sample_chunks[2:]

        hybrid_service.vector_service.search = AsyncMock(return_value=vector_results)
        hybrid_service.bm25_service.search = AsyncMock(return_value=bm25_results)

        query_text = "VinTech nhà máy"
        query_embedding = [0.5] * 1536

        vector_res, bm25_res = await hybrid_service.search_single_query(
            query_text, query_embedding, top_k=10
        )

        # Should return results from both searches
        assert len(vector_res) == 3
        assert len(bm25_res) == 3

        # Both searches should be called
        hybrid_service.vector_service.search.assert_called_once()
        hybrid_service.bm25_service.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_single_query_vector_only(self, hybrid_service, sample_chunks):
        """Test single query search with only vector search enabled."""
        hybrid_service.enable_vector = True
        hybrid_service.enable_bm25 = False

        vector_results = sample_chunks[:3]
        hybrid_service.vector_service.search = AsyncMock(return_value=vector_results)
        hybrid_service.bm25_service.search = AsyncMock(return_value=[])

        query_text = "test query"
        query_embedding = [0.5] * 1536

        vector_res, bm25_res = await hybrid_service.search_single_query(
            query_text, query_embedding, top_k=10
        )

        # Should return vector results and empty BM25
        assert len(vector_res) == 3
        assert len(bm25_res) == 0

    @pytest.mark.asyncio
    async def test_search_single_query_bm25_only(self, hybrid_service, sample_chunks):
        """Test single query search with only BM25 enabled."""
        hybrid_service.enable_vector = False
        hybrid_service.enable_bm25 = True

        bm25_results = sample_chunks[:3]
        hybrid_service.vector_service.search = AsyncMock(return_value=[])
        hybrid_service.bm25_service.search = AsyncMock(return_value=bm25_results)

        query_text = "test query"
        query_embedding = [0.5] * 1536

        vector_res, bm25_res = await hybrid_service.search_single_query(
            query_text, query_embedding, top_k=10
        )

        # Should return empty vector and BM25 results
        assert len(vector_res) == 0
        assert len(bm25_res) == 3

    @pytest.mark.asyncio
    async def test_search_single_query_both_disabled(self, hybrid_service):
        """Test single query search with both searches disabled."""
        hybrid_service.enable_vector = False
        hybrid_service.enable_bm25 = False

        query_text = "test query"
        query_embedding = [0.5] * 1536

        vector_res, bm25_res = await hybrid_service.search_single_query(
            query_text, query_embedding, top_k=10
        )

        # Both should be empty
        assert len(vector_res) == 0
        assert len(bm25_res) == 0

    @pytest.mark.asyncio
    async def test_search_single_query_passes_top_k(
        self, hybrid_service, sample_chunks
    ):
        """Test that top_k parameter is passed to search services."""
        hybrid_service.vector_service.search = AsyncMock(return_value=sample_chunks[:5])
        hybrid_service.bm25_service.search = AsyncMock(return_value=sample_chunks[:5])

        query_text = "test"
        query_embedding = [0.5] * 1536
        top_k = 20

        await hybrid_service.search_single_query(query_text, query_embedding, top_k)

        # Verify top_k was passed to both services
        hybrid_service.vector_service.search.assert_called_with(query_embedding, top_k)
        hybrid_service.bm25_service.search.assert_called_with(query_text, top_k)

    @pytest.mark.asyncio
    async def test_search_multi_query_basic(self, hybrid_service, sample_chunks):
        """Test multi-query search with 2 queries."""
        # Mock search results
        hybrid_service.vector_service.search = AsyncMock(return_value=sample_chunks[:3])
        hybrid_service.bm25_service.search = AsyncMock(return_value=sample_chunks[2:])

        queries = [
            ("query 1", [0.5] * 1536),
            ("query 2", [0.6] * 1536),
        ]

        result_lists = await hybrid_service.search_multi_query(queries, top_k=10)

        # Should return 2N lists for N queries (2 queries → 4 lists)
        assert len(result_lists) == 4

        # Each query produces 2 lists (vector + BM25)
        # Lists alternate: [vector_q1, bm25_q1, vector_q2, bm25_q2]
        assert len(result_lists[0]) == 3  # vector results for query 1
        assert len(result_lists[1]) == 3  # bm25 results for query 1
        assert len(result_lists[2]) == 3  # vector results for query 2
        assert len(result_lists[3]) == 3  # bm25 results for query 2

    @pytest.mark.asyncio
    async def test_search_multi_query_single_query(self, hybrid_service, sample_chunks):
        """Test multi-query with only 1 query."""
        hybrid_service.vector_service.search = AsyncMock(return_value=sample_chunks[:3])
        hybrid_service.bm25_service.search = AsyncMock(return_value=sample_chunks[2:])

        queries = [("single query", [0.5] * 1536)]

        result_lists = await hybrid_service.search_multi_query(queries, top_k=10)

        # 1 query → 2 lists
        assert len(result_lists) == 2

    @pytest.mark.asyncio
    async def test_search_multi_query_many_queries(self, hybrid_service, sample_chunks):
        """Test multi-query with many queries."""
        hybrid_service.vector_service.search = AsyncMock(return_value=sample_chunks[:2])
        hybrid_service.bm25_service.search = AsyncMock(return_value=sample_chunks[:2])

        # 5 queries
        queries = [(f"query {i}", [0.5] * 1536) for i in range(5)]

        result_lists = await hybrid_service.search_multi_query(queries, top_k=10)

        # 5 queries → 10 lists (5 * 2)
        assert len(result_lists) == 10

    @pytest.mark.asyncio
    async def test_search_multi_query_empty_queries(self, hybrid_service):
        """Test multi-query with empty query list."""
        result_lists = await hybrid_service.search_multi_query([], top_k=10)

        # Should return empty list
        assert result_lists == []

    @pytest.mark.asyncio
    async def test_search_multi_query_result_list_ordering(
        self, hybrid_service, sample_chunks
    ):
        """Test that result lists are ordered correctly."""
        # Mock different results for each call
        call_count = 0

        async def mock_vector_search(embedding, top_k):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return sample_chunks[:2]  # First query vector results
            else:
                return sample_chunks[2:4]  # Second query vector results

        call_count_bm25 = 0

        async def mock_bm25_search(text, top_k):
            nonlocal call_count_bm25
            call_count_bm25 += 1
            if call_count_bm25 == 1:
                return sample_chunks[1:3]  # First query BM25 results
            else:
                return sample_chunks[3:5]  # Second query BM25 results

        hybrid_service.vector_service.search = AsyncMock(side_effect=mock_vector_search)
        hybrid_service.bm25_service.search = AsyncMock(side_effect=mock_bm25_search)

        queries = [
            ("query 1", [0.5] * 1536),
            ("query 2", [0.6] * 1536),
        ]

        result_lists = await hybrid_service.search_multi_query(queries, top_k=10)

        # Verify ordering: [vector_q1, bm25_q1, vector_q2, bm25_q2]
        assert len(result_lists[0]) == 2  # vector_q1
        assert len(result_lists[1]) == 2  # bm25_q1
        assert len(result_lists[2]) == 2  # vector_q2
        assert len(result_lists[3]) == 2  # bm25_q2

    @pytest.mark.asyncio
    async def test_search_multi_query_preserves_results(
        self, hybrid_service, sample_chunks
    ):
        """Test that multi-query preserves all chunk results."""
        vector_chunk_1 = sample_chunks[0]
        bm25_chunk_1 = sample_chunks[1]

        async def mock_vector_search(embedding, top_k):
            return [vector_chunk_1]

        async def mock_bm25_search(text, top_k):
            return [bm25_chunk_1]

        hybrid_service.vector_service.search = AsyncMock(side_effect=mock_vector_search)
        hybrid_service.bm25_service.search = AsyncMock(side_effect=mock_bm25_search)

        queries = [("test query", [0.5] * 1536)]

        result_lists = await hybrid_service.search_multi_query(queries, top_k=10)

        # Verify chunks are preserved
        assert result_lists[0][0].chunk_id == vector_chunk_1.chunk_id
        assert result_lists[1][0].chunk_id == bm25_chunk_1.chunk_id

    @pytest.mark.asyncio
    async def test_search_with_vietnamese_text(self, hybrid_service, sample_chunks):
        """Test search with Vietnamese query text."""
        hybrid_service.vector_service.search = AsyncMock(return_value=sample_chunks[:2])
        hybrid_service.bm25_service.search = AsyncMock(return_value=sample_chunks[:2])

        query_text = "VinTech xây dựng nhà máy chip bán dẫn"
        query_embedding = [0.5] * 1536

        vector_res, bm25_res = await hybrid_service.search_single_query(
            query_text, query_embedding, top_k=10
        )

        # Should handle Vietnamese text without errors
        assert len(vector_res) == 2
        assert len(bm25_res) == 2

        # Verify Vietnamese text was passed to BM25
        hybrid_service.bm25_service.search.assert_called_with(query_text, 10)

    @pytest.mark.asyncio
    async def test_search_handles_empty_results(self, hybrid_service):
        """Test handling when both searches return empty results."""
        hybrid_service.vector_service.search = AsyncMock(return_value=[])
        hybrid_service.bm25_service.search = AsyncMock(return_value=[])

        query_text = "nonexistent query"
        query_embedding = [0.5] * 1536

        vector_res, bm25_res = await hybrid_service.search_single_query(
            query_text, query_embedding, top_k=10
        )

        # Both should be empty
        assert vector_res == []
        assert bm25_res == []

    @pytest.mark.asyncio
    async def test_search_handles_search_exceptions(self, hybrid_service):
        """Test handling when search services raise exceptions."""
        # Mock vector search to raise exception
        hybrid_service.vector_service.search = AsyncMock(
            side_effect=Exception("Vector search error")
        )
        hybrid_service.bm25_service.search = AsyncMock(return_value=[])

        query_text = "test"
        query_embedding = [0.5] * 1536

        # Should propagate the exception (no error handling in service)
        with pytest.raises(Exception, match="Vector search error"):
            await hybrid_service.search_single_query(
                query_text, query_embedding, top_k=10
            )
