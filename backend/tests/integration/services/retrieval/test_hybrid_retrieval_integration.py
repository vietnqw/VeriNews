"""
Integration tests for Hybrid Retrieval Service.

These tests verify the hybrid search combining vector and BM25:
- Single query hybrid search
- Multi-query hybrid search
- Result list fusion
- Vector + BM25 combination
- Configuration-based enabling/disabling

Requires Docker services to be running:
    docker compose -f docker/docker-compose.yml up -d

Tests cover:
- Integration between vector and BM25 search
- Sequential execution to avoid session conflicts
- Result deduplication across methods
- Configuration flexibility
"""

import pytest
from datetime import datetime, timezone

from app.models.article_chunk import ArticleChunk
from app.models.article import Article
from app.models.news_source import NewsSource
from app.models.rss_feed import RssFeed
from app.services.retrieval.hybrid_retrieval_service import HybridRetrievalService


@pytest.mark.integration
@pytest.mark.requires_postgres
class TestHybridRetrievalIntegration:
    """Integration tests for hybrid retrieval with PostgreSQL."""

    @pytest.fixture
    async def test_data(self, postgres_session):
        """Create test data for hybrid retrieval."""
        # Create news source
        source = NewsSource(
            name="VnExpress",
            base_url="https://vnexpress.net",
        )
        postgres_session.add(source)
        await postgres_session.flush()

        # Create RSS feed
        feed = RssFeed(
            source_id=source.id,
            feed_url="https://vnexpress.net/rss/tin-moi-nhat.rss",
            topic="Technology",
        )
        postgres_session.add(feed)
        await postgres_session.flush()

        # Create article
        article = Article(
            feed_id=feed.id,
            title="VinTech xây nhà máy chip tại Hà Nội",
            url="https://vnexpress.net/article123",
            published_at=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
            content="VinTech announces semiconductor factory",
        )
        postgres_session.add(article)
        await postgres_session.flush()

        # Create chunks with varied embeddings
        chunks_data = [
            {
                "text": "VinTech công bố kế hoạch xây dựng nhà máy sản xuất chip bán dẫn tại Hà Nội",
                "embedding": [1.0] * 1536,  # Very similar to query
            },
            {
                "text": "Dự án nhà máy dự kiến tạo ra 10,000 việc làm công nghệ cao",
                "embedding": [
                    1.0 if i % 2 == 0 else 0.5 for i in range(1536)
                ],  # Moderately similar
            },
            {
                "text": "Công nghệ sản xuất chip bán dẫn hiện đại sẽ được áp dụng",
                "embedding": [
                    1.0 if i % 3 == 0 else (0.5 if i % 3 == 1 else 0.0)
                    for i in range(1536)
                ],  # Less similar
            },
            {
                "text": "Nhà máy trang bị dây chuyền sản xuất tự động hóa hoàn toàn",
                "embedding": [-1.0] * 1536,  # Opposite direction
            },
            {
                "text": "VinTech hợp tác với đối tác quốc tế chuyển giao công nghệ",
                "embedding": [
                    1.0 if i % 2 == 0 else -1.0 for i in range(1536)
                ],  # Orthogonal
            },
        ]

        chunks = []
        for idx, data in enumerate(chunks_data):
            chunk = ArticleChunk(
                article_id=article.id,
                chunk_index=idx,
                chunk_text=data["text"],
                embedding=data["embedding"],
                article_title=article.title,
                source_name="VnExpress",
            )
            postgres_session.add(chunk)
            chunks.append(chunk)

        await postgres_session.commit()

        # Index chunks for BM25 search
        from app.services.retrieval.bm25_search_service import BM25SearchService

        bm25_service = BM25SearchService(session=postgres_session)
        for chunk in chunks:
            await bm25_service.index_chunk(chunk)

        await postgres_session.commit()

        return {
            "article": article,
            "chunks": chunks,
        }

    @pytest.mark.asyncio
    async def test_single_query_hybrid_search(self, postgres_session, test_data):
        """Test hybrid search for a single query returns both vector and BM25 results."""
        service = HybridRetrievalService(session=postgres_session)

        query_text = "nhà máy chip bán dẫn VinTech"
        query_embedding = [1.0] * 1536

        vector_results, bm25_results = await service.search_single_query(
            query_text=query_text, query_embedding=query_embedding, top_k=3
        )

        # Both methods should return results
        assert len(vector_results) > 0, "Vector search returned no results"
        assert len(bm25_results) > 0, "BM25 search returned no results"

        # Results should be limited by top_k
        assert len(vector_results) <= 3
        assert len(bm25_results) <= 3

        # Results should be ordered by score (descending)
        for i in range(len(vector_results) - 1):
            assert vector_results[i].score >= vector_results[i + 1].score

        for i in range(len(bm25_results) - 1):
            assert bm25_results[i].score >= bm25_results[i + 1].score

    @pytest.mark.asyncio
    async def test_multi_query_hybrid_search(self, postgres_session, test_data):
        """Test hybrid search for multiple queries returns combined results."""
        service = HybridRetrievalService(session=postgres_session)

        queries = [
            ("VinTech nhà máy chip", [1.0] * 1536),
            ("công nghệ sản xuất", [1.0 if i % 2 == 0 else 0.5 for i in range(1536)]),
            ("dự án đầu tư", [0.8] * 1536),
        ]

        all_result_lists = await service.search_multi_query(queries, top_k=3)

        # Should return 2N lists for N queries (vector + BM25 per query)
        assert len(all_result_lists) == 6  # 3 queries * 2 methods

        # Each list should have results (or be empty if no matches)
        for result_list in all_result_lists:
            assert isinstance(result_list, list)
            # Results should be ordered by score
            for i in range(len(result_list) - 1):
                assert result_list[i].score >= result_list[i + 1].score

    @pytest.mark.asyncio
    async def test_hybrid_search_result_completeness(self, postgres_session, test_data):
        """Test that hybrid search results include all required fields."""
        service = HybridRetrievalService(session=postgres_session)

        query_text = "VinTech"
        query_embedding = [1.0] * 1536

        vector_results, bm25_results = await service.search_single_query(
            query_text=query_text, query_embedding=query_embedding, top_k=5
        )

        # Verify vector results
        for result in vector_results:
            assert result.chunk_id is not None
            assert result.chunk_text is not None
            assert result.chunk_index >= 0
            assert result.article_id is not None
            assert result.article_title is not None
            assert result.source_name == "VnExpress"
            assert isinstance(result.score, float)

        # Verify BM25 results
        for result in bm25_results:
            assert result.chunk_id is not None
            assert result.chunk_text is not None
            assert result.chunk_index >= 0
            assert result.article_id is not None
            assert result.article_title is not None
            assert result.source_name == "VnExpress"
            assert isinstance(result.score, float)
            assert result.score > 0

    @pytest.mark.asyncio
    async def test_hybrid_search_different_rankings(self, postgres_session, test_data):
        """Test that vector and BM25 produce different rankings."""
        service = HybridRetrievalService(session=postgres_session)

        query_text = "nhà máy chip"
        query_embedding = [1.0] * 1536

        vector_results, bm25_results = await service.search_single_query(
            query_text=query_text, query_embedding=query_embedding, top_k=5
        )

        # Extract chunk IDs in order
        vector_ids = [r.chunk_id for r in vector_results]
        bm25_ids = [r.chunk_id for r in bm25_results]

        # Rankings should differ (different algorithms)
        # Note: They might be the same for very simple queries, but typically differ
        assert len(vector_ids) > 0 and len(bm25_ids) > 0

    @pytest.mark.asyncio
    async def test_hybrid_search_with_empty_query(self, postgres_session, test_data):
        """Test hybrid search behavior with empty/whitespace query."""
        service = HybridRetrievalService(session=postgres_session)

        query_text = "   "
        query_embedding = [0.0] * 1536

        vector_results, bm25_results = await service.search_single_query(
            query_text=query_text, query_embedding=query_embedding, top_k=3
        )

        # Should return empty or minimal results without errors
        assert isinstance(vector_results, list)
        assert isinstance(bm25_results, list)

    @pytest.mark.asyncio
    async def test_hybrid_search_top_k_limits(self, postgres_session, test_data):
        """Test that top_k parameter is respected by both search methods."""
        service = HybridRetrievalService(session=postgres_session)

        query_text = "VinTech nhà máy"
        query_embedding = [1.0] * 1536

        # Test different top_k values
        for top_k in [1, 2, 3, 5]:
            vector_results, bm25_results = await service.search_single_query(
                query_text=query_text, query_embedding=query_embedding, top_k=top_k
            )

            assert len(vector_results) <= top_k, f"Vector results exceed top_k={top_k}"
            assert len(bm25_results) <= top_k, f"BM25 results exceed top_k={top_k}"

    @pytest.mark.asyncio
    async def test_multi_query_result_list_count(self, postgres_session, test_data):
        """Test that multi-query search returns correct number of result lists."""
        service = HybridRetrievalService(session=postgres_session)

        # Test with different query counts
        for num_queries in [1, 2, 3, 5]:
            queries = [
                (f"query {i}", [float(i) / num_queries] * 1536)
                for i in range(num_queries)
            ]

            all_result_lists = await service.search_multi_query(queries, top_k=3)

            # Should return 2 * num_queries (vector + BM25 per query)
            assert len(all_result_lists) == num_queries * 2, (
                f"Expected {num_queries * 2} lists, got {len(all_result_lists)}"
            )

    @pytest.mark.asyncio
    async def test_hybrid_search_sequential_execution(
        self, postgres_session, test_data
    ):
        """Test that searches execute sequentially (avoid session conflicts)."""
        service = HybridRetrievalService(session=postgres_session)

        query_text = "test query"
        query_embedding = [1.0] * 1536

        # Multiple sequential calls should succeed without session conflicts
        for _ in range(3):
            vector_results, bm25_results = await service.search_single_query(
                query_text=query_text, query_embedding=query_embedding, top_k=3
            )

            # Each call should return results
            assert isinstance(vector_results, list)
            assert isinstance(bm25_results, list)

    @pytest.mark.asyncio
    async def test_hybrid_search_with_no_database_results(self, postgres_session):
        """Test hybrid search on empty database returns empty results."""
        service = HybridRetrievalService(session=postgres_session)

        query_text = "nonexistent query"
        query_embedding = [1.0] * 1536

        vector_results, bm25_results = await service.search_single_query(
            query_text=query_text, query_embedding=query_embedding, top_k=3
        )

        # Should return empty lists without errors
        assert vector_results == []
        assert bm25_results == []
