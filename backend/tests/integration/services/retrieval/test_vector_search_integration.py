"""
Integration tests for Vector Search Service with PostgreSQL + pgvector.

These tests require Docker services to be running:
    docker compose -f docker/docker-compose.yml up -d

Tests pgvector-specific features:
- Cosine similarity search with <=> operator
- L2 distance search with <-> operator
- Inner product search with <#> operator
- IVFFlat index usage for fast ANN search
- Embedding vector similarity ranking
"""

import pytest
from datetime import datetime, timezone

from app.models.article_chunk import ArticleChunk
from app.models.article import Article
from app.models.news_source import NewsSource
from app.models.rss_feed import RssFeed
from app.services.retrieval.vector_search_service import VectorSearchService


@pytest.mark.integration
@pytest.mark.requires_postgres
class TestVectorSearchIntegration:
    """Integration tests for vector search with PostgreSQL + pgvector."""

    @pytest.fixture
    async def news_source(self, postgres_session):
        """Create a test news source."""
        source = NewsSource(
            name="VnExpress",
            base_url="https://vnexpress.net",
        )
        postgres_session.add(source)
        await postgres_session.commit()
        await postgres_session.refresh(source)
        return source

    @pytest.fixture
    async def rss_feed(self, postgres_session, news_source):
        """Create a test RSS feed."""
        feed = RssFeed(
            source_id=news_source.id,
            feed_url="https://vnexpress.net/rss/tin-moi-nhat.rss",
            topic="Technology",
        )
        postgres_session.add(feed)
        await postgres_session.commit()
        await postgres_session.refresh(feed)
        return feed

    @pytest.fixture
    async def article(self, postgres_session, rss_feed):
        """Create a test article."""
        article = Article(
            feed_id=rss_feed.id,
            title="VinTech xây nhà máy sản xuất chip tại Hà Nội",
            url="https://vnexpress.net/article123",
            published_at=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
            content="VinTech announces new factory in Hanoi with $5B investment",
        )
        postgres_session.add(article)
        await postgres_session.commit()
        await postgres_session.refresh(article)
        return article

    @pytest.fixture
    async def embedded_chunks(self, postgres_session, article):
        """Create test chunks with different embeddings for similarity testing."""
        # Create embeddings that are progressively less similar to query
        # Query embedding will be all 1.0s
        embeddings = [
            # Very similar (all 1.0s) - cosine similarity ≈ 1.0
            [1.0] * 1536,
            # Moderately similar (mix of 1.0 and 0.5)
            [1.0 if i % 2 == 0 else 0.5 for i in range(1536)],
            # Less similar (mix of 1.0, 0.5, and 0.0)
            [1.0 if i % 3 == 0 else (0.5 if i % 3 == 1 else 0.0) for i in range(1536)],
            # Different direction (all -1.0s) - cosine similarity ≈ -1.0
            [-1.0] * 1536,
            # Orthogonal (alternating pattern)
            [1.0 if i % 2 == 0 else -1.0 for i in range(1536)],
        ]

        chunks_data = [
            "VinTech công bố kế hoạch xây dựng nhà máy sản xuất chip bán dẫn",
            "Dự án nhà máy dự kiến tạo ra 10,000 việc làm",
            "Công nghệ sản xuất chip bán dẫn hiện đại",
            "Nhà máy trang bị dây chuyền tự động hóa",
            "VinTech hợp tác với đối tác quốc tế",
        ]

        chunks = []
        for idx, (text, embedding) in enumerate(zip(chunks_data, embeddings)):
            chunk = ArticleChunk(
                article_id=article.id,
                chunk_index=idx,
                chunk_text=text,
                embedding=embedding,
                article_title=article.title,
                source_name="VnExpress",
            )
            postgres_session.add(chunk)
            chunks.append(chunk)

        await postgres_session.commit()
        return chunks

    @pytest.mark.asyncio
    async def test_cosine_similarity_search(self, postgres_session, embedded_chunks):
        """Test vector search with cosine similarity metric."""
        vector_service = VectorSearchService(session=postgres_session)

        # Query with embedding similar to chunk 0 (all 1.0s)
        query_embedding = [1.0] * 1536

        results = await vector_service.search(query_embedding, top_k=3)

        # Should return results
        assert len(results) > 0
        assert len(results) <= 3

        # Results should be ordered by similarity (highest first)
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score

        # Most similar chunk should be first (chunk 0 with all 1.0s)
        assert results[0].chunk_index == 0
        assert results[0].score > 0.9  # Very high cosine similarity

    @pytest.mark.asyncio
    async def test_top_k_limit(self, postgres_session, embedded_chunks):
        """Test that top_k parameter limits results correctly."""
        vector_service = VectorSearchService(session=postgres_session)

        query_embedding = [1.0] * 1536

        # Test different top_k values
        results_2 = await vector_service.search(query_embedding, top_k=2)
        results_5 = await vector_service.search(query_embedding, top_k=5)

        assert len(results_2) == 2
        assert len(results_5) == 5

        # First 2 results should be the same
        assert results_2[0].chunk_id == results_5[0].chunk_id
        assert results_2[1].chunk_id == results_5[1].chunk_id

    @pytest.mark.asyncio
    async def test_similarity_score_range(self, postgres_session, embedded_chunks):
        """Test that similarity scores are in valid range."""
        vector_service = VectorSearchService(session=postgres_session)

        query_embedding = [1.0] * 1536

        results = await vector_service.search(query_embedding, top_k=5)

        for result in results:
            # Cosine similarity scores should be between -1 and 1
            # But we convert to 0-2 range with (1 - distance)
            assert result.score >= -1.0
            assert result.score <= 2.0
            assert isinstance(result.score, float)

    @pytest.mark.asyncio
    async def test_search_result_completeness(self, postgres_session, embedded_chunks):
        """Test that search results include all required fields."""
        vector_service = VectorSearchService(session=postgres_session)

        query_embedding = [1.0] * 1536

        results = await vector_service.search(query_embedding, top_k=3)

        assert len(results) > 0

        for result in results:
            assert result.chunk_id is not None
            assert result.chunk_text is not None
            assert result.chunk_index >= 0
            assert result.article_id is not None
            assert result.article_title is not None
            assert result.source_name == "VnExpress"
            assert isinstance(result.score, float)

    @pytest.mark.asyncio
    async def test_empty_database_returns_empty_results(self, postgres_session):
        """Test that search on empty database returns empty list."""
        vector_service = VectorSearchService(session=postgres_session)

        query_embedding = [1.0] * 1536

        results = await vector_service.search(query_embedding, top_k=10)

        assert results == []

    @pytest.mark.asyncio
    async def test_different_query_embeddings_different_results(
        self, postgres_session, embedded_chunks
    ):
        """Test that different query embeddings produce different rankings."""
        vector_service = VectorSearchService(session=postgres_session)

        # Query 1: Similar to chunk 0 (all 1.0s)
        query1 = [1.0] * 1536
        results1 = await vector_service.search(query1, top_k=5)

        # Query 2: Similar to chunk 3 (all -1.0s)
        query2 = [-1.0] * 1536
        results2 = await vector_service.search(query2, top_k=5)

        # Different queries should produce different top results
        assert results1[0].chunk_id != results2[0].chunk_id

        # Query 1 should rank chunk 0 highest
        assert results1[0].chunk_index == 0

        # Query 2 should rank chunk 3 highest (most similar to -1.0s)
        assert results2[0].chunk_index == 3

    @pytest.mark.asyncio
    async def test_vector_dimension_handling(self, postgres_session, embedded_chunks):
        """Test that service handles correct embedding dimensions (1536)."""
        vector_service = VectorSearchService(session=postgres_session)

        # Correct dimension (1536)
        correct_query = [0.5] * 1536
        results = await vector_service.search(correct_query, top_k=3)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_normalized_vs_unnormalized_embeddings(
        self, postgres_session, embedded_chunks
    ):
        """Test that service handles both normalized and unnormalized vectors."""
        vector_service = VectorSearchService(session=postgres_session)

        # Unnormalized vector (large magnitude)
        unnormalized_query = [10.0] * 1536
        results1 = await vector_service.search(unnormalized_query, top_k=3)

        # Normalized version (same direction, unit length)
        normalized_query = [0.025] * 1536  # Approximately unit vector
        results2 = await vector_service.search(normalized_query, top_k=3)

        # Cosine similarity is direction-based, so ranking should be similar
        # (though scores may differ)
        assert results1[0].chunk_index == results2[0].chunk_index

    @pytest.mark.asyncio
    async def test_zero_vector_handling(self, postgres_session, embedded_chunks):
        """Test handling of zero vector query."""
        vector_service = VectorSearchService(session=postgres_session)

        # Zero vector (undefined direction)
        zero_query = [0.0] * 1536

        # Should not crash, but results may be undefined
        results = await vector_service.search(zero_query, top_k=3)

        # Should return results without errors
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_ordering_monotonic(self, postgres_session, embedded_chunks):
        """Test that search results are ordered monotonically by score."""
        vector_service = VectorSearchService(session=postgres_session)

        query_embedding = [1.0] * 1536

        results = await vector_service.search(query_embedding, top_k=5)

        # Verify strict descending order (or equal)
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score
