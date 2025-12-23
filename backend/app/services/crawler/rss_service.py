"""
RSS Feed Fetcher

Fetch and parse RSS feeds into normalized article metadata entries.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, List, TypedDict

import feedparser
import httpx
from bs4 import BeautifulSoup
from loguru import logger

from app.config.settings import settings


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


def _parse_sitemap(xml_content: str) -> List[FeedEntry]:
    """Parse Google Sitemap format (<urlset><url>...)."""
    soup = BeautifulSoup(xml_content, "xml")
    entries: List[FeedEntry] = []

    for url_tag in soup.find_all("url"):
        loc = url_tag.find("loc")
        if not loc:
            continue

        link = loc.get_text().strip()
        lastmod_tag = url_tag.find("lastmod")
        published_at = None

        if lastmod_tag:
            try:
                # Standard sitemap format is ISO 8601
                dt_str = lastmod_tag.get_text().strip()
                # Handle cases like "2025-12-23T09:24+07:00"
                if "Z" in dt_str or "+" in dt_str or "-" in dt_str.split("T")[-1]:
                    published_at = datetime.fromisoformat(dt_str)
                else:
                    # Naive ISO
                    published_at = datetime.fromisoformat(dt_str).replace(
                        tzinfo=timezone.utc
                    )
                published_at = published_at.astimezone(timezone.utc)
            except Exception:
                pass

        # Title extraction: Sitemaps don't have standard titles
        # Look for news-specific or image-specific extensions common in Tuoi Tre/Thanh Nien
        title = ""

        # 1. Try <image:title>
        img_title = url_tag.find("image:title") or url_tag.find("title")
        if img_title:
            title = img_title.get_text().strip()

        # 2. Try <image:caption>
        if not title:
            img_caption = url_tag.find("image:caption")
            if img_caption:
                title = img_caption.get_text().strip()

        # 3. Try <news:title> (Google News Sitemap)
        if not title:
            news_title = url_tag.find("news:title")
            if news_title:
                title = news_title.get_text().strip()

        # 4. Fallback: Clean title from URL slug
        if not title:
            # https://.../slug-here-123.htm -> slug here
            slug = link.split("/")[-1].split(".")[0]
            # Remove trailing numbers if they appear to be IDs (at end of string, preceded by hyphen)
            # Example: slug-title-12345 -> slug-title
            slug = re.sub(r"-\d+$", "", slug)
            title = slug.replace("-", " ").capitalize()

        # Clean CDATA and unescape
        title = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", title, flags=re.DOTALL)
        title = html.unescape(title).strip()

        entries.append(
            FeedEntry(
                title=title,
                link=link,
                published_at=published_at,
            )
        )

    return entries


def fetch_rss_feed(feed_url: str) -> List[FeedEntry]:
    """
    Fetch and parse RSS/Atom feed or Sitemap.

    Args:
        feed_url: URL of the feed or sitemap

    Returns:
        List of normalized entries with title, link, and published_at
    """
    headers = {"User-Agent": settings.crawler.user_agent}

    try:
        # Use httpx for fetching to detect content type and handle sitemaps
        with httpx.Client(
            timeout=settings.crawler.fetch_timeout_seconds,
            headers=headers,
            follow_redirects=True,
        ) as client:
            response = client.get(feed_url)
            response.raise_for_status()
            content = response.text

        # Detect format
        if "<urlset" in content and "<url" in content:
            logger.info(f"Detected sitemap format for {feed_url}")
            return _parse_sitemap(content)

        # Fallback to feedparser for standard RSS/Atom
        parsed = feedparser.parse(content)
        entries: List[FeedEntry] = []
        for e in parsed.entries:
            title = getattr(e, "title", "").strip()
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

    except Exception as e:
        logger.error(f"Error fetching feed {feed_url}: {e}")
        return []
