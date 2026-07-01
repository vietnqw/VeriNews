"""
Article Repository

Database operations for the Article model.
"""

from typing import Dict, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.services.base import BaseService


class ArticleRepository(BaseService[Article]):
    """Repository for Article read operations used by the retrieval pipeline."""

    def __init__(self):
        super().__init__(Article)

    async def get_metadata_by_ids(
        self, session: AsyncSession, article_ids: List[UUID]
    ) -> Dict[UUID, Dict]:
        """
        Fetch url/content/published_at for a set of articles in one query.

        Args:
            session: Database session
            article_ids: Article IDs to look up

        Returns:
            Mapping of article_id -> {"url", "content", "published_at"}.
            Missing IDs are simply absent from the mapping.
        """
        if not article_ids:
            return {}

        result = await session.execute(
            select(
                Article.id, Article.url, Article.content, Article.published_at
            ).where(Article.id.in_(article_ids))
        )
        return {
            row.id: {
                "url": row.url,
                "content": row.content,
                "published_at": row.published_at,
            }
            for row in result.all()
        }
