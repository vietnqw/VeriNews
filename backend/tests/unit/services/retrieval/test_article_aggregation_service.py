"""
Unit tests for Article Aggregation Service.

Tests the aggregation of chunk-level results to article-level results,
including relevance filtering, score summation, and result limiting.
"""

import pytest
from uuid import uuid4

from app.services.retrieval.article_aggregation_service import ArticleAggregationService
from app.services.retrieval.bm25_search_service import ChunkSearchResult


class TestArticleAggregationService:
    """Test suite for ArticleAggregationService."""

    @pytest.fixture
    def aggregation_service(self):
        """Create an ArticleAggregationService instance with test defaults."""
        service = ArticleAggregationService()
        # Override settings for predictable tests
        service.score_threshold = 0.7
        service.max_articles = 10
        service.include_chunks = True
        return service

    @pytest.fixture
    def sample_chunks(self):
        """Create sample chunk results for testing."""
        article_id_1 = uuid4()
        article_id_2 = uuid4()

        return [
            # Article 1: 3 chunks with high scores
            ChunkSearchResult(
                chunk_id=uuid4(),
                chunk_text="Chunk 1 content",
                chunk_index=0,
                article_id=article_id_1,
                article_title="VinTech xây nhà máy tại Hà Nội",
                source_name="VnExpress",
                score=0.95,
            ),
            ChunkSearchResult(
                chunk_id=uuid4(),
                chunk_text="Chunk 2 content",
                chunk_index=1,
                article_id=article_id_1,
                article_title="VinTech xây nhà máy tại Hà Nội",
                source_name="VnExpress",
                score=0.85,
            ),
            ChunkSearchResult(
                chunk_id=uuid4(),
                chunk_text="Chunk 3 content",
                chunk_index=2,
                article_id=article_id_1,
                article_title="VinTech xây nhà máy tại Hà Nội",
                source_name="VnExpress",
                score=0.75,
            ),
            # Article 2: 2 chunks with medium scores
            ChunkSearchResult(
                chunk_id=uuid4(),
                chunk_text="Chunk 4 content",
                chunk_index=0,
                article_id=article_id_2,
                article_title="Đầu tư công nghệ cao",
                source_name="Tuổi Trẻ",
                score=0.80,
            ),
            ChunkSearchResult(
                chunk_id=uuid4(),
                chunk_text="Chunk 5 content",
                chunk_index=1,
                article_id=article_id_2,
                article_title="Đầu tư công nghệ cao",
                source_name="Tuổi Trẻ",
                score=0.72,
            ),
        ]

    @pytest.mark.unit
    def test_aggregate_basic(self, aggregation_service, sample_chunks):
        """Test basic aggregation of chunks to articles."""
        articles = aggregation_service.aggregate_to_articles(sample_chunks)

        # Should return 2 articles
        assert len(articles) == 2

        # First article should have higher total score (0.95 + 0.85 + 0.75 = 2.55)
        assert articles[0].chunk_count == 3
        assert abs(articles[0].relevance_score - 2.55) < 0.01

        # Second article (0.80 + 0.72 = 1.52)
        assert articles[1].chunk_count == 2
        assert abs(articles[1].relevance_score - 1.52) < 0.01

    @pytest.mark.unit
    def test_aggregate_threshold_filtering(self, aggregation_service, sample_chunks):
        """Test that chunks below threshold are filtered out."""
        # Set high threshold (0.8) - should filter out chunks with scores < 0.8
        aggregation_service.score_threshold = 0.8

        articles = aggregation_service.aggregate_to_articles(sample_chunks)

        # Article 1: only 2 chunks pass (0.95, 0.85) - score 0.75 filtered out
        article_1 = next(a for a in articles if a.chunk_count == 2)
        assert abs(article_1.relevance_score - (0.95 + 0.85)) < 0.01

        # Article 2: only 1 chunk passes (0.80) - score 0.72 filtered out
        article_2 = next(a for a in articles if a.chunk_count == 1)
        assert abs(article_2.relevance_score - 0.80) < 0.01

    @pytest.mark.unit
    def test_aggregate_max_articles_limit(self, aggregation_service, sample_chunks):
        """Test that max_articles limit is respected."""
        aggregation_service.max_articles = 1  # Only return top 1 article

        articles = aggregation_service.aggregate_to_articles(sample_chunks)

        # Should only return 1 article (the one with highest score)
        assert len(articles) == 1
        assert articles[0].chunk_count == 3  # Article with 3 chunks

    @pytest.mark.unit
    def test_aggregate_empty_chunks(self, aggregation_service):
        """Test aggregation with empty chunk list."""
        articles = aggregation_service.aggregate_to_articles([])
        assert articles == []

    @pytest.mark.unit
    def test_aggregate_all_filtered(self, aggregation_service, sample_chunks):
        """Test when all chunks are filtered by threshold."""
        # Set threshold above all scores
        aggregation_service.score_threshold = 0.99

        articles = aggregation_service.aggregate_to_articles(sample_chunks)
        assert articles == []

    @pytest.mark.unit
    def test_aggregate_article_metadata(self, aggregation_service, sample_chunks):
        """Test that article metadata is correctly preserved."""
        articles = aggregation_service.aggregate_to_articles(sample_chunks)

        # Check first article metadata
        article = articles[0]
        assert article.article_id is not None
        assert article.title == "VinTech xây nhà máy tại Hà Nội"
        assert article.source_name == "VnExpress"
        assert article.published_at is None  # ChunkSearchResult doesn't include this

    @pytest.mark.unit
    def test_aggregate_relevant_chunks_included(
        self, aggregation_service, sample_chunks
    ):
        """Test that relevant chunks are included in article results."""
        articles = aggregation_service.aggregate_to_articles(sample_chunks)

        # First article should have 3 relevant chunks
        article = articles[0]
        assert len(article.relevant_chunks) == 3

        # Chunks should be present (order may vary based on insertion)
        chunk_scores = [chunk.score for chunk in article.relevant_chunks]
        assert 0.95 in chunk_scores
        assert 0.85 in chunk_scores
        assert 0.75 in chunk_scores

    @pytest.mark.unit
    def test_aggregate_sort_order(self, aggregation_service, sample_chunks):
        """Test that articles are sorted by relevance score (descending)."""
        articles = aggregation_service.aggregate_to_articles(sample_chunks)

        # Articles should be sorted by total score
        for i in range(len(articles) - 1):
            assert articles[i].relevance_score >= articles[i + 1].relevance_score

    @pytest.mark.unit
    def test_aggregate_single_chunk_article(self, aggregation_service):
        """Test aggregation with articles that have only one chunk."""
        single_chunk = [
            ChunkSearchResult(
                chunk_id=uuid4(),
                chunk_text="Single chunk content",
                chunk_index=0,
                article_id=uuid4(),
                article_title="Single chunk article",
                source_name="Test Source",
                score=0.88,
            )
        ]

        articles = aggregation_service.aggregate_to_articles(single_chunk)

        assert len(articles) == 1
        assert articles[0].chunk_count == 1
        assert abs(articles[0].relevance_score - 0.88) < 0.01

    @pytest.mark.unit
    def test_aggregate_threshold_edge_case(self, aggregation_service):
        """Test chunks with scores exactly at threshold."""
        chunks = [
            ChunkSearchResult(
                chunk_id=uuid4(),
                chunk_text="Chunk at threshold",
                chunk_index=0,
                article_id=uuid4(),
                article_title="Edge case article",
                source_name="Test Source",
                score=0.70,  # Exactly at threshold
            )
        ]

        articles = aggregation_service.aggregate_to_articles(chunks)

        # Chunk with score == threshold should be included
        assert len(articles) == 1
        assert articles[0].relevance_score == 0.70

    @pytest.mark.unit
    def test_aggregate_many_articles(self, aggregation_service):
        """Test aggregation with many articles."""
        # Create 20 articles with 1 chunk each
        chunks = []
        for i in range(20):
            chunks.append(
                ChunkSearchResult(
                    chunk_id=uuid4(),
                    chunk_text=f"Content {i}",
                    chunk_index=0,
                    article_id=uuid4(),
                    article_title=f"Article {i}",
                    source_name="Test Source",
                    score=0.9 - (i * 0.01),  # Decreasing scores
                )
            )

        # Request only top 5 articles
        aggregation_service.max_articles = 5

        articles = aggregation_service.aggregate_to_articles(chunks)

        assert len(articles) == 5

        # Should get the top 5 by score
        assert articles[0].title == "Article 0"
        assert articles[4].title == "Article 4"

    @pytest.mark.unit
    def test_aggregate_score_precision(self, aggregation_service):
        """Test that score summation maintains precision."""
        article_id = uuid4()
        # Use higher scores that pass the threshold
        chunks = [
            ChunkSearchResult(
                chunk_id=uuid4(),
                chunk_text=f"Chunk {i}",
                chunk_index=i,
                article_id=article_id,
                article_title="Precision test",
                source_name="Test Source",
                score=0.823456789,
            )
            for i in range(3)
        ]

        articles = aggregation_service.aggregate_to_articles(chunks)

        # Sum should maintain precision: 0.823456789 * 3 = 2.470370367
        expected_score = 0.823456789 * 3
        assert abs(articles[0].relevance_score - expected_score) < 1e-9

    @pytest.mark.unit
    def test_aggregate_include_chunks_disabled(
        self, aggregation_service, sample_chunks
    ):
        """Test that chunks are not included when include_chunks is False."""
        aggregation_service.include_chunks = False

        articles = aggregation_service.aggregate_to_articles(sample_chunks)

        # Articles should have empty relevant_chunks list
        for article in articles:
            assert article.relevant_chunks == []
            assert article.chunk_count > 0  # But chunk_count is still tracked

    @pytest.mark.unit
    def test_aggregate_to_dict(self, aggregation_service, sample_chunks):
        """Test ArticleResult.to_dict() serialization."""
        articles = aggregation_service.aggregate_to_articles(sample_chunks)

        article_dict = articles[0].to_dict()

        # Check dict structure
        assert "article_id" in article_dict
        assert "title" in article_dict
        assert "source_name" in article_dict
        assert "published_at" in article_dict
        assert "relevance_score" in article_dict
        assert "chunk_count" in article_dict
        assert "relevant_chunks" in article_dict

        # Check types
        assert isinstance(article_dict["article_id"], str)
        assert isinstance(article_dict["title"], str)
        assert isinstance(article_dict["relevance_score"], float)
        assert isinstance(article_dict["chunk_count"], int)
        assert isinstance(article_dict["relevant_chunks"], list)
