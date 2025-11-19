"""
Unit tests for Query Extraction Service.

Tests LLM-based extraction of clean queries and claims from Facebook posts.
Uses mocked OpenAI API responses.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.retrieval.query_extraction_service import QueryExtractionService


@pytest.mark.unit
class TestQueryExtractionService:
    """Unit tests for query extraction service."""

    @pytest.fixture
    def mock_llm_provider(self):
        """Mock LLM provider for testing."""
        mock = AsyncMock()
        return mock

    @pytest.fixture
    def extraction_service(self, mock_llm_provider):
        """Create query extraction service with mocked LLM."""
        with patch(
            "app.services.retrieval.query_extraction_service.AIServiceFactory.get_llm_provider",
            return_value=mock_llm_provider,
        ):
            service = QueryExtractionService()
            service.llm = mock_llm_provider
            return service

    @pytest.mark.asyncio
    async def test_extract_clean_query_and_claims(
        self, extraction_service, mock_llm_provider
    ):
        """Test successful extraction of clean query and claims."""
        # Mock LLM response (with CoT reasoning before JSON)
        mock_response = MagicMock()
        mock_response.content = """RATIONALE: This post contains specific factual claims with entities.

{
    "clean_query": "VinTech xây dựng nhà máy trị giá 5 tỷ USD tại Hà Nội",
    "claims": [
        "VinTech xây dựng nhà máy tại Hà Nội",
        "Nhà máy có giá trị 5 tỷ USD",
        "Dự án được công bố năm 2024"
    ],
    "factual_confidence": 3
}"""
        mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)

        # Test extraction
        post_text = "VinTech xây nhà máy 5 tỷ USD ở Hà Nội!!! Tuyệt vời 🎉🎉"
        result = await extraction_service.extract_queries(post_text)

        # Verify result structure
        assert "clean_query" in result
        assert "claims" in result
        assert "query_count" in result
        assert "factual_confidence" in result

        # Verify content
        assert (
            result["clean_query"]
            == "VinTech xây dựng nhà máy trị giá 5 tỷ USD tại Hà Nội"
        )
        assert len(result["claims"]) == 3
        assert result["query_count"] == 4  # 1 clean_query + 3 claims
        assert result["factual_confidence"] == 3

    @pytest.mark.asyncio
    async def test_extract_with_no_claims(self, extraction_service, mock_llm_provider):
        """Test extraction when LLM returns no claims."""
        mock_response = MagicMock()
        mock_response.content = """RATIONALE: This is a vague statement.

{
    "clean_query": "Thời tiết hôm nay đẹp",
    "claims": [],
    "factual_confidence": 2
}"""
        mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)

        result = await extraction_service.extract_queries("Thời tiết hôm nay đẹp!")

        assert result["clean_query"] == "Thời tiết hôm nay đẹp"
        assert result["claims"] == []
        assert result["query_count"] == 1  # Only clean_query
        assert result["factual_confidence"] == 2

    @pytest.mark.asyncio
    async def test_extract_limits_max_claims(
        self, extraction_service, mock_llm_provider
    ):
        """Test that excessive claims are truncated to max_claims."""
        # Set max_claims to 3
        extraction_service.max_claims = 3

        # Mock response with 5 claims
        mock_response = MagicMock()
        mock_response.content = json.dumps(
            {
                "clean_query": "Test query",
                "claims": ["Claim 1", "Claim 2", "Claim 3", "Claim 4", "Claim 5"],
                "factual_confidence": 8.0,
            }
        )
        mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)

        result = await extraction_service.extract_queries("Test post")

        # Should truncate to 3 claims
        assert len(result["claims"]) == 3
        assert result["query_count"] == 4  # 1 clean_query + 3 claims
        assert result["claims"] == ["Claim 1", "Claim 2", "Claim 3"]

    @pytest.mark.asyncio
    async def test_extract_filters_empty_claims(
        self, extraction_service, mock_llm_provider
    ):
        """Test that empty/whitespace claims are filtered out."""
        mock_response = MagicMock()
        mock_response.content = json.dumps(
            {
                "clean_query": "Test query",
                "claims": [
                    "Valid claim 1",
                    "",  # Empty
                    "   ",  # Whitespace only
                    "Valid claim 2",
                    "\n\t",  # Whitespace with newlines
                ],
                "factual_confidence": 7.0,
            }
        )
        mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)

        result = await extraction_service.extract_queries("Test post")

        # Should only keep valid claims
        assert len(result["claims"]) == 2
        assert result["claims"] == ["Valid claim 1", "Valid claim 2"]

    @pytest.mark.asyncio
    async def test_extract_handles_json_decode_error(
        self, extraction_service, mock_llm_provider
    ):
        """Test fallback when LLM returns invalid JSON."""
        # Mock invalid JSON response
        mock_response = MagicMock()
        mock_response.content = "This is not valid JSON { invalid }"
        mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)

        post_text = "VinTech xây nhà máy"
        result = await extraction_service.extract_queries(post_text)

        # Should fallback to using original post as clean_query
        assert result["clean_query"] == post_text
        assert result["claims"] == []
        assert result["query_count"] == 1

    @pytest.mark.asyncio
    async def test_extract_handles_llm_exception(
        self, extraction_service, mock_llm_provider
    ):
        """Test fallback when LLM raises an exception."""
        # Mock LLM exception
        mock_llm_provider.generate_completion = AsyncMock(
            side_effect=Exception("API Error")
        )

        post_text = "VinTech xây nhà máy 5 tỷ USD"
        result = await extraction_service.extract_queries(post_text)

        # Should fallback to using original post as clean_query
        assert result["clean_query"] == post_text
        assert result["claims"] == []
        assert result["query_count"] == 1

    @pytest.mark.asyncio
    async def test_extract_handles_missing_keys_in_response(
        self, extraction_service, mock_llm_provider
    ):
        """Test handling of LLM response missing expected keys."""
        # Mock response with missing 'claims' key
        mock_response = MagicMock()
        mock_response.content = json.dumps({"clean_query": "Test query"})
        mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)

        result = await extraction_service.extract_queries("Test post")

        # Should handle missing 'claims' gracefully
        assert result["clean_query"] == "Test query"
        assert result["claims"] == []
        assert result["query_count"] == 1

    @pytest.mark.asyncio
    async def test_extract_vietnamese_characters(
        self, extraction_service, mock_llm_provider
    ):
        """Test extraction with Vietnamese Unicode characters."""
        mock_response = MagicMock()
        mock_response.content = json.dumps(
            {
                "clean_query": "Công ty VinTech xây dựng nhà máy",
                "claims": ["Nhà máy sản xuất chip bán dẫn"],
            }
        )
        mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)

        post = "Công ty VinTech xây nhà máy!!! 🎉"
        result = await extraction_service.extract_queries(post)

        assert "Công ty VinTech" in result["clean_query"]
        assert "chip bán dẫn" in result["claims"][0]

    @pytest.mark.asyncio
    async def test_extract_strips_whitespace(
        self, extraction_service, mock_llm_provider
    ):
        """Test that whitespace is stripped from clean_query and claims."""
        mock_response = MagicMock()
        mock_response.content = json.dumps(
            {
                "clean_query": "  Test query with spaces  ",
                "claims": ["  Claim 1  ", "  Claim 2  "],
            }
        )
        mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)

        result = await extraction_service.extract_queries("Test post")

        # Should strip whitespace
        assert result["clean_query"] == "Test query with spaces"
        assert result["claims"] == ["Claim 1", "Claim 2"]

    @pytest.mark.asyncio
    async def test_prompt_includes_post_text(
        self, extraction_service, mock_llm_provider
    ):
        """Test that the prompt includes the original post text."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({"clean_query": "Test", "claims": []})
        mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)

        post_text = "VinTech xây nhà máy 5 tỷ USD"
        await extraction_service.extract_queries(post_text)

        # Verify LLM was called
        assert mock_llm_provider.generate_completion.called

        # Get the call arguments
        call_args = mock_llm_provider.generate_completion.call_args
        messages = call_args.kwargs["messages"]

        # Verify post text is in the prompt
        prompt_content = messages[0].content
        assert post_text in prompt_content

    @pytest.mark.asyncio
    async def test_prompt_specifies_json_format(
        self, extraction_service, mock_llm_provider
    ):
        """Test that the prompt requests CoT reasoning then JSON format."""
        mock_response = MagicMock()
        mock_response.content = """RATIONALE: Simple test.

{"clean_query": "Test", "claims": [], "factual_confidence": 1}"""
        mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)

        await extraction_service.extract_queries("Test post")

        # Verify response_format is NOT set (we allow free text for CoT)
        call_args = mock_llm_provider.generate_completion.call_args
        assert "response_format" not in call_args.kwargs

    @pytest.mark.asyncio
    async def test_extract_query_count_calculation(
        self, extraction_service, mock_llm_provider
    ):
        """Test that query_count is calculated correctly."""
        # Test with varying number of claims
        test_cases = [
            (0, 1),  # 0 claims → query_count = 1
            (1, 2),  # 1 claim → query_count = 2
            (3, 4),  # 3 claims → query_count = 4
            (5, 6),  # 5 claims → query_count = 6
        ]

        for num_claims, expected_count in test_cases:
            mock_response = MagicMock()
            mock_response.content = json.dumps(
                {
                    "clean_query": "Test",
                    "claims": [f"Claim {i}" for i in range(num_claims)],
                }
            )
            mock_llm_provider.generate_completion = AsyncMock(
                return_value=mock_response
            )

            result = await extraction_service.extract_queries("Test")
            assert result["query_count"] == expected_count

    @pytest.mark.asyncio
    async def test_extract_with_special_characters(
        self, extraction_service, mock_llm_provider
    ):
        """Test extraction with emojis and special characters."""
        mock_response = MagicMock()
        mock_response.content = json.dumps(
            {
                "clean_query": "VinTech announcement",
                "claims": ["Claim without emojis"],
                "factual_confidence": 8.0,
            }
        )
        mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)

        post = "VinTech!!! 🎉🎉 Tuyệt vời!!! ❤️❤️"
        result = await extraction_service.extract_queries(post)

        # Should successfully process despite emojis
        assert result["clean_query"] is not None
        assert len(result["claims"]) == 1

    @pytest.mark.asyncio
    async def test_extract_multi_sentence_claims(
        self, extraction_service, mock_llm_provider
    ):
        """Test extraction with multi-sentence claims that preserve context."""
        mock_response = MagicMock()
        mock_response.content = json.dumps(
            {
                "clean_query": "Nhổ răng 8 với Piezotome không đau không sưng không biến chứng tại Răng Hàm Mặt Hồng Ngọc",
                "claims": [
                    "Nhổ răng 8 với Piezotome không đau, không sưng, không biến chứng",
                    "Giảm giá 25% khi nhổ 1 răng, 30% khi nhổ 2 răng, và 35% khi nhổ từ 3 răng trở lên",
                    "Ưu đãi tại Răng Hàm Mặt Hồng Ngọc, liên hệ 091.110.3243 hoặc 024.3927.5565",
                ],
                "factual_confidence": 8.0,
            }
        )
        mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)

        post = """Nhổ răng 8 với Piezotome - Không đau, không sưng, không biến chứng
Nhổ 1 🦷 - Giảm ngay 25%
Nhổ 2 🦷🦷 - Giảm ngay 30%
Nhổ từ 🦷🦷🦷 - Giảm ngay 35%
   Ưu đãi chỉ có tại Răng Hàm Mặt Hồng Ngọc
📞 Liên hệ ngay 091.110.3243 | 024.3927.5565 để đặt lịch tư vấn miễn phí"""

        result = await extraction_service.extract_queries(post)

        # Verify multi-sentence claims are preserved
        assert len(result["claims"]) == 3
        assert "25%" in result["claims"][1]
        assert "30%" in result["claims"][1]
        assert "35%" in result["claims"][1]
        assert "091.110.3243" in result["claims"][2]
        assert "024.3927.5565" in result["claims"][2]

    @pytest.mark.asyncio
    async def test_extract_factual_confidence(
        self, extraction_service, mock_llm_provider
    ):
        """Test extraction with factual confidence scores (1-3 scale)."""
        mock_response = MagicMock()
        mock_response.content = """RATIONALE: Test.

{
    "clean_query": "Test query",
    "claims": ["Test claim"],
    "factual_confidence": 3
}"""
        mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)

        result = await extraction_service.extract_queries("Test post")

        assert "factual_confidence" in result
        assert result["factual_confidence"] == 3

    @pytest.mark.asyncio
    async def test_extract_factual_confidence_bounds(
        self, extraction_service, mock_llm_provider
    ):
        """Test that factual confidence is validated to [1, 2, 3] only."""
        # Test values - invalid values should default to 3
        test_cases = [
            (0, 3),  # Below 1 → defaults to 3
            (5, 3),  # Above 3 → defaults to 3
            (2, 2),  # Valid → unchanged
            (1, 1),  # Valid → unchanged
            (3, 3),  # Valid → unchanged
        ]

        for input_value, expected_value in test_cases:
            mock_response = MagicMock()
            mock_response.content = f"""RATIONALE: Test.

{{
    "clean_query": "Test",
    "claims": [],
    "factual_confidence": {input_value}
}}"""
            mock_llm_provider.generate_completion = AsyncMock(
                return_value=mock_response
            )

            result = await extraction_service.extract_queries("Test")
            assert result["factual_confidence"] == expected_value

    @pytest.mark.asyncio
    async def test_extract_factual_confidence_invalid_type(
        self, extraction_service, mock_llm_provider
    ):
        """Test handling of invalid factual_confidence type."""
        mock_response = MagicMock()
        mock_response.content = """RATIONALE: Test.

{
    "clean_query": "Test",
    "claims": [],
    "factual_confidence": "invalid"
}"""
        mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)

        result = await extraction_service.extract_queries("Test")

        # Should default to 3 when type is invalid
        assert result["factual_confidence"] == 3

    # Note: The following tests reference _extract_critical_entities method which was removed
    # Entity extraction is now done by the LLM in the prompt and validated with _validate_entity_preservation
    # These tests can be removed or refactored to test the new entity validation approach

    @pytest.mark.skip(
        reason="Method _extract_critical_entities no longer exists - entity extraction done by LLM"
    )
    def test_extract_critical_entities_phone_numbers(self, extraction_service):
        """Test extraction of phone numbers."""
        pass

    @pytest.mark.skip(
        reason="Method _extract_critical_entities no longer exists - entity extraction done by LLM"
    )
    def test_extract_critical_entities_percentages(self, extraction_service):
        """Test extraction of percentages."""
        pass

    @pytest.mark.skip(
        reason="Method _extract_critical_entities no longer exists - entity extraction done by LLM"
    )
    def test_extract_critical_entities_prices(self, extraction_service):
        """Test extraction of prices."""
        pass

    @pytest.mark.asyncio
    async def test_entity_preservation_validation(
        self, extraction_service, mock_llm_provider
    ):
        """Test that entity extraction works with new structure."""
        # Mock response with entities at post level (new structure)
        mock_response = MagicMock()
        mock_response.content = """RATIONALE: Test entity validation.

{
    "clean_query": "Nhổ răng 8 với Piezotome",
    "claims": [
        "Giảm giá khi nhổ răng"
    ],
    "entities": {
        "products_topics": ["Piezotome"]
    },
    "factual_confidence": 3
}"""
        mock_llm_provider.generate_completion = AsyncMock(return_value=mock_response)

        post = "Nhổ răng 8 với Piezotome giảm 25%. Liên hệ 091.110.3243"

        # Test that extraction works with new structure
        result = await extraction_service.extract_queries(post)

        # Verify the results
        assert result["clean_query"] == "Nhổ răng 8 với Piezotome"
        assert len(result["claims"]) == 1
        assert result["claims"][0] == "Giảm giá khi nhổ răng"
        assert "products_topics" in result["entities"]
        assert result["entities"]["products_topics"] == ["Piezotome"]
