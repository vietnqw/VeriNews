"""
Integration tests for BM25 Search Service with PostgreSQL.

These tests require Docker services to be running:
    docker compose -f docker/docker-compose.yml up -d

Tests PostgreSQL-specific features:
- tsvector full-text search
- ts_rank_cd BM25-like ranking
- to_tsquery query parsing
- Vietnamese tokenization with actual database
"""

import pytest
from datetime import datetime, timezone

from app.models.article_chunk import ArticleChunk
from app.models.article import Article
from app.models.news_source import NewsSource
from app.models.rss_feed import RssFeed
from app.services.retrieval.bm25_search_service import BM25SearchService


@pytest.mark.integration
@pytest.mark.requires_postgres
class TestBM25SearchIntegration:
    """Integration tests for BM25 search with PostgreSQL."""

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
    async def indexed_chunks(self, postgres_session, article):
        """Create and index test chunks."""
        bm25_service = BM25SearchService(session=postgres_session)

        # Create a dummy embedding (1536 dimensions filled with 0.1)
        dummy_embedding = [0.1] * 1536

        chunks_data = [
            "VinTech công bố kế hoạch xây dựng nhà máy sản xuất chip bán dẫn tại Hà Nội với vốn đầu tư 5 tỷ USD",
            "Dự án nhà máy dự kiến tạo ra 10,000 việc làm cho người lao động trong khu vực công nghệ cao",
            "Công nghệ sản xuất chip bán dẫn hiện đại sẽ được áp dụng tại nhà máy mới của VinTech",
            "Nhà máy sẽ được trang bị dây chuyền sản xuất tự động hóa hoàn toàn",
            "VinTech hợp tác với các đối tác quốc tế để chuyển giao công nghệ sản xuất chip",
        ]

        chunks = []
        for idx, text in enumerate(chunks_data):
            chunk = ArticleChunk(
                article_id=article.id,
                chunk_index=idx,
                chunk_text=text,
                embedding=dummy_embedding,  # Required field
                article_title=article.title,
                source_name="VnExpress",
            )
            postgres_session.add(chunk)
            await postgres_session.flush()

            # Index for BM25 search
            await bm25_service.index_chunk(chunk)
            chunks.append(chunk)

        await postgres_session.commit()
        return chunks

    @pytest.mark.asyncio
    async def test_search_vietnamese_compound_words(
        self, postgres_session, indexed_chunks
    ):
        """Test BM25 search with Vietnamese compound words."""
        bm25_service = BM25SearchService(session=postgres_session)

        results = await bm25_service.search("nhà máy công nghệ cao")

        # Should find relevant chunks
        assert len(results) > 0

        # Results should be ordered by relevance
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score

    @pytest.mark.asyncio
    async def test_search_relevance_ranking(self, postgres_session, indexed_chunks):
        """Test that BM25 ranks more relevant results higher."""
        bm25_service = BM25SearchService(session=postgres_session)

        # Search for "nhà máy chip bán dẫn" - should rank chunk 0 highest
        results = await bm25_service.search("nhà máy chip bán dẫn")

        assert len(results) > 0

        # First chunk mentions all these terms
        top_result = results[0]
        assert "nhà máy" in top_result.chunk_text.lower()
        assert "chip" in top_result.chunk_text.lower()
        assert "bán dẫn" in top_result.chunk_text.lower()

    @pytest.mark.asyncio
    async def test_search_top_k_limit(self, postgres_session, indexed_chunks):
        """Test that top_k parameter limits results."""
        bm25_service = BM25SearchService(session=postgres_session)

        results = await bm25_service.search("nhà máy", top_k=2)

        assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_search_no_results(self, postgres_session, indexed_chunks):
        """Test search with query that has no matches."""
        bm25_service = BM25SearchService(session=postgres_session)

        results = await bm25_service.search("absolutely irrelevant xyz123")

        assert results == []

    @pytest.mark.asyncio
    async def test_batch_indexing(self, postgres_session, article):
        """Test batch indexing of multiple chunks."""
        bm25_service = BM25SearchService(session=postgres_session)

        # Create dummy embedding
        dummy_embedding = [0.1] * 1536

        # Create unindexed chunks
        chunks = []
        for i in range(10):
            chunk = ArticleChunk(
                article_id=article.id,
                chunk_index=i,
                chunk_text=f"Batch test chunk {i} về công nghệ",
                embedding=dummy_embedding,
                article_title=article.title,
                source_name="VnExpress",
            )
            postgres_session.add(chunk)
            chunks.append(chunk)

        await postgres_session.commit()

        chunk_ids = [chunk.id for chunk in chunks]

        # Batch index
        indexed_count = await bm25_service.batch_index_chunks(chunk_ids, batch_size=3)

        assert indexed_count == 10

        # All chunks should be searchable
        results = await bm25_service.search("công nghệ")
        assert len(results) == 10

    @pytest.mark.asyncio
    async def test_reindexing_updates_search_vector(
        self, postgres_session, article, indexed_chunks
    ):
        """Test that re-indexing updates the search_vector."""
        bm25_service = BM25SearchService(session=postgres_session)

        # Get first chunk
        chunk = indexed_chunks[0]

        # Update chunk text
        chunk.chunk_text = "Completely new content about software development"
        postgres_session.add(chunk)
        await postgres_session.commit()

        # Re-index
        await bm25_service.index_chunk(chunk)

        # Old query should not find it
        old_results = await bm25_service.search("VinTech nhà máy")
        assert not any(r.chunk_id == chunk.id for r in old_results)

        # New query should find it
        new_results = await bm25_service.search("software development")
        assert any(r.chunk_id == chunk.id for r in new_results)

    @pytest.mark.asyncio
    async def test_search_result_completeness(self, postgres_session, indexed_chunks):
        """Test that search results include all required fields."""
        bm25_service = BM25SearchService(session=postgres_session)

        results = await bm25_service.search("VinTech")

        assert len(results) > 0

        for result in results:
            assert result.chunk_id is not None
            assert result.chunk_text is not None
            assert result.chunk_index >= 0
            assert result.article_id is not None
            assert result.article_title is not None
            assert result.source_name == "VnExpress"
            assert isinstance(result.score, float)
            assert result.score > 0

    @pytest.mark.asyncio
    async def test_vietnamese_tokenization_in_search(
        self, postgres_session, indexed_chunks
    ):
        """Test that Vietnamese tokenization works correctly in search."""
        bm25_service = BM25SearchService(session=postgres_session)

        # Search with compound word
        results = await bm25_service.search("công ty VinTech")

        # Should find results even though "công ty" is a compound word
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_concurrent_searches(self, postgres_session, indexed_chunks):
        """Test multiple concurrent searches."""
        import asyncio

        bm25_service = BM25SearchService(session=postgres_session)

        # Run multiple searches concurrently
        tasks = [
            bm25_service.search("nhà máy"),
            bm25_service.search("công nghệ"),
            bm25_service.search("VinTech"),
        ]

        results_list = await asyncio.gather(*tasks)

        # All searches should succeed
        assert all(isinstance(r, list) for r in results_list)
        assert all(len(r) > 0 for r in results_list)
