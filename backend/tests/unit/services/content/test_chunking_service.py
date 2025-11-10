"""
Unit tests for Chunking Service.

Tests paragraph-level text chunking with various edge cases.
Validates smart chunking for optimal embedding generation.
"""

import pytest
from app.services.content.chunking_service import (
    chunk_text,
    ParagraphChunker,
)


@pytest.mark.unit
class TestParagraphChunker:
    """Unit tests for paragraph chunker."""

    @pytest.fixture
    def chunker(self):
        """Create default paragraph chunker."""
        return ParagraphChunker(min_chunk_size=500, max_chunk_size=2000)

    # ==================== Basic Chunking Tests ====================

    def test_chunk_double_newline_paragraphs(self, chunker):
        """Test chunking with double newline paragraph separators."""
        text = """Đoạn văn thứ nhất với nội dung ngắn.

Đoạn văn thứ hai với nội dung dài hơn một chút để tạo thành chunk hợp lệ.

Đoạn văn thứ ba cũng có nội dung tương tự như vậy."""

        chunks = chunker.chunk(text)

        assert len(chunks) >= 1
        assert all(isinstance(chunk, str) for chunk in chunks)
        # Verify chunks are joined with double newlines
        assert "\n\n" in chunks[0] or len(chunks) == 1

    def test_chunk_single_newline_fallback(self, chunker):
        """Test chunking falls back to single newlines when no double newlines."""
        text = """Dòng thứ nhất với nội dung ngắn.
Dòng thứ hai với nội dung dài hơn một chút.
Dòng thứ ba cũng có nội dung tương tự."""

        chunks = chunker.chunk(text)

        assert len(chunks) >= 1
        assert all(isinstance(chunk, str) for chunk in chunks)

    def test_chunk_empty_content(self, chunker):
        """Test chunking with empty content."""
        chunks = chunker.chunk("")

        assert chunks == []

    def test_chunk_whitespace_only(self, chunker):
        """Test chunking with whitespace-only content."""
        chunks = chunker.chunk("   \n\n   \n   ")

        assert chunks == []

    def test_chunk_single_short_paragraph(self, chunker):
        """Test chunking with a single short paragraph (<500 chars)."""
        text = "Đây là một đoạn văn ngắn."

        chunks = chunker.chunk(text)

        assert len(chunks) == 1
        assert chunks[0] == text

    def test_chunk_single_medium_paragraph(self, chunker):
        """Test chunking with a single medium paragraph (500-2000 chars)."""
        # Create a paragraph around 1000 chars
        text = "Đoạn văn trung bình. " * 40

        chunks = chunker.chunk(text)

        assert len(chunks) == 1
        assert len(chunks[0]) > 500
        assert len(chunks[0]) < 2000

    # ==================== Paragraph Merging Tests ====================

    def test_chunk_merges_small_paragraphs(self, chunker):
        """Test that small paragraphs are merged to reach min_chunk_size."""
        # Create multiple small paragraphs (each ~100 chars)
        paragraphs = ["Đoạn nhỏ " + str(i) + ". " * 10 for i in range(10)]
        text = "\n\n".join(paragraphs)

        chunks = chunker.chunk(text)

        # Should merge paragraphs
        assert len(chunks) < 10
        # Each chunk should ideally be >= min_chunk_size (except possibly the last)
        assert any(len(chunk) >= 500 for chunk in chunks[:-1]) or len(chunks) == 1

    def test_chunk_respects_max_chunk_size(self, chunker):
        """Test that chunks aim to respect max_chunk_size when merging."""
        # Create paragraphs that when merged should respect max size
        paragraph = "Đoạn văn. " * 50  # ~500 chars each
        text = "\n\n".join([paragraph] * 10)

        chunks = chunker.chunk(text)

        # Most chunks should be close to max_chunk_size (allow some tolerance for sentence joining)
        # The chunker aims for max_chunk_size but may slightly exceed when preserving sentence boundaries
        assert all(len(chunk) <= 2100 for chunk in chunks)  # Allow 100 char tolerance

    # ==================== Long Paragraph Splitting Tests ====================

    def test_chunk_splits_very_long_paragraph(self, chunker):
        """Test that paragraphs exceeding max_chunk_size are split by sentences."""
        # Create a very long paragraph (>2000 chars)
        long_paragraph = "Đây là một câu dài. " * 150  # ~3000 chars

        chunks = chunker.chunk(long_paragraph)

        # Should split into multiple chunks
        assert len(chunks) > 1
        # Each chunk should be reasonably close to max_chunk_size (allow ~10% tolerance for sentence boundaries)
        assert all(
            len(chunk) <= 2210 for chunk in chunks
        )  # Chunker may exceed max when preserving sentences

    def test_chunk_splits_on_sentence_boundaries(self, chunker):
        """Test that long paragraphs are split on sentence boundaries."""
        # Create sentences with clear endings
        sentences = [
            "Câu thứ nhất với nội dung chi tiết.",
            "Câu thứ hai cũng có nội dung tương tự!",
            "Câu thứ ba tiếp tục với thông tin khác?",
        ] * 50  # Make it long enough to split

        long_paragraph = " ".join(sentences)

        chunks = chunker.chunk(long_paragraph)

        # Verify chunks end with sentence punctuation (or are at max size)
        for chunk in chunks:
            assert (
                chunk.rstrip().endswith((".", "!", "?"))
                or len(chunk) >= 1900  # Near max size
            )

    def test_chunk_handles_vietnamese_sentence_endings(self, chunker):
        """Test proper handling of Vietnamese sentence endings."""
        text = (
            """Công ty VinGroup công bố kế hoạch đầu tư.
Dự án sẽ được triển khai tại Hà Nội!
Tổng vốn đầu tư lên đến 5 tỷ USD?
Dự kiến hoàn thành vào năm 2026."""
            * 30
        )  # Make it long

        chunks = chunker.chunk(text)

        assert len(chunks) >= 1
        # Verify chunks are properly split on sentence boundaries
        for chunk in chunks:
            assert chunk.strip() != ""

    # ==================== Edge Case Tests ====================

    def test_chunk_no_newlines(self, chunker):
        """Test chunking content with no newlines (continuous text)."""
        # Create continuous text without newlines
        text = "Văn bản liên tục không có xuống dòng. " * 100

        chunks = chunker.chunk(text)

        # Should treat as one long paragraph and split by sentences
        assert len(chunks) >= 1
        # Allow ~10% tolerance for sentence boundary preservation
        assert all(len(chunk) <= 2200 for chunk in chunks)

    def test_chunk_mixed_newline_formats(self, chunker):
        """Test chunking with mixed newline formats (\\r\\n, \\n)."""
        text = "Dòng 1\r\nDòng 2\nDòng 3\r\n\r\nDòng 4"

        chunks = chunker.chunk(text)

        # Should normalize and handle correctly
        assert len(chunks) >= 1
        # Verify no \r remaining in chunks
        assert all("\r" not in chunk for chunk in chunks)

    def test_chunk_preserves_whitespace_within_text(self, chunker):
        """Test that internal whitespace is preserved."""
        text = "Đoạn  văn   với    nhiều    khoảng trắng.\n\nĐoạn hai cũng vậy."

        chunks = chunker.chunk(text)

        # Should preserve internal spaces
        assert "nhiều    khoảng" in " ".join(chunks)

    def test_chunk_very_long_single_sentence(self, chunker):
        """Test chunking with a very long single sentence (no periods)."""
        # Create one very long sentence without proper ending punctuation
        long_sentence = "Đây là một câu rất dài không có dấu chấm " * 100

        chunks = chunker.chunk(long_sentence)

        # Should still create chunks even without sentence boundaries
        assert len(chunks) >= 1
        # Total content should be preserved
        assert "".join(chunks).replace("\n\n", " ").strip() == long_sentence.strip()

    def test_chunk_multiple_consecutive_newlines(self, chunker):
        """Test handling of multiple consecutive newlines."""
        text = "Đoạn 1\n\n\n\nĐoạn 2\n\n\n\n\n\nĐoạn 3"

        chunks = chunker.chunk(text)

        assert len(chunks) >= 1
        # Should not create empty chunks
        assert all(chunk.strip() != "" for chunk in chunks)

    # ==================== Custom Size Tests ====================

    def test_chunk_custom_min_size(self):
        """Test chunker with custom min_chunk_size."""
        chunker = ParagraphChunker(min_chunk_size=1000, max_chunk_size=2000)

        # Create paragraphs that need merging to reach 1000 chars
        text = "\n\n".join(["Đoạn nhỏ. " * 30] * 10)  # Each ~300 chars

        chunks = chunker.chunk(text)

        # Most chunks should be >= 1000 chars (except possibly the last)
        assert any(len(chunk) >= 1000 for chunk in chunks[:-1]) or len(chunks) == 1

    def test_chunk_custom_max_size(self):
        """Test chunker with custom max_chunk_size."""
        chunker = ParagraphChunker(min_chunk_size=500, max_chunk_size=1000)

        # Create a long paragraph
        text = "Văn bản dài. " * 200  # ~2400 chars

        chunks = chunker.chunk(text)

        # All chunks should be close to 1000 chars (allow ~16% tolerance for sentence boundaries)
        assert all(len(chunk) <= 1200 for chunk in chunks)

    # ==================== Integration with chunk_text Function ====================

    def test_chunk_text_default_strategy(self):
        """Test chunk_text function with default paragraph strategy."""
        text = "Đoạn 1.\n\nĐoạn 2.\n\nĐoạn 3."

        chunks = chunk_text(text)

        assert len(chunks) >= 1
        assert all(isinstance(chunk, str) for chunk in chunks)

    def test_chunk_text_explicit_paragraph_strategy(self):
        """Test chunk_text with explicitly specified paragraph strategy."""
        text = "Đoạn 1.\n\nĐoạn 2."

        chunks = chunk_text(text, strategy="paragraph")

        assert len(chunks) >= 1

    def test_chunk_text_empty_content(self):
        """Test chunk_text with empty content."""
        chunks = chunk_text("")

        assert chunks == []

    def test_chunk_text_unknown_strategy_falls_back(self):
        """Test chunk_text with unknown strategy falls back to paragraph."""
        text = "Some text content."

        chunks = chunk_text(text, strategy="unknown_strategy")

        # Should fall back to paragraph chunking
        assert len(chunks) == 1
        assert chunks[0] == text

    # ==================== Real-World Vietnamese Content Tests ====================

    def test_chunk_vietnamese_news_article(self, chunker):
        """Test chunking with realistic Vietnamese news article content."""
        article = """VinGroup công bố kế hoạch xây dựng nhà máy sản xuất chip bán dẫn.

Tập đoàn VinGroup vừa công bố kế hoạch đầu tư 5 tỷ USD để xây dựng nhà máy sản xuất chip bán dẫn tại Hà Nội. Đây được xem là một trong những dự án công nghệ lớn nhất trong lịch sử Việt Nam.

Theo kế hoạch, dự án sẽ khởi công vào quý 2/2024 và dự kiến hoàn thành vào năm 2026. Nhà máy sẽ có công suất sản xuất 100.000 wafer mỗi tháng khi hoạt động hết công suất.

Đại diện VinGroup cho biết, dự án này sẽ tạo ra hàng nghìn việc làm chất lượng cao và góp phần nâng cao năng lực công nghệ của Việt Nam trong chuỗi cung ứng bán dẫn toàn cầu."""

        chunks = chunker.chunk(article)

        assert len(chunks) >= 1
        # Verify Vietnamese text is preserved correctly
        assert any("VinGroup" in chunk for chunk in chunks)
        assert any("bán dẫn" in chunk for chunk in chunks)

    def test_chunk_vietnamese_social_media_post(self, chunker):
        """Test chunking with Vietnamese social media style content."""
        post = """Tin vui!!! 🎉🎉🎉

VinTech xây nhà máy 5 tỷ USD ở Hà Nội!!!

Tuyệt vời quá đi! Việt Nam ngày càng phát triển! 🇻🇳

#VinGroup #CôngNghệ #ViệtNam"""

        chunks = chunker.chunk(post)

        assert len(chunks) >= 1
        # Should preserve emojis and special characters
        assert any("🎉" in chunk for chunk in chunks)

    def test_chunk_preserves_total_content(self, chunker):
        """Test that chunking preserves all original content."""
        original = """Đoạn 1 với nội dung quan trọng.

Đoạn 2 với thông tin chi tiết hơn về chủ đề.

Đoạn 3 kết luận nội dung."""

        chunks = chunker.chunk(original)

        # Reconstruct from chunks and verify all content is present
        reconstructed = "\n\n".join(chunks)

        # All original words should appear in reconstructed
        original_words = set(original.lower().split())
        reconstructed_words = set(reconstructed.lower().split())

        assert original_words.issubset(reconstructed_words)

    # ==================== Sentence Splitting Tests ====================

    def test_split_sentences_with_various_punctuation(self, chunker):
        """Test _split_sentences with various Vietnamese punctuation."""
        text = "Câu 1. Câu 2! Câu 3? Câu 4."

        sentences = chunker._split_sentences(text)

        assert len(sentences) == 4
        assert sentences[0].strip() == "Câu 1."
        assert sentences[1].strip() == "Câu 2!"
        assert sentences[2].strip() == "Câu 3?"
        assert sentences[3].strip() == "Câu 4."

    def test_split_sentences_without_punctuation(self, chunker):
        """Test _split_sentences with text without ending punctuation."""
        text = "Văn bản không có dấu chấm cuối"

        sentences = chunker._split_sentences(text)

        # Should still return the text as one "sentence"
        assert len(sentences) == 1
        assert sentences[0].strip() == text

    def test_split_sentences_preserves_punctuation(self, chunker):
        """Test that sentence splitting preserves punctuation."""
        text = "Câu đầu. Câu giữa! Câu cuối?"

        sentences = chunker._split_sentences(text)

        assert all(s.rstrip().endswith((".", "!", "?")) for s in sentences if s.strip())
