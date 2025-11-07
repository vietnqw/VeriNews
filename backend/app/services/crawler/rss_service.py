"""
RSS Feed Fetcher

Fetch and parse RSS feeds into normalized article metadata entries.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, TypedDict
import html
import re
from email.utils import parsedate_to_datetime

import feedparser


class FeedEntry(TypedDict, total=False):
    title: str
    link: str
    published_at: datetime | None


def _normalize_gmt_tz(date_str: str) -> str:
    """Normalize non-standard GMT±H[:MM] offsets to RFC 2822 "+HHMM".

    Examples:
      "GMT+7" -> "+0700", "GMT+07" -> "+0700", "GMT+07:30" -> "+0730"
    """
    if not date_str:
        return date_str
    pattern = re.compile(r"GMT([+-])(\d{1,2})(?::?(\d{2}))?\b")

    def repl(m: re.Match[str]) -> str:
        sign = m.group(1)
        hours = int(m.group(2))
        minutes = m.group(3) or "00"
        return f"{sign}{hours:02d}{minutes}"

    return pattern.sub(lambda m: repl(m), date_str)


def _parse_published(entry: Any) -> datetime | None:
    """Best-effort parse published date from feed entry (returns UTC-aware)."""
    # Prefer structured time from feedparser
    try:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            dt = datetime(*entry.published_parsed[:6])
            # Treat naive as UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
    except Exception:
        pass

    # Fallback: parse free-form string, normalizing GMT offsets like "GMT+7"
    try:
        raw = getattr(entry, "published", None) or getattr(entry, "updated", None)
        if not raw:
            return None
        normalized = _normalize_gmt_tz(str(raw))
        dt = parsedate_to_datetime(normalized)
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
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
        # Decode HTML entities (e.g., &uacute; → ú, &aacute; → á)
        # Feedparser usually decodes these, but some feeds may have double-encoded
        # or improperly encoded entities that need explicit decoding
        title = html.unescape(title)
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
