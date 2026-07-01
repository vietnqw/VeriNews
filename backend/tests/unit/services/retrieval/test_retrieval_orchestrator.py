"""
Unit tests for Retrieval Orchestrator.

Tests the full 6-stage retrieval pipeline coordination.
Uses mocked services to test orchestration logic.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.retrieval.retrieval_orchestrator import RetrievalOrchestrator
from app.services.retrieval.bm25_search_service import ChunkSearchResult
from app.services.retrieval.article_aggregation_service import ArticleResult


@pytest.mark.unit
class TestRetrievalOrchestrator:
    """Unit tests for retrieval orchestrator."""

    @pytest.fixture
    def mock_session(self):
        """Mock database session."""
        return MagicMock()

    @pytest.fixture
    def sample_chunks(self):
        """Create sample chunk results."""
        chunks = []
        for i in range(10):
            chunk = ChunkSearchResult(
                chunk_id=uuid4(),
                chunk_text=f"Sample chunk {i} about VinTech factory",
                chunk_index=i,
                article_id=uuid4(),
                article_title="VinTech Article",
                source_name="VnExpress",
                score=0.9 - (i * 0.05),
            )
            chunks.append(chunk)
        return chunks

    @pytest.fixture
    def sample_articles(self):
        """Create sample article results."""
        article = ArticleResult(
            article_id=uuid4(),
            title="VinTech announces factory",
            source_name="VnExpress",
            published_at="2024-01-15T10:00:00",
            relevance_score=0.85,
            url="https://vnexpress.net/vintech-factory",
            chunk_count=3,
            relevant_chunks=[],
        )
        return [article]

    @pytest.fixture
    def orchestrator(self, mock_session):
        """Create orchestrator with mocked services."""
        with (
            patch(
                "app.services.retrieval.retrieval_orchestrator.QueryExtractionService"
            ) as mock_query,
            patch(
                "app.services.retrieval.retrieval_orchestrator.HybridRetrievalService"
            ) as mock_hybrid,
            patch(
                "app.services.retrieval.retrieval_orchestrator.FusionService"
            ) as mock_fusion,
            patch(
                "app.services.retrieval.retrieval_orchestrator.RerankerService"
            ) as mock_reranker,
            patch(
                "app.services.retrieval.retrieval_orchestrator.ArticleAggregationService"
            ) as mock_aggregation,
            patch(
                "app.services.retrieval.retrieval_orchestrator.generate_embeddings_batch"
            ) as mock_embeddings,
        ):
            orch = RetrievalOrchestrator(session=mock_session)
            orch.query_service = mock_query.return_value
            orch.hybrid_service = mock_hybrid.return_value
            orch.fusion_service = mock_fusion.return_value
            orch.reranker_service = mock_reranker.return_value
            orch.aggregation_service = mock_aggregation.return_value
            orch._generate_embeddings_batch = mock_embeddings
            return orch

    @pytest.mark.asyncio
    async def test_retrieve_full_pipeline(
        self, orchestrator, sample_chunks, sample_articles
    ):
        """Test full retrieval pipeline execution."""
        # Mock all services
        orchestrator.query_service.extract_queries = AsyncMock(
            return_value={
                "clean_query": "VinTech factory investment",
                "claims": ["VinTech builds factory", "Investment is 5B USD"],
                "query_count": 3,
            }
        )

        # Mock embeddings
        with patch(
            "app.services.retrieval.retrieval_orchestrator.generate_embeddings_batch",
            new_callable=AsyncMock,
        ) as mock_embed:
            mock_embed.return_value = [[0.5] * 1536, [0.6] * 1536, [0.7] * 1536]

            # Mock hybrid search
            orchestrator.hybrid_service.search_multi_query = AsyncMock(
                return_value=[sample_chunks[:5], sample_chunks[3:8]]
            )

            # Mock fusion
            orchestrator.fusion_service.reciprocal_rank_fusion = MagicMock(
                return_value=sample_chunks[:10]
            )

            # Mock reranking
            orchestrator.reranker_service.rerank = AsyncMock(
                return_value=sample_chunks[:5]
            )

            # Mock aggregation
            orchestrator.aggregation_service.aggregate_to_articles = MagicMock(
                return_value=sample_articles
            )

            # Execute pipeline
            result = await orchestrator.retrieve("VinTech xây nhà máy 5 tỷ USD")

            # Verify result structure
            assert "articles" in result
            assert "total_time_ms" in result
            assert "stage_timings" in result
            assert "query_count" in result

            # Verify content
            assert len(result["articles"]) == 1
            assert result["query_count"] == 3

            # Verify stage timings exist
            assert "query_extraction" in result["stage_timings"]
            assert "embedding" in result["stage_timings"]
            assert "hybrid_search" in result["stage_timings"]
            assert "fusion" in result["stage_timings"]
            assert "reranking" in result["stage_timings"]
            assert "aggregation" in result["stage_timings"]

    @pytest.mark.asyncio
    async def test_retrieve_with_query_extraction_disabled(
        self, orchestrator, sample_chunks, sample_articles
    ):
        """Test pipeline when query extraction is disabled."""
        with (
            patch(
                "app.services.retrieval.retrieval_orchestrator.settings"
            ) as mock_settings,
            patch(
                "app.services.retrieval.retrieval_orchestrator.generate_embeddings_batch",
                new_callable=AsyncMock,
            ) as mock_embed,
        ):
            # Configure settings mock
            mock_settings.retrieval.query_extraction.enabled = False
            mock_settings.retrieval.reranking.enabled = True

            mock_embed.return_value = [[0.5] * 1536]

            orchestrator.hybrid_service.search_multi_query = AsyncMock(
                return_value=[sample_chunks[:5]]
            )
            orchestrator.fusion_service.reciprocal_rank_fusion = MagicMock(
                return_value=sample_chunks[:10]
            )
            orchestrator.reranker_service.rerank = AsyncMock(
                return_value=sample_chunks[:5]
            )
            orchestrator.aggregation_service.aggregate_to_articles = MagicMock(
                return_value=sample_articles
            )

            post_text = "VinTech factory"
            result = await orchestrator.retrieve(post_text)

            # Should use original post as single query
            assert result["query_count"] == 1

            # Query extraction service should not be called
            orchestrator.query_service.extract_queries.assert_not_called()

    @pytest.mark.asyncio
    async def test_retrieve_with_reranking_disabled(
        self, orchestrator, sample_chunks, sample_articles
    ):
        """Test pipeline when reranking is disabled."""
        with (
            patch(
                "app.services.retrieval.retrieval_orchestrator.settings"
            ) as mock_settings,
            patch(
                "app.services.retrieval.retrieval_orchestrator.generate_embeddings_batch",
                new_callable=AsyncMock,
            ) as mock_embed,
        ):
            # Configure settings mock
            mock_settings.retrieval.query_extraction.enabled = True
            mock_settings.retrieval.reranking.enabled = False

            mock_embed.return_value = [[0.5] * 1536]

            orchestrator.query_service.extract_queries = AsyncMock(
                return_value={
                    "clean_query": "Test",
                    "claims": [],
                    "query_count": 1,
                }
            )
            orchestrator.hybrid_service.search_multi_query = AsyncMock(
                return_value=[sample_chunks[:5]]
            )
            orchestrator.fusion_service.reciprocal_rank_fusion = MagicMock(
                return_value=sample_chunks[:10]
            )
            orchestrator.aggregation_service.aggregate_to_articles = MagicMock(
                return_value=sample_articles
            )

            result = await orchestrator.retrieve("Test post")

            # Reranker should not be called
            orchestrator.reranker_service.rerank.assert_not_called()

            # Should use top 10 from fusion directly
            assert result["stage_timings"]["reranking"] >= 0

    @pytest.mark.asyncio
    async def test_retrieve_stage_timing_accuracy(
        self, orchestrator, sample_chunks, sample_articles
    ):
        """Test that stage timings are measured correctly."""
        with patch(
            "app.services.retrieval.retrieval_orchestrator.generate_embeddings_batch",
            new_callable=AsyncMock,
        ) as mock_embed:
            mock_embed.return_value = [[0.5] * 1536]

            orchestrator.query_service.extract_queries = AsyncMock(
                return_value={"clean_query": "Test", "claims": [], "query_count": 1}
            )
            orchestrator.hybrid_service.search_multi_query = AsyncMock(
                return_value=[sample_chunks[:5]]
            )
            orchestrator.fusion_service.reciprocal_rank_fusion = MagicMock(
                return_value=sample_chunks[:10]
            )
            orchestrator.reranker_service.rerank = AsyncMock(
                return_value=sample_chunks[:5]
            )
            orchestrator.aggregation_service.aggregate_to_articles = MagicMock(
                return_value=sample_articles
            )

            result = await orchestrator.retrieve("Test")

            # All timings should be non-negative
            for stage, timing in result["stage_timings"].items():
                assert timing >= 0, f"Stage {stage} has negative timing"

            # Total time should be reasonable (within an order of magnitude of stage sum)
            # Note: total includes overhead from orchestration, logging, etc.
            total_stage_time = sum(result["stage_timings"].values())
            assert result["total_time_ms"] >= 0
            assert result["total_time_ms"] < total_stage_time * 100  # Sanity check

    @pytest.mark.asyncio
    async def test_retrieve_empty_fusion_results(self, orchestrator, sample_articles):
        """Test pipeline when fusion returns empty results."""
        with patch(
            "app.services.retrieval.retrieval_orchestrator.generate_embeddings_batch",
            new_callable=AsyncMock,
        ) as mock_embed:
            mock_embed.return_value = [[0.5] * 1536]

            orchestrator.query_service.extract_queries = AsyncMock(
                return_value={"clean_query": "Test", "claims": [], "query_count": 1}
            )
            orchestrator.hybrid_service.search_multi_query = AsyncMock(
                return_value=[[]]  # Empty results
            )
            orchestrator.fusion_service.reciprocal_rank_fusion = MagicMock(
                return_value=[]
            )
            orchestrator.aggregation_service.aggregate_to_articles = MagicMock(
                return_value=[]
            )

            result = await orchestrator.retrieve("Nonexistent query")

            # Should handle empty results gracefully
            assert result["articles"] == []
            assert result["query_count"] == 1

    @pytest.mark.asyncio
    async def test_retrieve_batch_embedding_generation(
        self, orchestrator, sample_chunks, sample_articles
    ):
        """Test that batch embedding is called with correct queries."""
        with patch(
            "app.services.retrieval.retrieval_orchestrator.generate_embeddings_batch",
            new_callable=AsyncMock,
        ) as mock_embed:
            mock_embed.return_value = [[0.5] * 1536, [0.6] * 1536, [0.7] * 1536]

            orchestrator.query_service.extract_queries = AsyncMock(
                return_value={
                    "clean_query": "Clean query",
                    "claims": ["Claim 1", "Claim 2"],
                    "query_count": 3,
                }
            )
            orchestrator.hybrid_service.search_multi_query = AsyncMock(
                return_value=[sample_chunks[:5]]
            )
            orchestrator.fusion_service.reciprocal_rank_fusion = MagicMock(
                return_value=sample_chunks[:10]
            )
            orchestrator.reranker_service.rerank = AsyncMock(
                return_value=sample_chunks[:5]
            )
            orchestrator.aggregation_service.aggregate_to_articles = MagicMock(
                return_value=sample_articles
            )

            await orchestrator.retrieve("Test post")

            # Verify batch embedding was called with [clean_query] + claims
            mock_embed.assert_called_once()
            call_args = mock_embed.call_args[0][0]
            assert len(call_args) == 3
            assert call_args[0] == "Clean query"
            assert call_args[1] == "Claim 1"
            assert call_args[2] == "Claim 2"

    @pytest.mark.asyncio
    async def test_retrieve_multi_query_hybrid_search(
        self, orchestrator, sample_chunks, sample_articles
    ):
        """Test that hybrid search receives correct query format."""
        with patch(
            "app.services.retrieval.retrieval_orchestrator.generate_embeddings_batch",
            new_callable=AsyncMock,
        ) as mock_embed:
            mock_embed.return_value = [[0.5] * 1536, [0.6] * 1536]

            orchestrator.query_service.extract_queries = AsyncMock(
                return_value={
                    "clean_query": "Query 1",
                    "claims": ["Query 2"],
                    "query_count": 2,
                }
            )
            orchestrator.hybrid_service.search_multi_query = AsyncMock(
                return_value=[sample_chunks[:5]]
            )
            orchestrator.fusion_service.reciprocal_rank_fusion = MagicMock(
                return_value=sample_chunks[:10]
            )
            orchestrator.reranker_service.rerank = AsyncMock(
                return_value=sample_chunks[:5]
            )
            orchestrator.aggregation_service.aggregate_to_articles = MagicMock(
                return_value=sample_articles
            )

            await orchestrator.retrieve("Test")

            # Verify hybrid search was called with (text, embedding) tuples
            orchestrator.hybrid_service.search_multi_query.assert_called_once()
            call_args = orchestrator.hybrid_service.search_multi_query.call_args[0][0]

            # Should be list of (text, embedding) tuples
            assert len(call_args) == 2
            assert call_args[0][0] == "Query 1"
            assert len(call_args[0][1]) == 1536
            assert call_args[1][0] == "Query 2"

    @pytest.mark.asyncio
    async def test_retrieve_reranking_top_100_chunks(
        self, orchestrator, sample_chunks, sample_articles
    ):
        """Test that reranking receives top 100 chunks from fusion."""
        with patch(
            "app.services.retrieval.retrieval_orchestrator.generate_embeddings_batch",
            new_callable=AsyncMock,
        ) as mock_embed:
            mock_embed.return_value = [[0.5] * 1536]

            # Create 150 chunks
            many_chunks = [
                ChunkSearchResult(
                    chunk_id=uuid4(),
                    chunk_text=f"Chunk {i}",
                    chunk_index=i,
                    article_id=uuid4(),
                    article_title="Article",
                    source_name="Source",
                    score=0.9 - (i * 0.001),
                )
                for i in range(150)
            ]

            orchestrator.query_service.extract_queries = AsyncMock(
                return_value={"clean_query": "Test", "claims": [], "query_count": 1}
            )
            orchestrator.hybrid_service.search_multi_query = AsyncMock(
                return_value=[many_chunks]
            )
            orchestrator.fusion_service.reciprocal_rank_fusion = MagicMock(
                return_value=many_chunks  # Return all 150
            )
            orchestrator.reranker_service.rerank = AsyncMock(
                return_value=sample_chunks[:10]
            )
            orchestrator.aggregation_service.aggregate_to_articles = MagicMock(
                return_value=sample_articles
            )

            await orchestrator.retrieve("Test")

            # Reranker should receive only top 100
            orchestrator.reranker_service.rerank.assert_called_once()
            call_args = orchestrator.reranker_service.rerank.call_args[0]
            chunks_for_reranking = call_args[1]
            assert len(chunks_for_reranking) == 100

    @pytest.mark.asyncio
    async def test_retrieve_with_vietnamese_text(
        self, orchestrator, sample_chunks, sample_articles
    ):
        """Test pipeline with Vietnamese Facebook post."""
        with patch(
            "app.services.retrieval.retrieval_orchestrator.generate_embeddings_batch",
            new_callable=AsyncMock,
        ) as mock_embed:
            mock_embed.return_value = [[0.5] * 1536]

            orchestrator.query_service.extract_queries = AsyncMock(
                return_value={
                    "clean_query": "VinTech xây dựng nhà máy chip",
                    "claims": ["Nhà máy có giá trị 5 tỷ USD"],
                    "query_count": 2,
                }
            )
            orchestrator.hybrid_service.search_multi_query = AsyncMock(
                return_value=[sample_chunks[:5]]
            )
            orchestrator.fusion_service.reciprocal_rank_fusion = MagicMock(
                return_value=sample_chunks[:10]
            )
            orchestrator.reranker_service.rerank = AsyncMock(
                return_value=sample_chunks[:5]
            )
            orchestrator.aggregation_service.aggregate_to_articles = MagicMock(
                return_value=sample_articles
            )

            vietnamese_post = "VinTech xây nhà máy 5 tỷ USD!!! Tuyệt vời 🎉"
            result = await orchestrator.retrieve(vietnamese_post)

            # Should handle Vietnamese text without errors
            assert result["query_count"] == 2
            assert len(result["articles"]) > 0

    @pytest.mark.asyncio
    async def test_retrieve_service_orchestration_order(
        self, orchestrator, sample_chunks, sample_articles
    ):
        """Test that services are called in correct order."""
        call_order = []

        async def track_query_extraction(*args, **kwargs):
            call_order.append("query_extraction")
            return {"clean_query": "Test", "claims": [], "query_count": 1}

        async def track_embeddings(*args, **kwargs):
            call_order.append("embeddings")
            return [[0.5] * 1536]

        async def track_hybrid(*args, **kwargs):
            call_order.append("hybrid_search")
            return [sample_chunks[:5]]

        def track_fusion(*args, **kwargs):
            call_order.append("fusion")
            return sample_chunks[:10]

        async def track_reranking(*args, **kwargs):
            call_order.append("reranking")
            return sample_chunks[:5]

        def track_aggregation(*args, **kwargs):
            call_order.append("aggregation")
            return sample_articles

        with patch(
            "app.services.retrieval.retrieval_orchestrator.generate_embeddings_batch",
            new_callable=AsyncMock,
        ) as mock_embed:
            mock_embed.side_effect = track_embeddings

            orchestrator.query_service.extract_queries = AsyncMock(
                side_effect=track_query_extraction
            )
            orchestrator.hybrid_service.search_multi_query = AsyncMock(
                side_effect=track_hybrid
            )
            orchestrator.fusion_service.reciprocal_rank_fusion = MagicMock(
                side_effect=track_fusion
            )
            orchestrator.reranker_service.rerank = AsyncMock(
                side_effect=track_reranking
            )
            orchestrator.aggregation_service.aggregate_to_articles = MagicMock(
                side_effect=track_aggregation
            )

            await orchestrator.retrieve("Test")

            # Verify correct order
            expected_order = [
                "query_extraction",
                "embeddings",
                "hybrid_search",
                "fusion",
                "reranking",
                "aggregation",
            ]
            assert call_order == expected_order
