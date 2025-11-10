"""
Unit tests for Retrieval Cache Service.

Tests Redis-based caching for retrieval results, including:
- Cache key generation (SHA256 hashing)
- Cache get/set operations
- TTL handling
- Error handling
- Cache clearing
"""

import hashlib
from uuid import uuid4

import pytest

from app.services.cache.retrieval_cache import RetrievalCache
from app.services.retrieval.article_aggregation_service import (
    ArticleResult,
    ChunkDetail,
)


class TestRetrievalCache:
    """Test suite for RetrievalCache."""

    @pytest.fixture
    async def cache_service(self, mock_redis):
        """Create a RetrievalCache instance with mocked Redis."""
        cache = RetrievalCache()
        # Override enabled to True for tests
        cache.enabled = True
        cache.redis_client = mock_redis
        return cache

    @pytest.fixture
    def sample_post_text(self):
        """Sample Facebook post text."""
        return "VinTech xây nhà máy 5 tỷ USD tại Hà Nội"

    @pytest.fixture
    def sample_article_results(self):
        """Sample article results for caching."""
        article_id = uuid4()
        return [
            ArticleResult(
                article_id=article_id,
                title="VinTech công bố dự án nhà máy mới",
                source_name="VnExpress",
                published_at=None,
                relevance_score=2.45,
                chunk_count=3,
                relevant_chunks=[
                    ChunkDetail(
                        chunk_id=uuid4(),
                        chunk_index=0,
                        chunk_text="Chunk 1 text",
                        score=0.95,
                    ),
                    ChunkDetail(
                        chunk_id=uuid4(),
                        chunk_index=1,
                        chunk_text="Chunk 2 text",
                        score=0.85,
                    ),
                ],
            )
        ]

    @pytest.fixture
    def sample_stage_timings(self):
        """Sample stage timings."""
        return {
            "query_extraction": 450.2,
            "embedding": 320.5,
            "hybrid_search": 890.3,
            "fusion": 12.1,
            "reranking": 1650.8,
            "aggregation": 8.3,
        }

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_key_deterministic(self, cache_service):
        """Test that cache key generation is deterministic."""
        text = "Test post text"
        key1 = cache_service._generate_key(text)
        key2 = cache_service._generate_key(text)

        assert key1 == key2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_key_different_texts(self, cache_service):
        """Test that different texts generate different keys."""
        key1 = cache_service._generate_key("Text 1")
        key2 = cache_service._generate_key("Text 2")

        assert key1 != key2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_key_format(self, cache_service):
        """Test cache key format includes prefix and hash."""
        text = "Test post"
        key = cache_service._generate_key(text)

        # Should start with prefix
        assert key.startswith(cache_service.key_prefix)

        # Should include SHA256 hash
        expected_hash = hashlib.sha256(text.encode()).hexdigest()
        assert expected_hash in key

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_set_and_get_cache(
        self,
        cache_service,
        sample_post_text,
        sample_article_results,
        sample_stage_timings,
    ):
        """Test setting and retrieving cached results."""
        # Set cache
        await cache_service.set(
            post_text=sample_post_text,
            articles=sample_article_results,
            total_time_ms=3500,
            stage_timings=sample_stage_timings,
            query_count=3,
        )

        # Get cache
        cached_result = await cache_service.get(sample_post_text)

        # Verify result structure
        assert cached_result is not None
        assert "articles" in cached_result
        assert "total_time_ms" in cached_result
        assert "stage_timings" in cached_result
        assert "query_count" in cached_result

        # Verify values
        assert cached_result["total_time_ms"] == 3500
        assert cached_result["query_count"] == 3
        assert len(cached_result["articles"]) == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_cache_miss(self, cache_service):
        """Test getting a non-existent cache entry."""
        result = await cache_service.get("Non-existent post text")
        assert result is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_disabled_cache(self, cache_service, sample_post_text):
        """Test that disabled cache returns None."""
        cache_service.enabled = False

        result = await cache_service.get(sample_post_text)
        assert result is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_set_disabled_cache(
        self,
        cache_service,
        sample_post_text,
        sample_article_results,
        sample_stage_timings,
        mock_redis,
    ):
        """Test that disabled cache doesn't store anything."""
        cache_service.enabled = False

        await cache_service.set(
            post_text=sample_post_text,
            articles=sample_article_results,
            total_time_ms=3500,
            stage_timings=sample_stage_timings,
            query_count=3,
        )

        # Verify nothing was stored (mock_redis should be empty)
        # Since cache is disabled, setex should not be called
        keys = await mock_redis.keys("*")
        assert len(keys) == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cache_key_exact_match(
        self,
        cache_service,
        sample_article_results,
        sample_stage_timings,
    ):
        """Test that cache only returns results for exact text match."""
        text1 = "VinTech xây nhà máy"
        text2 = "VinTech xây nhà máy "  # Extra space

        # Set cache for text1
        await cache_service.set(
            post_text=text1,
            articles=sample_article_results,
            total_time_ms=3500,
            stage_timings=sample_stage_timings,
            query_count=3,
        )

        # Get with exact text should hit
        result1 = await cache_service.get(text1)
        assert result1 is not None

        # Get with different text should miss
        result2 = await cache_service.get(text2)
        assert result2 is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cache_serialization(
        self,
        cache_service,
        sample_post_text,
        sample_article_results,
        sample_stage_timings,
    ):
        """Test that ArticleResult objects are properly serialized/deserialized."""
        await cache_service.set(
            post_text=sample_post_text,
            articles=sample_article_results,
            total_time_ms=3500,
            stage_timings=sample_stage_timings,
            query_count=3,
        )

        cached_result = await cache_service.get(sample_post_text)

        # Verify article structure
        article = cached_result["articles"][0]
        assert "article_id" in article
        assert "title" in article
        assert "source_name" in article
        assert "relevance_score" in article
        assert "chunk_count" in article
        assert "relevant_chunks" in article

        # Verify article values
        assert article["title"] == "VinTech công bố dự án nhà máy mới"
        assert article["source_name"] == "VnExpress"
        assert article["relevance_score"] == 2.45
        assert article["chunk_count"] == 3
        assert len(article["relevant_chunks"]) == 2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cache_stage_timings(
        self,
        cache_service,
        sample_post_text,
        sample_article_results,
        sample_stage_timings,
    ):
        """Test that stage timings are properly cached."""
        await cache_service.set(
            post_text=sample_post_text,
            articles=sample_article_results,
            total_time_ms=3500,
            stage_timings=sample_stage_timings,
            query_count=3,
        )

        cached_result = await cache_service.get(sample_post_text)

        # Verify stage timings
        stage_timings = cached_result["stage_timings"]
        assert stage_timings["query_extraction"] == 450.2
        assert stage_timings["embedding"] == 320.5
        assert stage_timings["hybrid_search"] == 890.3
        assert stage_timings["fusion"] == 12.1
        assert stage_timings["reranking"] == 1650.8
        assert stage_timings["aggregation"] == 8.3

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_clear_all_cache(
        self,
        cache_service,
        sample_post_text,
        sample_article_results,
        sample_stage_timings,
    ):
        """Test clearing all cache entries."""
        # Add multiple cache entries
        await cache_service.set(
            post_text=sample_post_text,
            articles=sample_article_results,
            total_time_ms=3500,
            stage_timings=sample_stage_timings,
            query_count=3,
        )

        await cache_service.set(
            post_text="Another post text",
            articles=sample_article_results,
            total_time_ms=2500,
            stage_timings=sample_stage_timings,
            query_count=2,
        )

        # Clear all
        deleted_count = await cache_service.clear_all()

        # Should have deleted 2 entries
        assert deleted_count == 2

        # Verify cache is empty
        result = await cache_service.get(sample_post_text)
        assert result is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_clear_empty_cache(self, cache_service):
        """Test clearing cache when it's already empty."""
        deleted_count = await cache_service.clear_all()
        assert deleted_count == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_clear_disabled_cache(self, cache_service):
        """Test that clearing disabled cache returns 0."""
        cache_service.enabled = False

        deleted_count = await cache_service.clear_all()
        assert deleted_count == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cache_empty_articles_list(
        self, cache_service, sample_post_text, sample_stage_timings
    ):
        """Test caching with empty articles list."""
        await cache_service.set(
            post_text=sample_post_text,
            articles=[],
            total_time_ms=1000,
            stage_timings=sample_stage_timings,
            query_count=1,
        )

        cached_result = await cache_service.get(sample_post_text)
        assert cached_result is not None
        assert cached_result["articles"] == []

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cache_unicode_text(
        self, cache_service, sample_article_results, sample_stage_timings
    ):
        """Test caching with Vietnamese Unicode text."""
        vietnamese_text = (
            "Công ty VinTech đầu tư 5 tỷ USD vào dự án nhà máy công nghệ cao"
        )

        await cache_service.set(
            post_text=vietnamese_text,
            articles=sample_article_results,
            total_time_ms=3500,
            stage_timings=sample_stage_timings,
            query_count=3,
        )

        cached_result = await cache_service.get(vietnamese_text)
        assert cached_result is not None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cache_special_characters(
        self, cache_service, sample_article_results, sample_stage_timings
    ):
        """Test caching with special characters and emojis."""
        text_with_special_chars = "VinTech!!! 🎉🎊 Dự án #mới @2024"

        await cache_service.set(
            post_text=text_with_special_chars,
            articles=sample_article_results,
            total_time_ms=3500,
            stage_timings=sample_stage_timings,
            query_count=3,
        )

        cached_result = await cache_service.get(text_with_special_chars)
        assert cached_result is not None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cache_very_long_text(
        self, cache_service, sample_article_results, sample_stage_timings
    ):
        """Test caching with very long text."""
        long_text = "VinTech " * 1000  # Very long text

        await cache_service.set(
            post_text=long_text,
            articles=sample_article_results,
            total_time_ms=3500,
            stage_timings=sample_stage_timings,
            query_count=3,
        )

        cached_result = await cache_service.get(long_text)
        assert cached_result is not None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_close_connection(self, cache_service):
        """Test closing Redis connection."""
        # Should not raise any errors
        await cache_service.close()

        # After closing, client should still work (FakeRedis doesn't actually close)
        # In real Redis, this would require reconnection
