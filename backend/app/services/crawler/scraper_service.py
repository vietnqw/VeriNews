"""
Article Scraper

Download an article URL and extract clean textual content.
Uses trafilatura for intelligent extraction with fallback strategies.
"""

from __future__ import annotations

import html
from typing import Optional

import httpx
import justext
import trafilatura
from bs4 import BeautifulSoup
from loguru import logger
from readability import Document

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


def _extract_with_trafilatura(
    html_content: str, *, favor_precision: bool = True
) -> str:
    """
    Extract article content using trafilatura.

    Trafilatura is an ML-based extraction library optimized for news articles.
    It automatically removes boilerplate, comments, ads, and navigation.
    """
    text = trafilatura.extract(
        html_content,
        include_comments=False,  # Exclude comment sections
        include_tables=True,  # Keep data tables if present
        no_fallback=False,  # Allow fallback extraction methods
        favor_precision=favor_precision,  # Precision vs recall tradeoff
        deduplicate=True,  # Remove duplicate sentences
    )
    return text or ""


def _extract_with_mvp_approach(html_content: str) -> str:
    """
    Extract content using MVP's two-stage approach.

    Fallback method using readability-lxml + justext pipeline.
    Works well on standard Vietnamese news layouts.
    """
    try:
        # Stage 1: Use readability to find main content block
        doc = Document(html_content)
        main_content_html = doc.summary()

        # Stage 2: Use justext to clean boilerplate
        paragraphs = justext.justext(
            main_content_html, justext.get_stoplist("Vietnamese")
        )
        cleaned_text = "\n\n".join(p.text for p in paragraphs if not p.is_boilerplate)

        # Decode HTML entities
        cleaned_text = html.unescape(cleaned_text)

        return cleaned_text.strip()

    except Exception as e:
        logger.warning(f"MVP extraction failed: {e}")
        return ""


def _extract_basic_paragraphs(html_content: str) -> str:
    """
    Last resort: Basic paragraph extraction.

    Extracts all <p> tags from the page. May include boilerplate
    but ensures we always get something.
    """
    try:
        soup = BeautifulSoup(html_content, "lxml")
        paragraphs = [p.get_text().strip() for p in soup.find_all("p")]
        # Filter out very short paragraphs (likely navigation/ads)
        meaningful_paragraphs = [p for p in paragraphs if len(p) > 50]
        return "\n\n".join(meaningful_paragraphs)

    except Exception as e:
        logger.error(f"Basic extraction failed: {e}")
        return ""


async def scrape_article_content(url: str) -> str:
    """
    Scrape clean article content from URL.

    Uses a multi-stage fallback strategy for maximum reliability:
    1. Trafilatura (precision mode) - Best for most news sites
    2. Trafilatura (recall mode) - More lenient extraction
    3. MVP approach (readability + justext) - Vietnamese-optimized fallback
    4. Basic paragraph extraction - Last resort

    Returns:
        Cleaned article text with boilerplate, comments, and ads removed.
        Empty string if all extraction methods fail.
    """
    html = await fetch_html(url)

    # Strategy 1: Trafilatura with high precision
    logger.debug(f"Attempting trafilatura (precision) extraction for {url}")
    text = _extract_with_trafilatura(html, favor_precision=True)

    if len(text) >= 100:
        logger.info(
            f"Successfully extracted {len(text)} chars using trafilatura (precision)"
        )
        if settings.crawler.max_content_length > 0:
            text = text[: settings.crawler.max_content_length]
        return text.strip()

    # Strategy 2: Trafilatura with higher recall
    logger.debug(f"Attempting trafilatura (recall) extraction for {url}")
    text = _extract_with_trafilatura(html, favor_precision=False)

    if len(text) >= 100:
        logger.info(
            f"Successfully extracted {len(text)} chars using trafilatura (recall)"
        )
        if settings.crawler.max_content_length > 0:
            text = text[: settings.crawler.max_content_length]
        return text.strip()

    # Strategy 3: MVP approach (readability + justext)
    logger.debug(f"Attempting MVP extraction for {url}")
    text = _extract_with_mvp_approach(html)

    if len(text) >= 100:
        logger.info(f"Successfully extracted {len(text)} chars using MVP approach")
        if settings.crawler.max_content_length > 0:
            text = text[: settings.crawler.max_content_length]
        return text.strip()

    # Strategy 4: Last resort - basic extraction
    logger.warning(f"Using basic extraction fallback for {url}")
    text = _extract_basic_paragraphs(html)

    if len(text) >= 50:
        logger.info(f"Extracted {len(text)} chars using basic extraction")
        if settings.crawler.max_content_length > 0:
            text = text[: settings.crawler.max_content_length]
        return text.strip()

    # Complete failure
    logger.error(f"All extraction methods failed for {url}")
    return ""
