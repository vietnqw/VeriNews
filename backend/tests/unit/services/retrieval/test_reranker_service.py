"""
Unit tests for Reranker Service.

Tests LLM-based chunk reranking with parallel worker optimization.
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
    """Unit tests for reranker service with parallel workers."""

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
            service.num_workers = 4  # Set num workers for testing
            service.worker_timeout = 7.0
            service.max_concurrent = 4
            service.score_threshold = 5  # 0-10 scale
            service.top_n = 10
            service.entity_filter_enabled = True
            service.min_entity_match_ratio = 0.2
            return service

    @pytest.fixture
    def sample_chunks(self):
        """Create sample chunks for testing."""
        chunks = []
        for i in range(20):
            chunk = ChunkSearchResult(
                chunk_id=uuid4(),
                chunk_text=f"Sample chunk {i} about technology and innovation",
                chunk_index=i,
                article_id=uuid4(),
                article_title="Test Article",
                source_name="VnExpress",
                score=0.3 + (i * 0.03),  # Initial RRF scores 0.3 to 0.87
            )
            chunks.append(chunk)
        return chunks

    @pytest.mark.asyncio
    async def test_rerank_basic_functionality(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test basic reranking functionality with parallel workers."""

        # Mock LLM response with scores (using new format with passage IDs)
        # 4 workers, 20 chunks = 5 chunks per worker
        def mock_generate(messages, **kwargs):
            response = MagicMock()
            # Return scores for 5 chunks per worker
            response.content = json.dumps(
                {"id0": 8, "id1": 9, "id2": 7, "id3": 6, "id4": 8}
            )
            return response

        mock_llm_provider.generate_completion = AsyncMock(side_effect=mock_generate)

        result = await reranker_service.rerank(
            query="technology innovation", chunks=sample_chunks, top_n=10
        )

        # Should return top 10 chunks
        assert len(result) == 10

        # Should be sorted by score (descending)
        for i in range(len(result) - 1):
            assert result[i].score >= result[i + 1].score

        # LLM should be called 4 times (one per worker)
        assert mock_llm_provider.generate_completion.call_count == 4

    @pytest.mark.asyncio
    async def test_rerank_empty_chunks(self, reranker_service, mock_llm_provider):
        """Test reranking with empty chunk list."""
        result = await reranker_service.rerank(query="test", chunks=[], top_n=10)

        # Should return empty list
        assert result == []
        # LLM should not be called
        assert not mock_llm_provider.generate_completion.called

    @pytest.mark.asyncio
    async def test_rerank_round_robin_batching(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test that chunks are distributed round-robin to workers."""
        reranker_service.num_workers = 3

        # Mock responses for 3 workers
        def mock_generate(messages, **kwargs):
            response = MagicMock()
            # Each worker handles different number of chunks (20 chunks / 3 workers)
            # Worker 0 & 1 get 7 chunks, worker 2 gets 6 chunks
            response.content = json.dumps(
                {
                    "id0": 7,
                    "id1": 8,
                    "id2": 6,
                    "id3": 9,
                    "id4": 5,
                    "id5": 7,
                    "id6": 8,
                }
            )
            return response

        mock_llm_provider.generate_completion = AsyncMock(side_effect=mock_generate)

        result = await reranker_service.rerank(
            query="test", chunks=sample_chunks, top_n=10
        )

        # LLM should be called 3 times (one per worker)
        assert mock_llm_provider.generate_completion.call_count == 3
        assert len(result) == 10

    @pytest.mark.asyncio
    async def test_rerank_score_normalization(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test that scores are kept in 0-10 range."""

        # Mock response with scores in 0-10 range
        def mock_generate(messages, **kwargs):
            response = MagicMock()
            response.content = json.dumps(
                {"id0": 10, "id1": 5, "id2": 7, "id3": 8, "id4": 6}
            )
            return response

        mock_llm_provider.generate_completion = AsyncMock(side_effect=mock_generate)

        chunks = sample_chunks[:20]
        result = await reranker_service.rerank(query="test", chunks=chunks, top_n=10)

        # Scores should be in 0-10 range
        for chunk in result:
            assert 0.0 <= chunk.score <= 10.0

        # Check that we have the max score of 10
        max_score = max(chunk.score for chunk in result)
        assert max_score == 10.0

    @pytest.mark.asyncio
    async def test_rerank_score_threshold_filtering(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test that chunks below score threshold are filtered out."""
        reranker_service.score_threshold = 5

        # Mock response with mix of scores above and below threshold
        def mock_generate(messages, **kwargs):
            response = MagicMock()
            # Some scores below threshold (0-4), some above (5-10)
            response.content = json.dumps(
                {"id0": 8, "id1": 3, "id3": 7, "id4": 6}
            )  # id2 excluded (below 5)
            return response

        mock_llm_provider.generate_completion = AsyncMock(side_effect=mock_generate)

        chunks = sample_chunks[:20]
        result = await reranker_service.rerank(query="test", chunks=chunks, top_n=10)

        # All results should have score >= threshold (normalized)
        normalized_threshold = (5 - 0) / (10 - 0)  # 0.5
        for chunk in result:
            assert chunk.score >= normalized_threshold

    @pytest.mark.asyncio
    async def test_rerank_worker_timeout_fallback(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test fallback to RRF scores when worker times out."""
        reranker_service.worker_timeout = 0.001  # Very short timeout

        # Mock slow response that will timeout
        async def slow_response(messages, **kwargs):
            import asyncio

            await asyncio.sleep(1)  # Longer than timeout
            response = MagicMock()
            response.content = json.dumps({"id0": 9})
            return response

        mock_llm_provider.generate_completion = AsyncMock(side_effect=slow_response)

        chunks = sample_chunks[:20]
        result = await reranker_service.rerank(query="test", chunks=chunks, top_n=10)

        # Should still return results (using fallback RRF scores)
        assert len(result) == 10

        # Scores should be the original RRF scores (fallback)
        # Check that some chunk has its original score preserved
        original_scores = [c.score for c in chunks]
        result_scores = [c.score for c in result]

        # At least some scores should match original (fallback used)
        assert any(score in original_scores for score in result_scores)

    @pytest.mark.asyncio
    async def test_rerank_handles_llm_exception(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test fallback when LLM raises an exception."""
        # Mock LLM exception
        mock_llm_provider.generate_completion = AsyncMock(
            side_effect=Exception("API Error")
        )

        chunks = sample_chunks[:20]
        result = await reranker_service.rerank(query="test", chunks=chunks, top_n=10)

        # Should return chunks with fallback RRF scores
        assert len(result) == 10

        # Scores should be original RRF scores (fallback)
        original_scores = sorted([c.score for c in chunks], reverse=True)
        result_scores = [c.score for c in result]

        # Top results should match top original scores
        assert result_scores[0] == original_scores[0]

    @pytest.mark.asyncio
    async def test_rerank_top_n_limit(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test that top_n parameter limits results correctly."""

        # Mock response
        def mock_generate(messages, **kwargs):
            response = MagicMock()
            response.content = json.dumps(
                {"id0": 9, "id1": 8, "id2": 7, "id3": 6, "id4": 5}
            )
            return response

        mock_llm_provider.generate_completion = AsyncMock(side_effect=mock_generate)

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
    async def test_rerank_preserves_chunk_metadata(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test that reranking preserves chunk metadata."""

        def mock_generate(messages, **kwargs):
            response = MagicMock()
            response.content = json.dumps(
                {"id0": 8, "id1": 7, "id2": 9, "id3": 6, "id4": 8}
            )
            return response

        mock_llm_provider.generate_completion = AsyncMock(side_effect=mock_generate)

        chunks = sample_chunks[:20]
        original_ids = [chunk.chunk_id for chunk in chunks]

        result = await reranker_service.rerank(query="test", chunks=chunks, top_n=10)

        # All returned chunks should be from original set
        result_ids = [chunk.chunk_id for chunk in result]
        assert all(chunk_id in original_ids for chunk_id in result_ids)

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

        def mock_generate(messages, **kwargs):
            response = MagicMock()
            response.content = json.dumps(
                {"id0": 5, "id1": 9, "id2": 3, "id3": 7, "id4": 8}
            )
            return response

        mock_llm_provider.generate_completion = AsyncMock(side_effect=mock_generate)

        chunks = sample_chunks[:20]
        result = await reranker_service.rerank(query="test", chunks=chunks, top_n=10)

        # Verify descending order
        for i in range(len(result) - 1):
            assert result[i].score >= result[i + 1].score

    @pytest.mark.asyncio
    async def test_rerank_num_workers_configuration(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test that num_workers configuration works correctly."""
        # Set num workers to 5
        reranker_service.num_workers = 5

        def mock_generate(messages, **kwargs):
            response = MagicMock()
            response.content = json.dumps({"id0": 8, "id1": 7, "id2": 9, "id3": 6})
            return response

        mock_llm_provider.generate_completion = AsyncMock(side_effect=mock_generate)

        # 20 chunks with 5 workers = 4 chunks per worker
        chunks = sample_chunks[:20]
        await reranker_service.rerank(query="test", chunks=chunks, top_n=10)

        # Should be called 5 times (one per worker)
        assert mock_llm_provider.generate_completion.call_count == 5

    @pytest.mark.asyncio
    async def test_rerank_prompt_includes_query(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test that the prompt includes the query."""

        def mock_generate(messages, **kwargs):
            response = MagicMock()
            response.content = json.dumps(
                {"id0": 8, "id1": 7, "id2": 6, "id3": 9, "id4": 5}
            )
            return response

        mock_llm_provider.generate_completion = AsyncMock(side_effect=mock_generate)

        query = "VinTech factory investment"
        chunks = sample_chunks[:20]
        await reranker_service.rerank(query=query, chunks=chunks, top_n=10)

        # Get the call arguments from first worker
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

        def mock_generate(messages, **kwargs):
            response = MagicMock()
            response.content = json.dumps(
                {"id0": 8, "id1": 7, "id2": 6, "id3": 9, "id4": 5}
            )
            return response

        mock_llm_provider.generate_completion = AsyncMock(side_effect=mock_generate)

        chunks = sample_chunks[:20]
        await reranker_service.rerank(query="test", chunks=chunks, top_n=10)

        # Get the call arguments from any worker
        call_args = mock_llm_provider.generate_completion.call_args
        messages = call_args.kwargs["messages"]
        prompt_content = messages[0].content

        # Verify passages are in the prompt (using XML format)
        assert "<passage id=" in prompt_content
        assert "</passage>" in prompt_content

    @pytest.mark.asyncio
    async def test_rerank_uses_json_format(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test that reranking requests JSON format from LLM."""

        def mock_generate(messages, **kwargs):
            response = MagicMock()
            response.content = json.dumps(
                {"id0": 8, "id1": 7, "id2": 6, "id3": 9, "id4": 5}
            )
            return response

        mock_llm_provider.generate_completion = AsyncMock(side_effect=mock_generate)

        chunks = sample_chunks[:20]
        await reranker_service.rerank(query="test", chunks=chunks, top_n=10)

        # Verify response_format is set to json_object
        call_args = mock_llm_provider.generate_completion.call_args
        assert call_args.kwargs["response_format"] == {"type": "json_object"}

    @pytest.mark.asyncio
    async def test_rerank_with_vietnamese_text(
        self, reranker_service, mock_llm_provider
    ):
        """Test reranking with Vietnamese text."""
        # Create Vietnamese chunks
        vietnamese_chunks = []
        for i in range(20):
            chunk = ChunkSearchResult(
                chunk_id=uuid4(),
                chunk_text=f"VinTech công bố kế hoạch xây dựng nhà máy chip {i}",
                chunk_index=i,
                article_id=uuid4(),
                article_title="VinTech nhà máy",
                source_name="VnExpress",
                score=0.5 + (i * 0.02),
            )
            vietnamese_chunks.append(chunk)

        def mock_generate(messages, **kwargs):
            response = MagicMock()
            response.content = json.dumps(
                {"id0": 9, "id1": 8, "id2": 7, "id3": 6, "id4": 5}
            )
            return response

        mock_llm_provider.generate_completion = AsyncMock(side_effect=mock_generate)

        result = await reranker_service.rerank(
            query="nhà máy chip bán dẫn", chunks=vietnamese_chunks, top_n=10
        )

        assert len(result) == 10
        # Should preserve Vietnamese text
        assert all("VinTech" in chunk.chunk_text for chunk in result)

    @pytest.mark.asyncio
    async def test_rerank_prompt_format(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test that the scoring prompt uses the graded fact-checking format."""

        def mock_generate(messages, **kwargs):
            response = MagicMock()
            response.content = json.dumps(
                {"id0": 8, "id1": 7, "id2": 9, "id3": 6, "id4": 5}
            )
            return response

        mock_llm_provider.generate_completion = AsyncMock(side_effect=mock_generate)

        chunks = sample_chunks[:20]
        await reranker_service.rerank(query="test", chunks=chunks, top_n=10)

        # Get the prompt
        call_args = mock_llm_provider.generate_completion.call_args
        messages = call_args.kwargs["messages"]
        prompt_content = messages[0].content

        # Verify the fact-checking grading rubric and XML input format
        assert "fact-checking" in prompt_content
        assert "grading_scale" in prompt_content
        assert "PERFECT match" in prompt_content
        assert "<query>" in prompt_content
        assert "<passages>" in prompt_content

    @pytest.mark.asyncio
    async def test_rerank_partial_worker_success(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test that reranking continues even if some workers fail."""
        call_count = 0

        # First 2 workers succeed, last 2 fail
        async def mixed_response(messages, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                response = MagicMock()
                response.content = json.dumps(
                    {"id0": 8, "id1": 7, "id2": 9, "id3": 6, "id4": 5}
                )
                return response
            else:
                raise Exception("Worker failed")

        mock_llm_provider.generate_completion = AsyncMock(side_effect=mixed_response)

        chunks = sample_chunks[:20]
        result = await reranker_service.rerank(query="test", chunks=chunks, top_n=10)

        # Should still return results (partial success + fallback)
        assert len(result) == 10

        # All 4 workers should have been attempted
        assert mock_llm_provider.generate_completion.call_count == 4

    @pytest.mark.asyncio
    async def test_rerank_entity_filtering(self, reranker_service, mock_llm_provider):
        """Test entity-based filtering before reranking."""
        # Create chunks with and without target entities
        chunks_with_entities = []
        for i in range(10):
            chunk = ChunkSearchResult(
                chunk_id=uuid4(),
                chunk_text=f"VinTech and Samsung are building factories in Hà Nội chunk {i}",
                chunk_index=i,
                article_id=uuid4(),
                article_title="Tech News",
                source_name="VnExpress",
                score=0.5 + (i * 0.01),
            )
            chunks_with_entities.append(chunk)

        chunks_without_entities = []
        for i in range(10):
            chunk = ChunkSearchResult(
                chunk_id=uuid4(),
                chunk_text=f"Random content about different topics chunk {i}",
                chunk_index=i + 10,
                article_id=uuid4(),
                article_title="Other News",
                source_name="VnExpress",
                score=0.6 + (i * 0.01),
            )
            chunks_without_entities.append(chunk)

        # Mix chunks
        all_chunks = chunks_with_entities + chunks_without_entities

        # Define entities from query
        entities = {
            "organizations": ["VinTech", "Samsung"],
            "locations": ["Hà Nội"],
        }

        def mock_generate(messages, **kwargs):
            response = MagicMock()
            response.content = json.dumps(
                {"id0": 8, "id1": 7, "id2": 9, "id3": 6, "id4": 8}
            )
            return response

        mock_llm_provider.generate_completion = AsyncMock(side_effect=mock_generate)

        # Enable entity filtering
        reranker_service.entity_filter_enabled = True
        reranker_service.min_entity_match_ratio = 0.3  # Require 30% entity match

        result = await reranker_service.rerank(
            query="VinTech Samsung factories Hà Nội",
            chunks=all_chunks,
            top_n=10,
            entities=entities,
        )

        # Should only include chunks with entities
        assert len(result) > 0
        # All results should contain at least one entity
        for chunk in result:
            text_lower = chunk.chunk_text.lower()
            has_entity = any(
                entity.lower() in text_lower
                for entity_list in entities.values()
                for entity in entity_list
            )
            assert has_entity, f"Chunk should contain entity: {chunk.chunk_text}"

    @pytest.mark.asyncio
    async def test_rerank_entity_filtering_disabled(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test that entity filtering can be disabled."""

        def mock_generate(messages, **kwargs):
            response = MagicMock()
            response.content = json.dumps(
                {"id0": 8, "id1": 7, "id2": 9, "id3": 6, "id4": 8}
            )
            return response

        mock_llm_provider.generate_completion = AsyncMock(side_effect=mock_generate)

        # Disable entity filtering
        reranker_service.entity_filter_enabled = False

        entities = {"organizations": ["VinTech"]}

        result = await reranker_service.rerank(
            query="test", chunks=sample_chunks, top_n=10, entities=entities
        )

        # Should return results even though chunks don't contain entities
        assert len(result) == 10

    @pytest.mark.asyncio
    async def test_rerank_entity_filtering_no_entities(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test reranking when no entities are provided."""

        def mock_generate(messages, **kwargs):
            response = MagicMock()
            response.content = json.dumps(
                {"id0": 8, "id1": 7, "id2": 9, "id3": 6, "id4": 8}
            )
            return response

        mock_llm_provider.generate_completion = AsyncMock(side_effect=mock_generate)

        # Enable filtering but provide no entities
        reranker_service.entity_filter_enabled = True

        result = await reranker_service.rerank(
            query="test", chunks=sample_chunks, top_n=10, entities=None
        )

        # Should return results normally (no filtering applied)
        assert len(result) == 10

    @pytest.mark.asyncio
    async def test_calculate_entity_match_ratio(self, reranker_service):
        """Test entity match ratio calculation."""
        text = "VinTech and Samsung are building factories in Hà Nội"
        entities = ["VinTech", "Samsung", "Hà Nội", "Microsoft"]

        ratio = reranker_service._calculate_entity_match_ratio(text, entities)

        # 3 out of 4 entities match = 0.75
        assert ratio == 0.75

    @pytest.mark.asyncio
    async def test_calculate_entity_match_ratio_case_insensitive(
        self, reranker_service
    ):
        """Test entity matching is case-insensitive."""
        text = "vintech and SAMSUNG are building factories"
        entities = ["VinTech", "Samsung"]

        ratio = reranker_service._calculate_entity_match_ratio(text, entities)

        # Both should match despite different cases
        assert ratio == 1.0

    @pytest.mark.asyncio
    async def test_entity_filtering_empty_result(
        self, reranker_service, mock_llm_provider, sample_chunks
    ):
        """Test when entity filtering removes all chunks."""
        # Enable strict filtering
        reranker_service.entity_filter_enabled = True
        reranker_service.min_entity_match_ratio = 1.0  # Require 100% match

        # Entities that don't appear in sample chunks
        entities = {"organizations": ["NonExistentCompany", "FakeOrg"]}

        result = await reranker_service.rerank(
            query="test", chunks=sample_chunks, top_n=10, entities=entities
        )

        # Should return empty list when all chunks filtered out
        assert len(result) == 0
        # LLM should not be called
        assert not mock_llm_provider.generate_completion.called
