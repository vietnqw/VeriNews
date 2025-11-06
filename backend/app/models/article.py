"""
Article Model

Represents a news article from an RSS feed.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.article_chunk import ArticleChunk
    from app.models.rss_feed import RssFeed


class Article(Base):
    """
    Article model - represents a news article.

    Article content is stored in chunks (ArticleChunk) with embeddings.
    No full content field here - reconstruct from chunks when needed.
    """

    __tablename__ = "articles"

    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Core Fields
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)

    # Publication Date
    published_at: Mapped[datetime | None] = mapped_column(
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
    feed_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rss_feeds.id", ondelete="CASCADE"), nullable=False
    )

    # Relationships
    rss_feed: Mapped["RssFeed"] = relationship("RssFeed", back_populates="articles")
    chunks: Mapped[list["ArticleChunk"]] = relationship(
        "ArticleChunk",
        back_populates="article",
        cascade="all, delete-orphan",
        order_by="ArticleChunk.chunk_index",
    )

    def __repr__(self) -> str:
        return (
            f"Article(id={self.id}, title={self.title[:50]}..., url={self.url[:50]}...)"
        )
