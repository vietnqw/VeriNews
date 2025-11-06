"""
News Source Repository

Database operations for NewsSource model.
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news_source import NewsSource
from app.services.base import BaseService


class NewsSourceRepository(BaseService[NewsSource]):
    """Repository for NewsSource CRUD operations"""

    def __init__(self):
        super().__init__(NewsSource)

    async def get_by_name(
        self, session: AsyncSession, name: str
    ) -> Optional[NewsSource]:
        """
        Get a news source by name.

        Args:
            session: Database session
            name: Name of the news source

        Returns:
            NewsSource if found, None otherwise
        """
        result = await session.execute(
            select(NewsSource).where(NewsSource.name == name)
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self, session: AsyncSession, name: str, base_url: str
    ) -> tuple[NewsSource, bool]:
        """
        Get existing source or create new one.

        Args:
            session: Database session
            name: Name of the news source
            base_url: Base URL of the news source

        Returns:
            Tuple of (NewsSource instance, created boolean)
        """
        existing = await self.get_by_name(session, name)
        if existing:
            return existing, False

        source = await self.create(session, name=name, base_url=base_url)
        return source, True
