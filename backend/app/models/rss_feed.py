"""
RssFeed Model

Represents an RSS feed from a trusted news source.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.expression import true

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.article import Article
    from app.models.news_source import NewsSource


class RssFeed(Base):
    """
    RssFeed model - represents an RSS feed from a news source.

    Each feed can be for a specific topic or section of the news source.
    """

    __tablename__ = "rss_feeds"

    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Core Fields
    feed_url: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    topic: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Status and Tracking Fields
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=true(), nullable=False
    )
    last_fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Foreign Keys
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("news_sources.id", ondelete="CASCADE"), nullable=False
    )

    # Relationships
    news_source: Mapped["NewsSource"] = relationship(
        "NewsSource", back_populates="rss_feeds"
    )
    articles: Mapped[list["Article"]] = relationship(
        "Article", back_populates="rss_feed", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"RssFeed(id={self.id}, feed_url={self.feed_url}, topic={self.topic})"
