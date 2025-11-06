"""
RSS Feed CRUD Service

Provides database operations for managing news sources and RSS feeds.
"""

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.news_source import NewsSource
from app.models.rss_feed import RssFeed


async def create_source(session: AsyncSession, name: str, base_url: str) -> NewsSource:
    """
    Create a new news source.

    Args:
        session: Database session
        name: Name of the news source
        base_url: Base URL of the news source

    Returns:
        NewsSource: Created news source

    Raises:
        IntegrityError: If source with same name or URL already exists
    """
    source = NewsSource(name=name, base_url=base_url)
    session.add(source)
    await session.flush()
    return source


async def get_source_by_name(session: AsyncSession, name: str) -> Optional[NewsSource]:
    """
    Get a news source by name.

    Args:
        session: Database session
        name: Name of the news source

    Returns:
        Optional[NewsSource]: News source if found, None otherwise
    """
    result = await session.execute(select(NewsSource).where(NewsSource.name == name))
    return result.scalar_one_or_none()


async def get_source_by_id(
    session: AsyncSession, source_id: uuid.UUID
) -> Optional[NewsSource]:
    """
    Get a news source by ID.

    Args:
        session: Database session
        source_id: UUID of the news source

    Returns:
        Optional[NewsSource]: News source if found, None otherwise
    """
    result = await session.execute(select(NewsSource).where(NewsSource.id == source_id))
    return result.scalar_one_or_none()


async def create_feed(
    session: AsyncSession, source_id: uuid.UUID, feed_url: str, topic: Optional[str]
) -> RssFeed:
    """
    Create a new RSS feed for a source.

    Args:
        session: Database session
        source_id: UUID of the parent news source
        feed_url: URL of the RSS feed
        topic: Optional topic/category of the feed

    Returns:
        RssFeed: Created RSS feed

    Raises:
        IntegrityError: If feed with same URL already exists
    """
    feed = RssFeed(source_id=source_id, feed_url=feed_url, topic=topic)
    session.add(feed)
    await session.flush()
    return feed


async def get_feed_by_url(session: AsyncSession, feed_url: str) -> Optional[RssFeed]:
    """
    Get an RSS feed by URL.

    Args:
        session: Database session
        feed_url: URL of the RSS feed

    Returns:
        Optional[RssFeed]: RSS feed if found, None otherwise
    """
    result = await session.execute(select(RssFeed).where(RssFeed.feed_url == feed_url))
    return result.scalar_one_or_none()


async def get_feed_by_id(
    session: AsyncSession, feed_id: uuid.UUID
) -> Optional[RssFeed]:
    """
    Get an RSS feed by ID.

    Args:
        session: Database session
        feed_id: UUID of the RSS feed

    Returns:
        Optional[RssFeed]: RSS feed if found, None otherwise
    """
    result = await session.execute(select(RssFeed).where(RssFeed.id == feed_id))
    return result.scalar_one_or_none()


async def list_all_feeds(session: AsyncSession) -> List[RssFeed]:
    """
    List all RSS feeds with their news sources.

    Args:
        session: Database session

    Returns:
        List[RssFeed]: List of all RSS feeds
    """
    result = await session.execute(
        select(RssFeed).options(selectinload(RssFeed.news_source))
    )
    return list(result.scalars().all())


async def list_active_feeds(session: AsyncSession) -> List[RssFeed]:
    """
    List all active RSS feeds.

    Args:
        session: Database session

    Returns:
        List[RssFeed]: List of active RSS feeds
    """
    result = await session.execute(
        select(RssFeed)
        .where(RssFeed.is_active == True)  # noqa: E712
        .options(selectinload(RssFeed.news_source))
    )
    return list(result.scalars().all())


async def delete_feed(session: AsyncSession, feed_id: uuid.UUID) -> bool:
    """
    Delete an RSS feed.

    Args:
        session: Database session
        feed_id: UUID of the RSS feed to delete

    Returns:
        bool: True if feed was deleted, False if not found
    """
    feed = await get_feed_by_id(session, feed_id)
    if feed:
        await session.delete(feed)
        await session.flush()
        return True
    return False


async def update_feed_status(
    session: AsyncSession, feed_id: uuid.UUID, is_active: bool
) -> Optional[RssFeed]:
    """
    Update the active status of an RSS feed.

    Args:
        session: Database session
        feed_id: UUID of the RSS feed
        is_active: New active status

    Returns:
        Optional[RssFeed]: Updated feed if found, None otherwise
    """
    feed = await get_feed_by_id(session, feed_id)
    if feed:
        feed.is_active = is_active
        await session.flush()
        return feed
    return None


async def update_feed_fields(
    session: AsyncSession,
    feed_id: uuid.UUID,
    *,
    topic: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Optional[RssFeed]:
    """
    Update mutable fields of an RSS feed (topic, is_active).

    Args:
        session: Database session
        feed_id: UUID of the RSS feed
        topic: Optional new topic
        is_active: Optional new active status

    Returns:
        Optional[RssFeed]: Updated feed if found, None otherwise
    """
    feed = await get_feed_by_id(session, feed_id)
    if not feed:
        return None

    if topic is not None and topic != feed.topic:
        feed.topic = topic
    if is_active is not None and is_active != feed.is_active:
        feed.is_active = is_active

    await session.flush()
    return feed
