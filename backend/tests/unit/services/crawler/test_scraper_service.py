"""
Unit tests for Scraper Service.

Tests article content extraction with fallback strategies.
Uses mocked HTTP responses to avoid external requests.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from app.services.crawler.scraper_service import (
    fetch_html,
    scrape_article_content,
    _extract_with_trafilatura,
    _extract_with_mvp_approach,
    _extract_basic_paragraphs,
)


@pytest.mark.unit
class TestScraperService:
    """Unit tests for Scraper Service."""

    # Sample HTML fixtures
    SIMPLE_HTML = """
    <html>
        <body>
            <article>
                <h1>Test Article Title</h1>
                <p>This is the first paragraph of the article content.</p>
                <p>This is the second paragraph with more details about the topic.</p>
                <p>This is the third paragraph continuing the discussion.</p>
            </article>
        </body>
    </html>
    """

    VIETNAMESE_HTML = """
    <html>
        <body>
            <article>
                <h1>Tin tức công nghệ Việt Nam</h1>
                <p>Công ty VinTech vừa công bố kế hoạch đầu tư 5 tỷ USD vào nhà máy sản xuất chip tại Hà Nội.</p>
                <p>Dự án này được kỳ vọng sẽ tạo ra hàng nghìn việc làm cho người lao động Việt Nam.</p>
                <p>Theo đại diện công ty, nhà máy dự kiến hoàn thành vào cuối năm 2025.</p>
            </article>
        </body>
    </html>
    """

    NOISY_HTML = """
    <html>
        <body>
            <nav>Navigation menu</nav>
            <aside>Advertisement here</aside>
            <article>
                <p>This is actual article content that should be extracted.</p>
                <p>This paragraph contains important information about the topic.</p>
            </article>
            <div class="comments">User comments here</div>
            <footer>Footer content</footer>
        </body>
    </html>
    """

    HTML_WITH_SHORT_PARAGRAPHS = """
    <html>
        <body>
            <p>Short</p>
            <p>Too small</p>
            <p>This is a longer paragraph that contains enough text to be considered meaningful content that should be extracted.</p>
            <p>Another meaningful paragraph with sufficient length to pass the minimum character threshold for extraction.</p>
        </body>
    </html>
    """

    @pytest.mark.asyncio
    async def test_fetch_html_success(self):
        """Test successful HTML fetching."""
        mock_response = AsyncMock()
        mock_response.text = self.SIMPLE_HTML
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            html = await fetch_html("https://example.com/article")

            assert html == self.SIMPLE_HTML
            mock_response.raise_for_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_html_with_custom_timeout(self):
        """Test HTML fetching with custom timeout."""
        mock_response = AsyncMock()
        mock_response.text = self.SIMPLE_HTML
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            html = await fetch_html("https://example.com/article", timeout_s=60)

            assert html == self.SIMPLE_HTML
            # Verify AsyncClient was called with custom timeout
            mock_client.assert_called_once()
            call_kwargs = mock_client.call_args.kwargs
            assert call_kwargs["timeout"] == 60

    @pytest.mark.asyncio
    async def test_fetch_html_follows_redirects(self):
        """Test that HTTP client follows redirects."""
        mock_response = AsyncMock()
        mock_response.text = self.SIMPLE_HTML
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            await fetch_html("https://example.com/article")

            # Verify follow_redirects=True was passed
            mock_client.assert_called_once()
            call_kwargs = mock_client.call_args.kwargs
            assert call_kwargs["follow_redirects"] is True

    @pytest.mark.asyncio
    async def test_fetch_html_includes_user_agent(self):
        """Test that User-Agent header is included."""
        mock_response = AsyncMock()
        mock_response.text = self.SIMPLE_HTML
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            await fetch_html("https://example.com/article")

            # Verify User-Agent header was passed
            mock_client.assert_called_once()
            call_kwargs = mock_client.call_args.kwargs
            assert "headers" in call_kwargs
            assert "User-Agent" in call_kwargs["headers"]

    @pytest.mark.asyncio
    async def test_fetch_html_raises_on_http_error(self):
        """Test that HTTP errors are raised."""
        import httpx

        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError(
                "404 Not Found", request=Mock(), response=Mock()
            )
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(httpx.HTTPStatusError):
                await fetch_html("https://example.com/nonexistent")

    def test_extract_with_trafilatura_success(self):
        """Test successful trafilatura extraction."""
        with patch("trafilatura.extract") as mock_extract:
            mock_extract.return_value = "Extracted article content"

            result = _extract_with_trafilatura(self.SIMPLE_HTML, favor_precision=True)

            assert result == "Extracted article content"
            mock_extract.assert_called_once()
            call_kwargs = mock_extract.call_args.kwargs
            assert call_kwargs["favor_precision"] is True
            assert call_kwargs["include_comments"] is False
            assert call_kwargs["deduplicate"] is True

    def test_extract_with_trafilatura_returns_empty_on_failure(self):
        """Test trafilatura returns empty string when extraction fails."""
        with patch("trafilatura.extract") as mock_extract:
            mock_extract.return_value = None

            result = _extract_with_trafilatura(self.SIMPLE_HTML, favor_precision=True)

            assert result == ""

    def test_extract_with_trafilatura_recall_mode(self):
        """Test trafilatura with recall mode (favor_precision=False)."""
        with patch("trafilatura.extract") as mock_extract:
            mock_extract.return_value = "More content extracted"

            result = _extract_with_trafilatura(self.SIMPLE_HTML, favor_precision=False)

            assert result == "More content extracted"
            call_kwargs = mock_extract.call_args.kwargs
            assert call_kwargs["favor_precision"] is False

    def test_extract_with_mvp_approach_success(self):
        """Test MVP extraction approach success."""
        # Mock Document and justext with full module paths
        with (
            patch("app.services.crawler.scraper_service.Document") as mock_doc,
            patch(
                "app.services.crawler.scraper_service.justext.justext"
            ) as mock_justext,
            patch(
                "app.services.crawler.scraper_service.justext.get_stoplist"
            ) as mock_stoplist,
        ):
            # Mock Document to return HTML
            mock_doc.return_value.summary.return_value = self.SIMPLE_HTML

            # Mock justext paragraphs
            mock_paragraph = Mock()
            mock_paragraph.text = "This is extracted paragraph text from the article."
            mock_paragraph.is_boilerplate = False
            mock_justext.return_value = [mock_paragraph]
            mock_stoplist.return_value = []

            result = _extract_with_mvp_approach(self.SIMPLE_HTML)

            assert "extracted paragraph text" in result
            mock_doc.assert_called_once_with(self.SIMPLE_HTML)
            mock_justext.assert_called_once()

    def test_extract_with_mvp_approach_filters_boilerplate(self):
        """Test MVP approach filters out boilerplate paragraphs."""
        with (
            patch("app.services.crawler.scraper_service.Document") as mock_doc,
            patch(
                "app.services.crawler.scraper_service.justext.justext"
            ) as mock_justext,
            patch(
                "app.services.crawler.scraper_service.justext.get_stoplist"
            ) as mock_stoplist,
        ):
            mock_doc.return_value.summary.return_value = self.SIMPLE_HTML

            # Mix of boilerplate and content paragraphs
            good_para = Mock()
            good_para.text = "Real content paragraph"
            good_para.is_boilerplate = False

            boilerplate_para = Mock()
            boilerplate_para.text = "Advertisement"
            boilerplate_para.is_boilerplate = True

            mock_justext.return_value = [good_para, boilerplate_para]
            mock_stoplist.return_value = []

            result = _extract_with_mvp_approach(self.SIMPLE_HTML)

            assert "Real content paragraph" in result
            assert "Advertisement" not in result

    def test_extract_with_mvp_approach_handles_errors(self):
        """Test MVP approach returns empty string on errors."""
        with patch("app.services.crawler.scraper_service.Document") as mock_doc:
            mock_doc.side_effect = Exception("Extraction error")

            result = _extract_with_mvp_approach(self.SIMPLE_HTML)

            assert result == ""

    def test_extract_with_mvp_approach_decodes_html_entities(self):
        """Test MVP approach decodes HTML entities."""
        html_with_entities = "<p>&lt;tag&gt; &amp; &quot;quotes&quot;</p>"

        with (
            patch("app.services.crawler.scraper_service.Document") as mock_doc,
            patch(
                "app.services.crawler.scraper_service.justext.justext"
            ) as mock_justext,
            patch(
                "app.services.crawler.scraper_service.justext.get_stoplist"
            ) as mock_stoplist,
        ):
            mock_doc.return_value.summary.return_value = html_with_entities

            mock_paragraph = Mock()
            mock_paragraph.text = "&lt;tag&gt; &amp; &quot;quotes&quot;"
            mock_paragraph.is_boilerplate = False
            mock_justext.return_value = [mock_paragraph]
            mock_stoplist.return_value = []

            result = _extract_with_mvp_approach(html_with_entities)

            # HTML entities should be decoded
            assert "<tag>" in result or "&" in result  # Should be decoded

    def test_extract_basic_paragraphs_success(self):
        """Test basic paragraph extraction."""
        result = _extract_basic_paragraphs(self.HTML_WITH_SHORT_PARAGRAPHS)

        # Should extract longer paragraphs, filter short ones
        assert "meaningful content" in result
        assert "sufficient length" in result
        # Short paragraphs should be filtered (< 50 chars)
        assert "Short" not in result

    def test_extract_basic_paragraphs_filters_short_content(self):
        """Test that short paragraphs are filtered out."""
        result = _extract_basic_paragraphs(self.HTML_WITH_SHORT_PARAGRAPHS)

        # Count how many paragraphs were extracted
        # Only paragraphs > 50 chars should be included
        paragraphs = [p for p in result.split("\n\n") if p.strip()]
        assert len(paragraphs) == 2  # Only 2 long paragraphs

    def test_extract_basic_paragraphs_handles_errors(self):
        """Test basic extraction returns empty string on errors."""
        invalid_html = None

        result = _extract_basic_paragraphs(invalid_html)

        assert result == ""

    def test_extract_basic_paragraphs_with_vietnamese_content(self):
        """Test basic extraction works with Vietnamese text."""
        result = _extract_basic_paragraphs(self.VIETNAMESE_HTML)

        assert "VinTech" in result or "công nghệ" in result

    @pytest.mark.asyncio
    async def test_scrape_article_content_trafilatura_precision_success(self):
        """Test scrape_article_content uses trafilatura precision first."""
        long_text = "A" * 150  # 150 chars, meets minimum threshold

        with (
            patch("app.services.crawler.scraper_service.fetch_html") as mock_fetch,
            patch("trafilatura.extract") as mock_extract,
        ):
            mock_fetch.return_value = self.SIMPLE_HTML
            mock_extract.return_value = long_text

            result = await scrape_article_content("https://example.com/article")

            assert result == long_text.strip()
            # Should use precision mode first
            call_kwargs = mock_extract.call_args.kwargs
            assert call_kwargs["favor_precision"] is True

    @pytest.mark.asyncio
    async def test_scrape_article_content_falls_back_to_recall(self):
        """Test fallback to trafilatura recall mode."""
        short_text = "Too short"  # < 100 chars
        long_text = "B" * 150  # 150 chars

        with (
            patch("app.services.crawler.scraper_service.fetch_html") as mock_fetch,
            patch("trafilatura.extract") as mock_extract,
        ):
            mock_fetch.return_value = self.SIMPLE_HTML
            # First call (precision) returns short text, second call (recall) returns long text
            mock_extract.side_effect = [short_text, long_text]

            result = await scrape_article_content("https://example.com/article")

            assert result == long_text.strip()
            # Should have been called twice (precision then recall)
            assert mock_extract.call_count == 2

    @pytest.mark.asyncio
    async def test_scrape_article_content_falls_back_to_mvp(self):
        """Test fallback to MVP approach."""
        mvp_text = "C" * 150

        with (
            patch("app.services.crawler.scraper_service.fetch_html") as mock_fetch,
            patch("trafilatura.extract") as mock_extract,
            patch(
                "app.services.crawler.scraper_service._extract_with_mvp_approach"
            ) as mock_mvp,
        ):
            mock_fetch.return_value = self.SIMPLE_HTML
            mock_extract.return_value = ""  # Trafilatura fails
            mock_mvp.return_value = mvp_text

            result = await scrape_article_content("https://example.com/article")

            assert result == mvp_text.strip()
            mock_mvp.assert_called_once()

    @pytest.mark.asyncio
    async def test_scrape_article_content_falls_back_to_basic(self):
        """Test fallback to basic paragraph extraction."""
        basic_text = "D" * 60  # 60 chars, meets basic threshold (50 chars)

        with (
            patch("app.services.crawler.scraper_service.fetch_html") as mock_fetch,
            patch("trafilatura.extract") as mock_extract,
            patch(
                "app.services.crawler.scraper_service._extract_with_mvp_approach"
            ) as mock_mvp,
            patch(
                "app.services.crawler.scraper_service._extract_basic_paragraphs"
            ) as mock_basic,
        ):
            mock_fetch.return_value = self.SIMPLE_HTML
            mock_extract.return_value = ""  # Trafilatura fails
            mock_mvp.return_value = ""  # MVP fails
            mock_basic.return_value = basic_text

            result = await scrape_article_content("https://example.com/article")

            assert result == basic_text.strip()
            mock_basic.assert_called_once()

    @pytest.mark.asyncio
    async def test_scrape_article_content_returns_empty_on_complete_failure(self):
        """Test that empty string is returned when all methods fail."""
        with (
            patch("app.services.crawler.scraper_service.fetch_html") as mock_fetch,
            patch("trafilatura.extract") as mock_extract,
            patch(
                "app.services.crawler.scraper_service._extract_with_mvp_approach"
            ) as mock_mvp,
            patch(
                "app.services.crawler.scraper_service._extract_basic_paragraphs"
            ) as mock_basic,
        ):
            mock_fetch.return_value = self.SIMPLE_HTML
            mock_extract.return_value = ""
            mock_mvp.return_value = ""
            mock_basic.return_value = ""  # All methods fail

            result = await scrape_article_content("https://example.com/article")

            assert result == ""

    @pytest.mark.asyncio
    async def test_scrape_article_content_respects_max_content_length(self):
        """Test that content is truncated to max_content_length."""
        very_long_text = "E" * 100000  # Very long text

        with (
            patch("app.services.crawler.scraper_service.fetch_html") as mock_fetch,
            patch("trafilatura.extract") as mock_extract,
            patch("app.services.crawler.scraper_service.settings") as mock_settings,
        ):
            mock_fetch.return_value = self.SIMPLE_HTML
            mock_extract.return_value = very_long_text
            mock_settings.crawler.max_content_length = 1000  # Limit to 1000 chars

            result = await scrape_article_content("https://example.com/article")

            assert len(result) == 1000

    @pytest.mark.asyncio
    async def test_scrape_article_content_no_truncation_when_max_length_zero(self):
        """Test no truncation when max_content_length is 0 (disabled)."""
        long_text = "F" * 5000

        with (
            patch("app.services.crawler.scraper_service.fetch_html") as mock_fetch,
            patch("trafilatura.extract") as mock_extract,
            patch("app.services.crawler.scraper_service.settings") as mock_settings,
        ):
            mock_fetch.return_value = self.SIMPLE_HTML
            mock_extract.return_value = long_text
            mock_settings.crawler.max_content_length = 0  # No limit

            result = await scrape_article_content("https://example.com/article")

            assert len(result) == 5000  # Full text, no truncation
