"""
RSS Feed Fetcher

Fetch and parse RSS feeds into normalized article metadata entries.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, TypedDict

import feedparser


class FeedEntry(TypedDict, total=False):
    title: str
    link: str
    published_at: datetime | None


def _parse_published(entry: Any) -> datetime | None:
    """Best-effort parse published date from feed entry."""
    # feedparser normalizes to 'published_parsed' when available
    try:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            # time.struct_time → datetime (naive)
            return datetime(*entry.published_parsed[:6])
    except Exception:
        return None
    return None


def fetch_rss_feed(feed_url: str) -> List[FeedEntry]:
    """
    Fetch and parse RSS/Atom feed.

    Args:
        feed_url: URL of the RSS/Atom feed

    Returns:
        List of normalized entries with title, link, and published_at
    """
    parsed = feedparser.parse(feed_url)
    entries: List[FeedEntry] = []
    for e in parsed.entries:
        title = getattr(e, "title", "").strip()
        link = getattr(e, "link", "").strip()
        if not link:
            continue
        entries.append(
            FeedEntry(
                title=title or link,
                link=link,
                published_at=_parse_published(e),
            )
        )
    return entries
