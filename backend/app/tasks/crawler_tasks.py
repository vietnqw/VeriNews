"""
Celery tasks for crawling pipeline.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import List

from celery import shared_task
from loguru import logger
from sqlalchemy import select

from app.config.database import async_session_maker
from app.models.article import Article
from app.models.rss_feed import RssFeed
from app.services.article_processor import process_article
from app.services.article_scraper import scrape_article_content
from app.services.rss_fetcher import fetch_rss_feed


def _run(coro):
    return asyncio.run(coro)


@shared_task(
    autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3}
)
def kickoff_all_crawls() -> int:
    """Fan-out crawl tasks for all active feeds."""

    async def _inner() -> int:
        count = 0
        async with async_session_maker() as session:
            result = await session.execute(select(RssFeed).where(RssFeed.is_active))
            feeds: List[RssFeed] = list(result.scalars().all())
            for feed in feeds:
                crawl_feed.delay(str(feed.id))
                count += 1
        return count

    scheduled = _run(_inner())
    logger.info(f"Scheduled crawl for {scheduled} feeds")
    return scheduled


@shared_task(
    autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3}
)
def crawl_feed(feed_id: str) -> int:
    """Fetch RSS and enqueue processing for new articles."""

    async def _inner() -> int:
        new_count = 0
        async with async_session_maker() as session:
            feed_uuid = uuid.UUID(feed_id)
            feed = await session.get(RssFeed, feed_uuid)
            if not feed:
                return 0

            entries = fetch_rss_feed(feed.feed_url)

            # Cache existing URLs for quick duplicate checks
            existing_urls = set()
            result = await session.execute(
                select(Article.url).where(Article.feed_id == feed_uuid)
            )
            for (url,) in result.all():
                existing_urls.add(url)

            for e in entries:
                if e["link"] in existing_urls:
                    continue
                article = Article(
                    title=e.get("title") or e["link"],
                    url=e["link"],
                    published_at=e.get("published_at"),
                    feed_id=feed_uuid,
                )
                session.add(article)
                await session.flush()
                process_article_task.delay(str(article.id))
                new_count += 1

            feed.last_fetched_at = datetime.utcnow()
            await session.flush()
        return new_count

    created = _run(_inner())
    logger.info(f"Feed {feed_id}: created {created} new articles")
    return created


@shared_task(
    autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3}
)
def process_article_task(article_id: str) -> int:
    """Scrape article content and create chunks+embeddings."""

    async def _inner() -> int:
        async with async_session_maker() as session:
            aid = uuid.UUID(article_id)
            article = await session.get(Article, aid)
            if not article:
                return 0
            # Scrape content
            content = await scrape_article_content(article.url)
            article.content = content
            await session.flush()
            # Process into chunks
            created = await process_article(session, aid)
            await session.commit()
            return created

    created_chunks = _run(_inner())
    logger.info(f"Article {article_id}: created {created_chunks} chunks")
    return created_chunks
