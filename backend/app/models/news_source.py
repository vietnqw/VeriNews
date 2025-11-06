"""
NewsSource Model

Represents a trusted news organization that provides RSS feeds.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.rss_feed import RssFeed


class NewsSource(Base):
    """
    NewsSource model - represents a trusted news organization.

    A NewsSource can have multiple RSS feeds for different topics or sections.
    """

    __tablename__ = "news_sources"

    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Core Fields
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)

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

    # Relationships
    rss_feeds: Mapped[list["RssFeed"]] = relationship(
        "RssFeed", back_populates="news_source", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"NewsSource(id={self.id}, name={self.name}, base_url={self.base_url})"
