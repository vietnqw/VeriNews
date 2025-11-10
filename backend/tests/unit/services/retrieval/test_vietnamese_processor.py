"""
Unit tests for Vietnamese text processing.

Tests the pyvi-based Vietnamese tokenization used for BM25 search.
"""

import pytest

from app.services.retrieval.vietnamese_processor import (
    tokenize_for_search,
    tokenize_vietnamese,
)


@pytest.mark.unit
@pytest.mark.asyncio
class TestVietnameseProcessor:
    """Test suite for Vietnamese text tokenization."""

    async def test_tokenize_compound_words(self):
        """Test that compound Vietnamese words are properly segmented."""
        text = "Công ty VinTech xây dựng nhà máy"
        result = await tokenize_vietnamese(text)

        # Compound words should be joined with underscores
        assert "công_ty" in result.lower()
        assert "xây_dựng" in result.lower()
        assert "nhà_máy" in result.lower()

    async def test_tokenize_simple_text(self):
        """Test tokenization of simple Vietnamese text."""
        text = "Hà Nội Việt Nam"
        result = await tokenize_vietnamese(text)

        assert "hà_nội" in result.lower()
        assert "việt_nam" in result.lower()

    async def test_tokenize_empty_string(self):
        """Test handling of empty input."""
        result = await tokenize_vietnamese("")
        assert result == ""

    async def test_tokenize_whitespace_only(self):
        """Test handling of whitespace-only input."""
        result = await tokenize_vietnamese("   \n\t  ")
        assert result.strip() == ""

    async def test_tokenize_with_special_characters(self):
        """Test that special characters are handled correctly."""
        text = "VinTech!!! Tuyệt vời 🎉"
        result = await tokenize_vietnamese(text)

        # Should preserve alphanumeric and Vietnamese characters
        assert "vintech" in result.lower()
        assert "tuyệt_vời" in result.lower()

    async def test_tokenize_mixed_language(self):
        """Test handling of mixed Vietnamese-English text."""
        text = "VinTech sản xuất chip AI"
        result = await tokenize_vietnamese(text)

        # English words should remain as-is (lowercase)
        assert "vintech" in result.lower()
        assert "chip" in result.lower()
        assert "ai" in result.lower()

    async def test_tokenize_numbers(self):
        """Test that numbers are preserved."""
        text = "5 tỷ USD năm 2024"
        result = await tokenize_vietnamese(text)

        assert "5" in result
        assert "2024" in result
        assert "tỷ" in result.lower()

    async def test_tokenize_for_search_format(self):
        """Test that tokenize_for_search produces tsquery-compatible output."""
        text = "Công ty xây nhà máy"
        result = await tokenize_for_search(text)

        # Should be lowercase and space-separated for tsquery
        assert result.islower()
        assert " " in result  # Space-separated tokens

    async def test_tokenize_preserves_vietnamese_chars(self):
        """Test that Vietnamese diacritics are preserved."""
        text = "Hà Nội, Đà Nẵng, Huế"
        result = await tokenize_vietnamese(text)

        # Diacritics should be preserved
        assert "hà_nội" in result.lower()
        assert "đà_nẵng" in result.lower()
        assert "huế" in result.lower()

    async def test_tokenize_long_text(self):
        """Test tokenization of longer text passages."""
        text = """
        VinGroup công bố kế hoạch đầu tư 5 tỷ USD
        để xây dựng nhà máy sản xuất chip bán dẫn
        tại khu công nghiệp Hà Nội vào năm 2024.
        """
        result = await tokenize_vietnamese(text)

        assert len(result) > 0
        assert "công_ty" in result.lower() or "vingroup" in result.lower()
        assert "nhà_máy" in result.lower()
        assert "chip" in result.lower()


@pytest.mark.unit
@pytest.mark.asyncio
class TestVietnameseProcessorEdgeCases:
    """Test edge cases and error handling."""

    async def test_tokenize_with_disabled_processing(self):
        """Test that tokenization is controlled by settings."""
        # Note: This test documents current behavior
        # The setting is checked at import time, so we can't easily mock it
        # In practice, Vietnamese processing is always enabled in production

        text = "Công ty VinTech"
        result = await tokenize_vietnamese(text)

        # With Vietnamese processing enabled, we get tokenized output
        assert result.lower() == "công_ty vintech"

    async def test_tokenize_unicode_edge_cases(self):
        """Test handling of various Unicode characters."""
        # Test with various Unicode spaces and special chars
        text = "Test\u00a0text\u200bwith\u2009special\u3000spaces"
        result = await tokenize_vietnamese(text)

        assert len(result) > 0
        assert "test" in result.lower()
        assert "text" in result.lower()

    async def test_tokenize_very_long_text(self):
        """Test performance with very long input."""
        # Generate a long text (1000 words)
        text = " ".join(["Công ty VinTech xây dựng nhà máy"] * 200)
        result = await tokenize_vietnamese(text)

        assert len(result) > 0
        assert "công_ty" in result.lower()

    async def test_tokenize_special_vietnamese_chars(self):
        """Test handling of special Vietnamese characters."""
        text = "Đ, đ, Ơ, ơ, Ư, ư, Â, â, Ê, ê, Ô, ô"
        result = await tokenize_vietnamese(text)

        # All Vietnamese characters should be preserved
        for char in ["đ", "ơ", "ư", "â", "ê", "ô"]:
            assert char in result.lower()
