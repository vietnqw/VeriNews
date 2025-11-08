"""
VerificationRequest Model

Represents a user's request to verify a Facebook post.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.retrieval_result import RetrievalResult


class VerificationStatus(str, enum.Enum):
    """Status of a verification request"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class VerificationRequest(Base):
    """
    VerificationRequest model - represents a verification request.

    Stores the original Facebook post text and extracted queries (clean_query + claims).
    The text_hash enables Redis caching for exact-match posts.
    """

    __tablename__ = "verification_requests"

    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Original Post
    original_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Hash for caching (SHA256 of original_text)
    text_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )

    # Extracted Queries (from LLM)
    clean_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    claims: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Status
    status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus),
        nullable=False,
        default=VerificationStatus.PENDING,
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

    # Relationships
    retrieval_result: Mapped["RetrievalResult | None"] = relationship(
        "RetrievalResult",
        back_populates="verification_request",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"VerificationRequest(id={self.id}, status={self.status}, text_hash={self.text_hash[:16]}...)"
