"""
Article Scraper

Download an article URL and extract main textual content using heuristics.
"""

from __future__ import annotations

from typing import Optional

import httpx
from bs4 import BeautifulSoup

from app.config.settings import settings


async def fetch_html(url: str, *, timeout_s: Optional[int] = None) -> str:
    """Fetch page HTML with configured user-agent and timeout."""
    timeout = timeout_s or settings.crawler.fetch_timeout_seconds
    headers = {"User-Agent": settings.crawler.user_agent}
    async with httpx.AsyncClient(
        timeout=timeout, headers=headers, follow_redirects=True
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text


def _pick_longest_text(*nodes: str) -> str:
    texts = [n.strip() for n in nodes if n and n.strip()]
    if not texts:
        return ""
    return max(texts, key=len)


def _extract_text(soup: BeautifulSoup) -> str:
    # Try common containers
    candidates = []
    for selector in [
        "article",
        "div.article-body",
        "div[itemprop='articleBody']",
        "section.article-body",
        "div#article",
        "main",
    ]:
        node = soup.select_one(selector)
        if node:
            candidates.append(node.get_text("\n"))

    # Fallback: concatenate paragraph texts
    if not candidates:
        paragraphs = [p.get_text("\n") for p in soup.find_all("p")]
        candidates.append("\n\n".join(paragraphs))

    return _pick_longest_text(*candidates)


async def scrape_article_content(url: str) -> str:
    """Scrape main textual content from article URL."""
    html = await fetch_html(url)
    soup = BeautifulSoup(html, "lxml")
    text = _extract_text(soup)
    if settings.crawler.max_content_length > 0:
        text = text[: settings.crawler.max_content_length]
    return text
