"""
Celery tasks for crawling pipeline.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import List

from celery import shared_task
from loguru import logger
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError

from app.config.database import async_session_maker, engine
from app.models.article import Article
from app.models.rss_feed import RssFeed
from app.services.crawler.processor_service import process_article
from app.services.crawler.scraper_service import scrape_article_content
from app.services.crawler.rss_service import fetch_rss_feed
from app.config.settings import settings
from app.services.cache.retrieval_cache import RetrievalCache


def _run(coro):
    """
    Run async coroutine in Celery worker context.

    Celery workers run in fork pool mode, so each worker has its own process
    and can safely use asyncio.run().
    """
    return asyncio.run(coro)


@shared_task(
    autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3}
)
def kickoff_all_crawls() -> int:
    """Fan-out crawl tasks for all active feeds."""

    async def _inner() -> int:
        count = 0
        try:
            # Clear the retrieval cache at the start of the crawl cycle
            logger.info("Clearing retrieval cache before starting crawl cycle...")
            cache = RetrievalCache()
            deleted_count = await cache.clear_all()
            logger.info(f"Cleared {deleted_count} cache entries.")
            await cache.close()

            async with async_session_maker() as session:
                result = await session.execute(select(RssFeed).where(RssFeed.is_active))
                feeds: List[RssFeed] = list(result.scalars().all())
                for feed in feeds:
                    crawl_feed.delay(str(feed.id))
                    count += 1
            return count
        finally:
            # Ensure async engine is disposed before loop teardown in Celery worker
            await engine.dispose()

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
        try:
            async with async_session_maker() as session:
                feed_uuid = uuid.UUID(feed_id)
                feed = await session.get(RssFeed, feed_uuid)
                if not feed:
                    return 0

                entries = fetch_rss_feed(feed.feed_url)
                max_new = settings.crawler.max_articles_per_feed
                ingest_max_age_hours = settings.crawler.ingest_max_age_hours
                cutoff_time = datetime.now(timezone.utc) - timedelta(
                    hours=ingest_max_age_hours
                )

                # Cache existing URLs for quick duplicate checks
                existing_urls = set()
                result = await session.execute(
                    select(Article.url).where(Article.feed_id == feed_uuid)
                )
                for (url,) in result.all():
                    existing_urls.add(url)

                # Collect new article IDs to process after commit
                new_article_ids = []
                processed = 0
                for e in entries:
                    # Skip articles older than the ingest cutoff (if published_at is available)
                    if e.get("published_at") and e["published_at"] < cutoff_time:
                        continue
                    if e["link"] in existing_urls:
                        continue
                    if max_new > 0 and processed >= max_new:
                        break

                    try:
                        article = Article(
                            title=e.get("title") or e["link"],
                            url=e["link"],
                            published_at=e.get("published_at"),
                            feed_id=feed_uuid,
                        )
                        session.add(article)
                        await session.flush()
                        # Store article ID for processing after commit
                        new_article_ids.append(str(article.id))
                        new_count += 1
                        processed += 1
                    except IntegrityError:
                        # Article URL already exists (race condition with another worker)
                        await session.rollback()
                        logger.debug(f"Skipping duplicate article: {e['link']}")
                        continue

                feed.last_fetched_at = datetime.utcnow()
                await session.flush()
                await session.commit()

                # Enqueue processing tasks AFTER commit so articles are visible to workers
                logger.info(
                    f"Enqueueing {len(new_article_ids)} article processing tasks"
                )
                for article_id in new_article_ids:
                    try:
                        process_article_task.delay(article_id)
                        logger.debug(f"Enqueued task for article {article_id}")
                    except Exception as e:
                        logger.error(
                            f"Failed to enqueue task for article {article_id}: {e}"
                        )
            return new_count
        finally:
            await engine.dispose()

    created = _run(_inner())
    logger.info(f"Feed {feed_id}: created {created} new articles")
    return created


@shared_task(
    autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3}
)
def process_article_task(article_id: str) -> int:
    """Scrape article content and create chunks+embeddings."""

    async def _inner() -> int:
        try:
            async with async_session_maker() as session:
                aid = uuid.UUID(article_id)
                article = await session.get(Article, aid)
                if not article:
                    logger.warning(f"Article {article_id} not found")
                    return 0

                logger.info(f"Processing article {article_id}: {article.url}")

                # Scrape content
                logger.debug(f"Starting scrape for {article.url}")
                content = await scrape_article_content(article.url)
                logger.info(f"Scraped {len(content)} chars from {article.url}")

                article.content = content
                await session.flush()

                # Process into chunks
                logger.debug("Processing article into chunks")
                created = await process_article(session, aid)
                await session.commit()

                logger.info(f"Created {created} chunks for article {article_id}")
                return created
        except Exception as e:
            logger.error(f"Error processing article {article_id}: {e}", exc_info=True)
            raise
        finally:
            await engine.dispose()

    created_chunks = _run(_inner())
    logger.info(f"Article {article_id}: created {created_chunks} chunks")
    return created_chunks


@shared_task(
    autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3}
)
def cleanup_expired_articles() -> int:
    """
    Delete articles whose created_at is older than now - retention_hours.
    Cascading deletes will remove related ArticleChunk rows.
    """

    async def _inner() -> int:
        try:
            async with async_session_maker() as session:
                retention_hours = settings.crawler.retention_hours
                cutoff_time = datetime.now(timezone.utc) - timedelta(
                    hours=retention_hours
                )

                # Use RETURNING to count deleted rows reliably
                result = await session.execute(
                    delete(Article)
                    .where(Article.created_at < cutoff_time)
                    .returning(Article.id)
                )
                deleted_ids = [row[0] for row in result.fetchall()]
                await session.commit()

                deleted_count = len(deleted_ids)
                if deleted_count > 0:
                    logger.info(
                        f"Deleted {deleted_count} expired articles older than {retention_hours}h"
                    )
                else:
                    logger.debug(
                        f"No expired articles found older than {retention_hours}h"
                    )
                return deleted_count
        finally:
            await engine.dispose()

    deleted = _run(_inner())
    logger.info(f"Cleanup complete: deleted {deleted} expired articles")
    return deleted
