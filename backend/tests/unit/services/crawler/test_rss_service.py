"""
Unit tests for RSS Service.

Tests RSS feed fetching and parsing functionality.
Uses mocked feedparser to avoid external HTTP requests.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from types import SimpleNamespace

from app.services.crawler.rss_service import (
    fetch_rss_feed,
    _normalize_gmt_tz,
    _parse_published,
    FeedEntry,
)


@pytest.mark.unit
class TestRSSService:
    """Unit tests for RSS Service."""

    def test_normalize_gmt_tz_gmt_plus_7(self):
        """Test normalizing 'GMT+7' to '+0700'."""
        result = _normalize_gmt_tz("Mon, 15 Jan 2024 10:30:00 GMT+7")
        assert "+0700" in result
        assert "GMT+7" not in result

    def test_normalize_gmt_tz_gmt_plus_07(self):
        """Test normalizing 'GMT+07' to '+0700'."""
        result = _normalize_gmt_tz("Mon, 15 Jan 2024 10:30:00 GMT+07")
        assert "+0700" in result

    def test_normalize_gmt_tz_gmt_plus_0730(self):
        """Test normalizing 'GMT+07:30' to '+0730'."""
        result = _normalize_gmt_tz("Mon, 15 Jan 2024 10:30:00 GMT+07:30")
        assert "+0730" in result

    def test_normalize_gmt_tz_gmt_minus_5(self):
        """Test normalizing 'GMT-5' to '-0500'."""
        result = _normalize_gmt_tz("Mon, 15 Jan 2024 10:30:00 GMT-5")
        assert "-0500" in result

    def test_normalize_gmt_tz_no_gmt(self):
        """Test that strings without GMT are unchanged."""
        original = "Mon, 15 Jan 2024 10:30:00 +0700"
        result = _normalize_gmt_tz(original)
        assert result == original

    def test_normalize_gmt_tz_empty_string(self):
        """Test normalizing empty string returns empty string."""
        result = _normalize_gmt_tz("")
        assert result == ""

    def test_parse_published_with_published_parsed(self):
        """Test parsing published date from feedparser's published_parsed."""
        entry = SimpleNamespace(published_parsed=(2024, 1, 15, 10, 30, 0, 0, 15, 0))

        result = _parse_published(entry)

        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30
        assert result.tzinfo == timezone.utc

    def test_parse_published_with_string_fallback(self):
        """Test parsing published date from string when published_parsed not available."""
        entry = SimpleNamespace(
            published="Mon, 15 Jan 2024 10:30:00 +0700",
            published_parsed=None,
        )

        result = _parse_published(entry)

        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        # Time adjusted to UTC (10:30 +0700 = 03:30 UTC)
        assert result.tzinfo == timezone.utc

    def test_parse_published_with_gmt_offset(self):
        """Test parsing published date with GMT+7 offset."""
        entry = SimpleNamespace(
            published="Mon, 15 Jan 2024 10:30:00 GMT+7",
            published_parsed=None,
        )

        result = _parse_published(entry)

        assert result is not None
        assert result.year == 2024
        assert result.tzinfo == timezone.utc

    def test_parse_published_with_updated_fallback(self):
        """Test falling back to 'updated' field when 'published' not available."""
        entry = SimpleNamespace(
            published=None,
            updated="Mon, 15 Jan 2024 10:30:00 +0000",
            published_parsed=None,
        )

        result = _parse_published(entry)

        assert result is not None
        assert result.year == 2024

    def test_parse_published_returns_none_when_no_date(self):
        """Test that None is returned when no date fields are available."""
        entry = SimpleNamespace(
            published=None,
            updated=None,
            published_parsed=None,
        )

        result = _parse_published(entry)

        assert result is None

    def test_parse_published_handles_invalid_date_string(self):
        """Test that invalid date strings return None."""
        entry = SimpleNamespace(
            published="not a valid date",
            published_parsed=None,
        )

        result = _parse_published(entry)

        assert result is None

    @patch("app.services.crawler.rss_service.feedparser.parse")
    def test_fetch_rss_feed_basic(self, mock_parse):
        """Test basic RSS feed fetching and parsing."""
        # Mock feedparser response
        mock_parse.return_value = Mock(
            entries=[
                Mock(
                    title="Article 1",
                    link="https://example.com/article1",
                    published_parsed=(2024, 1, 15, 10, 0, 0, 0, 15, 0),
                ),
                Mock(
                    title="Article 2",
                    link="https://example.com/article2",
                    published_parsed=(2024, 1, 15, 11, 0, 0, 0, 15, 0),
                ),
            ]
        )

        entries = fetch_rss_feed("https://example.com/rss")

        assert len(entries) == 2
        assert entries[0]["title"] == "Article 1"
        assert entries[0]["link"] == "https://example.com/article1"
        assert entries[0]["published_at"] is not None
        assert entries[1]["title"] == "Article 2"

    @patch("app.services.crawler.rss_service.feedparser.parse")
    def test_fetch_rss_feed_decodes_html_entities(self, mock_parse):
        """Test that HTML entities in titles are decoded."""
        mock_parse.return_value = Mock(
            entries=[
                Mock(
                    title="Article &amp; News &quot;Today&quot;",
                    link="https://example.com/article1",
                    published_parsed=(2024, 1, 15, 10, 0, 0, 0, 15, 0),
                ),
            ]
        )

        entries = fetch_rss_feed("https://example.com/rss")

        # HTML entities should be decoded
        assert entries[0]["title"] == 'Article & News "Today"'

    @patch("app.services.crawler.rss_service.feedparser.parse")
    def test_fetch_rss_feed_skips_entries_without_link(self, mock_parse):
        """Test that entries without links are skipped."""
        # Create mock entry without link attribute using spec
        entry_no_link = Mock(spec=["title", "published_parsed"])
        entry_no_link.title = "Article without link attribute"
        entry_no_link.published_parsed = (2024, 1, 15, 12, 0, 0, 0, 15, 0)

        mock_parse.return_value = Mock(
            entries=[
                Mock(
                    title="Article with link",
                    link="https://example.com/article1",
                    published_parsed=(2024, 1, 15, 10, 0, 0, 0, 15, 0),
                ),
                Mock(
                    title="Article with empty link",
                    link="",
                    published_parsed=(2024, 1, 15, 11, 0, 0, 0, 15, 0),
                ),
                entry_no_link,
            ]
        )

        entries = fetch_rss_feed("https://example.com/rss")

        # Only the first entry with a valid link should be included
        assert len(entries) == 1
        assert entries[0]["title"] == "Article with link"

    @patch("app.services.crawler.rss_service.feedparser.parse")
    def test_fetch_rss_feed_uses_link_as_title_fallback(self, mock_parse):
        """Test that link is used as title if title is empty."""
        mock_parse.return_value = Mock(
            entries=[
                Mock(
                    title="",
                    link="https://example.com/article1",
                    published_parsed=(2024, 1, 15, 10, 0, 0, 0, 15, 0),
                ),
            ]
        )

        entries = fetch_rss_feed("https://example.com/rss")

        # Link should be used as title
        assert entries[0]["title"] == "https://example.com/article1"

    @patch("app.services.crawler.rss_service.feedparser.parse")
    def test_fetch_rss_feed_strips_whitespace(self, mock_parse):
        """Test that whitespace is stripped from titles and links."""
        mock_parse.return_value = Mock(
            entries=[
                Mock(
                    title="  Article with spaces  ",
                    link="  https://example.com/article1  ",
                    published_parsed=(2024, 1, 15, 10, 0, 0, 0, 15, 0),
                ),
            ]
        )

        entries = fetch_rss_feed("https://example.com/rss")

        assert entries[0]["title"] == "Article with spaces"
        assert entries[0]["link"] == "https://example.com/article1"

    @patch("app.services.crawler.rss_service.feedparser.parse")
    def test_fetch_rss_feed_empty_feed(self, mock_parse):
        """Test fetching empty RSS feed returns empty list."""
        mock_parse.return_value = Mock(entries=[])

        entries = fetch_rss_feed("https://example.com/rss")

        assert entries == []

    @patch("app.services.crawler.rss_service.feedparser.parse")
    def test_fetch_rss_feed_with_vietnamese_content(self, mock_parse):
        """Test fetching RSS feed with Vietnamese characters."""
        mock_parse.return_value = Mock(
            entries=[
                Mock(
                    title="Tin tức mới nhất về công nghệ",
                    link="https://vnexpress.net/article1",
                    published_parsed=(2024, 1, 15, 10, 0, 0, 0, 15, 0),
                ),
            ]
        )

        entries = fetch_rss_feed("https://vnexpress.net/rss")

        assert entries[0]["title"] == "Tin tức mới nhất về công nghệ"
        assert "vnexpress.net" in entries[0]["link"]

    @patch("app.services.crawler.rss_service.feedparser.parse")
    def test_fetch_rss_feed_published_at_can_be_none(self, mock_parse):
        """Test that published_at can be None if parsing fails."""
        mock_parse.return_value = Mock(
            entries=[
                Mock(
                    title="Article without date",
                    link="https://example.com/article1",
                    published=None,
                    updated=None,
                    published_parsed=None,
                ),
            ]
        )

        entries = fetch_rss_feed("https://example.com/rss")

        assert len(entries) == 1
        assert entries[0]["published_at"] is None

    @patch("app.services.crawler.rss_service.feedparser.parse")
    def test_fetch_rss_feed_handles_multiple_html_entities(self, mock_parse):
        """Test handling multiple HTML entities in title."""
        mock_parse.return_value = Mock(
            entries=[
                Mock(
                    title="&lt;Breaking&gt; News &amp; Updates &quot;Today&quot;",
                    link="https://example.com/article1",
                    published_parsed=(2024, 1, 15, 10, 0, 0, 0, 15, 0),
                ),
            ]
        )

        entries = fetch_rss_feed("https://example.com/rss")

        assert entries[0]["title"] == '<Breaking> News & Updates "Today"'

    def test_feed_entry_type_structure(self):
        """Test that FeedEntry TypedDict has correct structure."""
        # This is more of a type check, ensuring the structure is correct
        entry: FeedEntry = {
            "title": "Test",
            "link": "https://example.com",
            "published_at": datetime.now(timezone.utc),
        }

        assert "title" in entry
        assert "link" in entry
        assert "published_at" in entry
