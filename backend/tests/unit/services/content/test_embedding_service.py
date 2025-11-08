"""
Unit tests for Embedding Service.

Tests embedding generation for both single text and batch operations.
Uses mocked OpenAI API responses.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from openai import RateLimitError, APIError, APIConnectionError

from app.services.content.embedding_service import (
    generate_embedding,
    generate_embedding_async,
    generate_embeddings_batch,
    get_embedding_dimensions,
)
from app.services.ai.base import EmbeddingResponse


@pytest.mark.unit
class TestEmbeddingService:
    """Unit tests for embedding service."""

    @pytest.fixture
    def mock_embedding_provider(self):
        """Mock embedding provider for testing."""
        mock = AsyncMock()
        mock.dimensions = 1536
        return mock

    @pytest.fixture
    def sample_embedding_vector(self):
        """Sample 1536-dimensional embedding vector."""
        return [0.1 * i for i in range(1536)]

    @pytest.fixture
    def sample_embedding_response(self, sample_embedding_vector):
        """Sample embedding response."""
        return EmbeddingResponse(
            embedding=sample_embedding_vector,
            model="text-embedding-3-small",
            usage={"prompt_tokens": 10, "total_tokens": 10},
        )

    # ==================== Single Embedding Tests ====================

    @pytest.mark.asyncio
    async def test_generate_embedding_async_success(
        self, mock_embedding_provider, sample_embedding_response
    ):
        """Test successful single embedding generation."""
        mock_embedding_provider.generate_embedding = AsyncMock(
            return_value=sample_embedding_response
        )

        with patch(
            "app.services.content.embedding_service.AIServiceFactory.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            result = await generate_embedding_async("Test text")

            assert len(result) == 1536
            assert all(isinstance(x, float) for x in result)
            mock_embedding_provider.generate_embedding.assert_called_once_with(
                "Test text"
            )

    def test_generate_embedding_sync_wrapper(
        self, mock_embedding_provider, sample_embedding_response
    ):
        """Test synchronous wrapper for embedding generation."""
        mock_embedding_provider.generate_embedding = AsyncMock(
            return_value=sample_embedding_response
        )

        with patch(
            "app.services.content.embedding_service.AIServiceFactory.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            result = generate_embedding("Test text")

            assert len(result) == 1536
            assert all(isinstance(x, float) for x in result)

    @pytest.mark.asyncio
    async def test_generate_embedding_empty_text(
        self, mock_embedding_provider, sample_embedding_response
    ):
        """Test embedding generation with empty text."""
        mock_embedding_provider.generate_embedding = AsyncMock(
            return_value=sample_embedding_response
        )

        with patch(
            "app.services.content.embedding_service.AIServiceFactory.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            result = await generate_embedding_async("")

            assert len(result) == 1536
            mock_embedding_provider.generate_embedding.assert_called_once_with("")

    @pytest.mark.asyncio
    async def test_generate_embedding_vietnamese_text(
        self, mock_embedding_provider, sample_embedding_response
    ):
        """Test embedding generation with Vietnamese text."""
        vietnamese_text = "VinGroup công bố kế hoạch xây dựng nhà máy bán dẫn"

        mock_embedding_provider.generate_embedding = AsyncMock(
            return_value=sample_embedding_response
        )

        with patch(
            "app.services.content.embedding_service.AIServiceFactory.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            result = await generate_embedding_async(vietnamese_text)

            assert len(result) == 1536
            mock_embedding_provider.generate_embedding.assert_called_once_with(
                vietnamese_text
            )

    @pytest.mark.asyncio
    async def test_generate_embedding_special_characters(
        self, mock_embedding_provider, sample_embedding_response
    ):
        """Test embedding generation with special characters and emojis."""
        text_with_special = "VinTech 🎉🎉 xây nhà máy 5 tỷ USD!!! @#$%"

        mock_embedding_provider.generate_embedding = AsyncMock(
            return_value=sample_embedding_response
        )

        with patch(
            "app.services.content.embedding_service.AIServiceFactory.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            result = await generate_embedding_async(text_with_special)

            assert len(result) == 1536
            mock_embedding_provider.generate_embedding.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_embedding_very_long_text(
        self, mock_embedding_provider, sample_embedding_response
    ):
        """Test embedding generation with text longer than 8191 tokens."""
        # Create a very long text (approximate ~10k tokens)
        long_text = "Văn bản dài. " * 5000

        mock_embedding_provider.generate_embedding = AsyncMock(
            return_value=sample_embedding_response
        )

        with patch(
            "app.services.content.embedding_service.AIServiceFactory.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            result = await generate_embedding_async(long_text)

            assert len(result) == 1536
            # Verify the provider was called with the long text
            mock_embedding_provider.generate_embedding.assert_called_once()

    # ==================== Batch Embedding Tests ====================

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_success(
        self, mock_embedding_provider, sample_embedding_vector
    ):
        """Test successful batch embedding generation."""
        texts = ["Text 1", "Text 2", "Text 3"]

        batch_responses = [
            EmbeddingResponse(
                embedding=[0.1 * (i + 1) * j for j in range(1536)],
                model="text-embedding-3-small",
                usage={"prompt_tokens": 5, "total_tokens": 5},
            )
            for i in range(3)
        ]

        mock_embedding_provider.generate_embeddings_batch = AsyncMock(
            return_value=batch_responses
        )

        with patch(
            "app.services.content.embedding_service.AIServiceFactory.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            result = await generate_embeddings_batch(texts)

            assert len(result) == 3
            assert all(len(emb) == 1536 for emb in result)
            mock_embedding_provider.generate_embeddings_batch.assert_called_once_with(
                texts
            )

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_single_text(
        self, mock_embedding_provider, sample_embedding_response
    ):
        """Test batch embedding with single text."""
        texts = ["Single text"]

        mock_embedding_provider.generate_embeddings_batch = AsyncMock(
            return_value=[sample_embedding_response]
        )

        with patch(
            "app.services.content.embedding_service.AIServiceFactory.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            result = await generate_embeddings_batch(texts)

            assert len(result) == 1
            assert len(result[0]) == 1536

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_empty_list(self, mock_embedding_provider):
        """Test batch embedding with empty list."""
        mock_embedding_provider.generate_embeddings_batch = AsyncMock(return_value=[])

        with patch(
            "app.services.content.embedding_service.AIServiceFactory.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            result = await generate_embeddings_batch([])

            assert len(result) == 0
            mock_embedding_provider.generate_embeddings_batch.assert_called_once_with(
                []
            )

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_vietnamese_texts(
        self, mock_embedding_provider, sample_embedding_vector
    ):
        """Test batch embedding with Vietnamese texts."""
        vietnamese_texts = [
            "VinGroup công bố kế hoạch",
            "Nhà máy bán dẫn tại Hà Nội",
            "Tổng vốn đầu tư 5 tỷ USD",
        ]

        batch_responses = [
            EmbeddingResponse(
                embedding=[0.1 * (i + 1) * j for j in range(1536)],
                model="text-embedding-3-small",
                usage={"prompt_tokens": 5, "total_tokens": 5},
            )
            for i in range(3)
        ]

        mock_embedding_provider.generate_embeddings_batch = AsyncMock(
            return_value=batch_responses
        )

        with patch(
            "app.services.content.embedding_service.AIServiceFactory.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            result = await generate_embeddings_batch(vietnamese_texts)

            assert len(result) == 3
            assert all(len(emb) == 1536 for emb in result)

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_large_batch(
        self, mock_embedding_provider, sample_embedding_vector
    ):
        """Test batch embedding with large number of texts."""
        texts = [f"Text {i}" for i in range(100)]

        batch_responses = [
            EmbeddingResponse(
                embedding=[0.1 * (i + 1) * j for j in range(1536)],
                model="text-embedding-3-small",
                usage={"prompt_tokens": 5, "total_tokens": 5},
            )
            for i in range(100)
        ]

        mock_embedding_provider.generate_embeddings_batch = AsyncMock(
            return_value=batch_responses
        )

        with patch(
            "app.services.content.embedding_service.AIServiceFactory.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            result = await generate_embeddings_batch(texts)

            assert len(result) == 100
            assert all(len(emb) == 1536 for emb in result)

    # ==================== Error Handling Tests ====================

    @pytest.mark.asyncio
    async def test_generate_embedding_api_error(self, mock_embedding_provider):
        """Test handling of OpenAI API errors."""
        mock_embedding_provider.generate_embedding = AsyncMock(
            side_effect=APIError(
                "API Error",
                request=MagicMock(),
                body=None,
            )
        )

        with patch(
            "app.services.content.embedding_service.AIServiceFactory.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            with pytest.raises(APIError):
                await generate_embedding_async("Test text")

    @pytest.mark.asyncio
    async def test_generate_embedding_rate_limit_error(self, mock_embedding_provider):
        """Test handling of rate limit errors."""
        mock_embedding_provider.generate_embedding = AsyncMock(
            side_effect=RateLimitError(
                "Rate limit exceeded",
                response=MagicMock(),
                body=None,
            )
        )

        with patch(
            "app.services.content.embedding_service.AIServiceFactory.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            with pytest.raises(RateLimitError):
                await generate_embedding_async("Test text")

    @pytest.mark.asyncio
    async def test_generate_embedding_connection_error(self, mock_embedding_provider):
        """Test handling of connection errors."""
        mock_embedding_provider.generate_embedding = AsyncMock(
            side_effect=APIConnectionError(request=MagicMock())
        )

        with patch(
            "app.services.content.embedding_service.AIServiceFactory.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            with pytest.raises(APIConnectionError):
                await generate_embedding_async("Test text")

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_api_error(self, mock_embedding_provider):
        """Test batch embedding with API error."""
        mock_embedding_provider.generate_embeddings_batch = AsyncMock(
            side_effect=APIError(
                "Batch API Error",
                request=MagicMock(),
                body=None,
            )
        )

        with patch(
            "app.services.content.embedding_service.AIServiceFactory.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            with pytest.raises(APIError):
                await generate_embeddings_batch(["Text 1", "Text 2"])

    # ==================== Utility Function Tests ====================

    def test_get_embedding_dimensions(self, mock_embedding_provider):
        """Test getting embedding dimensions from provider."""
        with patch(
            "app.services.content.embedding_service.AIServiceFactory.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            dimensions = get_embedding_dimensions()

            assert dimensions == 1536

    # ==================== Concurrent Request Tests ====================

    @pytest.mark.asyncio
    async def test_concurrent_embedding_requests(
        self, mock_embedding_provider, sample_embedding_response
    ):
        """Test handling of concurrent embedding requests."""
        import asyncio

        mock_embedding_provider.generate_embedding = AsyncMock(
            return_value=sample_embedding_response
        )

        with patch(
            "app.services.content.embedding_service.AIServiceFactory.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            # Generate 10 concurrent requests
            tasks = [generate_embedding_async(f"Text {i}") for i in range(10)]
            results = await asyncio.gather(*tasks)

            assert len(results) == 10
            assert all(len(emb) == 1536 for emb in results)
            # Verify all requests were made
            assert mock_embedding_provider.generate_embedding.call_count == 10
