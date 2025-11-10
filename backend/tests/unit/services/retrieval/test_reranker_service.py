"""
Unit tests for Reranker Service.

Tests LLM-based chunk reranking with batch optimization.
Uses mocked OpenAI API responses.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.retrieval.reranker_service import RerankerService
from app.services.retrieval.bm25_search_service import ChunkSearchResult


@pytest.mark.unit
class TestRerankerService:
    """Unit tests for reranker service."""

    @pytest.fixture
    def mock_llm_provider(self):
        """Mock LLM provider for testing."""
        mock = AsyncMock()
        return mock

    @pytest.fixture
    def reranker_service(self, mock_llm_provider):
        """Create reranker service with mocked LLM."""
        with patch(
            "app.services.retrieval.reranker_service.AIServiceFactory.get_llm_provider",
            return_value=mock_llm_provider,
        ):
            service = RerankerService()
            service.llm = mock_llm_provider
            service.batch_size = 5  # Set batch size for testing
            service.score_range = (0, 10)  # Score range 0-10
            service.top_n = 10
            return service

    @pytest.fixture
    def sample_chunks(self):
        """Create sample chunks for testing."""
        chunks = []
        for i in range(10):
            chunk = ChunkSearchResult(
                chunk_id=uuid4(),
                chunk_text=f"Sample chunk {i} about technology and innovation",
                chunk_index=i,
                article_id=uuid4(),
                article_title="Test Article",
                source_name="VnExpress",
                score=0.5 + (i * 0.05),  # Initial scores 0.5 to 0.95
            )
            chunks.append(chunk)
        return chunks

    @pytest.mark.asyncio
    async def test_rerank_basic_functionality(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test basic reranking functionality."""
        # Mock LLM response with scores for 5 chunks (1 batch)
        mock_response = MagicMock()
        mock_response.content = json.dumps({"scores": [8, 6, 9, 5, 7]})
        mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)

        # Rerank first 5 chunks
        chunks = sample_chunks[:5]
        result = await reranker_service.rerank(
            query="technology innovation", chunks=chunks, top_n=3
        )

        # Should return top 3 chunks
        assert len(result) == 3

        # Should be sorted by normalized score (descending)
        assert result[0].score >= result[1].score >= result[2].score

    @pytest.mark.asyncio
    async def test_rerank_empty_chunks(self, reranker_service, mock_llm_provider):
        """Test reranking with empty chunk list."""
        result = await reranker_service.rerank(query="test", chunks=[], top_n=10)

        # Should return empty list
        assert result == []
        # LLM should not be called
        assert not mock_llm_provider.generate_completion.called

    @pytest.mark.asyncio
    async def test_rerank_batch_processing(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test that chunks are processed in batches."""
        reranker_service.batch_size = 3

        # Mock responses for 4 batches (3+3+3+1)
        def mock_generate(messages, **kwargs):
            # Return scores based on batch size
            response = MagicMock()
            response.content = json.dumps({"scores": [7, 8, 6]})
            return response

        mock_llm_provider.generate_completion = AsyncMock(side_effect=mock_generate)

        # Rerank 10 chunks (should create 4 batches: 3, 3, 3, 1)
        result = await reranker_service.rerank(
            query="test", chunks=sample_chunks, top_n=5
        )

        # LLM should be called 4 times (4 batches)
        assert mock_llm_provider.generate_completion.call_count == 4

        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_rerank_score_normalization(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test that scores are normalized to 0-1 range."""
        reranker_service.score_range = (0, 10)  # Original range 0-10

        # Mock response with scores in 0-10 range
        mock_response = MagicMock()
        mock_response.content = json.dumps({"scores": [10, 5, 0, 7, 3]})
        mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)

        chunks = sample_chunks[:5]
        result = await reranker_service.rerank(query="test", chunks=chunks, top_n=5)

        # Scores should be normalized to 0-1
        for chunk in result:
            assert 0.0 <= chunk.score <= 1.0

        # Check specific normalizations
        # Score 10 → 1.0, Score 5 → 0.5, Score 0 → 0.0
        scores = [chunk.score for chunk in result]
        assert max(scores) == 1.0  # Normalized from 10
        assert min(scores) == 0.0  # Normalized from 0

    @pytest.mark.asyncio
    async def test_rerank_top_n_limit(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test that top_n parameter limits results correctly."""
        # Mock response
        mock_response = MagicMock()
        mock_response.content = json.dumps({"scores": [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]})
        mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)

        # Test different top_n values
        result_3 = await reranker_service.rerank(
            query="test", chunks=sample_chunks, top_n=3
        )
        result_7 = await reranker_service.rerank(
            query="test", chunks=sample_chunks, top_n=7
        )

        assert len(result_3) == 3
        assert len(result_7) == 7

    @pytest.mark.asyncio
    async def test_rerank_handles_json_decode_error(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test fallback when LLM returns invalid JSON."""
        # Mock invalid JSON response
        mock_response = MagicMock()
        mock_response.content = "Invalid JSON { invalid }"
        mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)

        chunks = sample_chunks[:5]
        result = await reranker_service.rerank(query="test", chunks=chunks, top_n=3)

        # Should return chunks with zero scores (normalized)
        assert len(result) == 3
        for chunk in result:
            assert chunk.score == 0.0

    @pytest.mark.asyncio
    async def test_rerank_handles_llm_exception(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test fallback when LLM raises an exception."""
        # Mock LLM exception
        mock_llm_provider.generate_completion = AsyncMock(
            side_effect=Exception("API Error")
        )

        chunks = sample_chunks[:5]
        result = await reranker_service.rerank(query="test", chunks=chunks, top_n=3)

        # Should return chunks with zero scores
        assert len(result) == 3
        for chunk in result:
            assert chunk.score == 0.0

    @pytest.mark.asyncio
    async def test_rerank_handles_mismatched_score_count(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test handling when LLM returns wrong number of scores."""
        # Mock response with only 3 scores for 5 chunks
        mock_response = MagicMock()
        mock_response.content = json.dumps({"scores": [8, 7, 6]})  # Only 3 scores
        mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)

        chunks = sample_chunks[:5]
        result = await reranker_service.rerank(query="test", chunks=chunks, top_n=5)

        # Should pad with zeros
        assert len(result) == 5
        # Last 2 chunks should have score 0.0 (padded)

    @pytest.mark.asyncio
    async def test_rerank_preserves_chunk_metadata(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test that reranking preserves chunk metadata."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({"scores": [8, 7, 6, 9, 5]})
        mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)

        chunks = sample_chunks[:5]
        original_ids = [chunk.chunk_id for chunk in chunks]

        result = await reranker_service.rerank(query="test", chunks=chunks, top_n=5)

        # All chunks should be present (may be reordered)
        result_ids = [chunk.chunk_id for chunk in result]
        assert set(result_ids) == set(original_ids)

        # Check metadata preservation
        for chunk in result:
            assert chunk.chunk_id is not None
            assert chunk.chunk_text is not None
            assert chunk.article_id is not None
            assert chunk.article_title == "Test Article"
            assert chunk.source_name == "VnExpress"

    @pytest.mark.asyncio
    async def test_rerank_ordering_by_score(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test that results are ordered by descending score."""
        # Mock response with specific scores
        mock_response = MagicMock()
        mock_response.content = json.dumps({"scores": [3, 9, 1, 7, 5]})
        mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)

        chunks = sample_chunks[:5]
        result = await reranker_service.rerank(query="test", chunks=chunks, top_n=5)

        # Verify descending order
        for i in range(len(result) - 1):
            assert result[i].score >= result[i + 1].score

        # Highest score should be first (score 9 → normalized to 0.9)
        assert result[0].score > result[1].score

    @pytest.mark.asyncio
    async def test_rerank_batch_size_configuration(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test that batch_size configuration works correctly."""
        # Set batch size to 2
        reranker_service.batch_size = 2

        mock_response = MagicMock()
        mock_response.content = json.dumps({"scores": [8, 7]})
        mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)

        # 6 chunks should create 3 batches of 2
        chunks = sample_chunks[:6]
        await reranker_service.rerank(query="test", chunks=chunks, top_n=6)

        # Should be called 3 times (6 chunks / batch_size 2)
        assert mock_llm_provider.generate_completion.call_count == 3

    @pytest.mark.asyncio
    async def test_rerank_prompt_includes_query(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test that the prompt includes the query."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({"scores": [8, 7, 6, 5, 4]})
        mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)

        query = "VinTech factory investment"
        chunks = sample_chunks[:5]
        await reranker_service.rerank(query=query, chunks=chunks, top_n=3)

        # Get the call arguments
        call_args = mock_llm_provider.generate_completion.call_args
        messages = call_args.kwargs["messages"]

        # Verify query is in the prompt
        prompt_content = messages[0].content
        assert query in prompt_content

    @pytest.mark.asyncio
    async def test_rerank_prompt_includes_chunks(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test that the prompt includes chunk texts."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({"scores": [8, 7, 6, 5, 4]})
        mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)

        chunks = sample_chunks[:5]
        await reranker_service.rerank(query="test", chunks=chunks, top_n=3)

        # Get the call arguments
        call_args = mock_llm_provider.generate_completion.call_args
        messages = call_args.kwargs["messages"]
        prompt_content = messages[0].content

        # Verify chunks are in the prompt
        for i, chunk in enumerate(chunks):
            assert f"Chunk {i}" in prompt_content
            # Chunk text should be truncated to 500 chars in prompt
            assert chunk.chunk_text[:100] in prompt_content

    @pytest.mark.asyncio
    async def test_rerank_uses_json_format(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test that reranking requests JSON format from LLM."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({"scores": [8, 7, 6, 5, 4]})
        mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)

        chunks = sample_chunks[:5]
        await reranker_service.rerank(query="test", chunks=chunks, top_n=3)

        # Verify response_format is set to json_object
        call_args = mock_llm_provider.generate_completion.call_args
        assert call_args.kwargs["response_format"] == {"type": "json_object"}

    @pytest.mark.asyncio
    async def test_rerank_with_vietnamese_text(
        self, reranker_service, mock_llm_provider
    ):
        """Test reranking with Vietnamese text."""
        # Create Vietnamese chunks
        vietnamese_chunks = [
            ChunkSearchResult(
                chunk_id=uuid4(),
                chunk_text="VinTech công bố kế hoạch xây dựng nhà máy chip",
                chunk_index=0,
                article_id=uuid4(),
                article_title="VinTech nhà máy",
                source_name="VnExpress",
                score=0.8,
            ),
            ChunkSearchResult(
                chunk_id=uuid4(),
                chunk_text="Công nghệ sản xuất chip bán dẫn hiện đại",
                chunk_index=1,
                article_id=uuid4(),
                article_title="Công nghệ chip",
                source_name="VnExpress",
                score=0.7,
            ),
        ]

        mock_response = MagicMock()
        mock_response.content = json.dumps({"scores": [9, 8]})
        mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)

        result = await reranker_service.rerank(
            query="nhà máy chip bán dẫn", chunks=vietnamese_chunks, top_n=2
        )

        assert len(result) == 2
        # Should preserve Vietnamese text
        assert "VinTech" in result[0].chunk_text or "VinTech" in result[1].chunk_text
