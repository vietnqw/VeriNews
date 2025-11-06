"""
RSS Feed Repository

Database operations for RssFeed model.
"""

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.rss_feed import RssFeed
from app.services.base import BaseService


class RssFeedRepository(BaseService[RssFeed]):
    """Repository for RssFeed CRUD operations"""

    def __init__(self):
        super().__init__(RssFeed)

    async def get_by_url(
        self, session: AsyncSession, feed_url: str
    ) -> Optional[RssFeed]:
        """
        Get an RSS feed by URL.

        Args:
            session: Database session
            feed_url: URL of the RSS feed

        Returns:
            RssFeed if found, None otherwise
        """
        result = await session.execute(
            select(RssFeed).where(RssFeed.feed_url == feed_url)
        )
        return result.scalar_one_or_none()

    async def list_all_with_source(self, session: AsyncSession) -> List[RssFeed]:
        """
        List all RSS feeds with their news sources eagerly loaded.

        Args:
            session: Database session

        Returns:
            List of all RSS feeds with sources
        """
        result = await session.execute(
            select(RssFeed).options(selectinload(RssFeed.news_source))
        )
        return list(result.scalars().all())

    async def list_active(self, session: AsyncSession) -> List[RssFeed]:
        """
        List all active RSS feeds.

        Args:
            session: Database session

        Returns:
            List of active RSS feeds
        """
        result = await session.execute(
            select(RssFeed)
            .where(RssFeed.is_active == True)  # noqa: E712
            .options(selectinload(RssFeed.news_source))
        )
        return list(result.scalars().all())

    async def update_status(
        self, session: AsyncSession, feed_id: uuid.UUID, is_active: bool
    ) -> Optional[RssFeed]:
        """
        Update the active status of an RSS feed.

        Args:
            session: Database session
            feed_id: UUID of the RSS feed
            is_active: New active status

        Returns:
            Updated feed if found, None otherwise
        """
        return await self.update(session, feed_id, is_active=is_active)

    async def get_or_create(
        self,
        session: AsyncSession,
        source_id: uuid.UUID,
        feed_url: str,
        topic: Optional[str] = None,
    ) -> tuple[RssFeed, bool]:
        """
        Get existing feed or create new one.

        Args:
            session: Database session
            source_id: UUID of the parent news source
            feed_url: URL of the RSS feed
            topic: Optional topic/category

        Returns:
            Tuple of (RssFeed instance, created boolean)
        """
        existing = await self.get_by_url(session, feed_url)
        if existing:
            return existing, False

        feed = await self.create(
            session, source_id=source_id, feed_url=feed_url, topic=topic
        )
        return feed, True
