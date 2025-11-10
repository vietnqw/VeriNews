"""
RetrievalResult Model

Represents the result of the retrieval pipeline for a verification request.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.verification_request import VerificationRequest


class RetrievalResult(Base):
    """
    RetrievalResult model - stores results from the retrieval pipeline.

    Contains all intermediate and final results from the two-stage hybrid retrieval:
    - Retrieved chunks from RRF fusion
    - Reranked chunks after OpenAI reranking
    - Final aggregated articles
    - Timing breakdown for performance monitoring
    """

    __tablename__ = "retrieval_results"

    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Foreign Key to VerificationRequest
    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("verification_requests.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Retrieval Results (stored as JSON)
    retrieved_chunks_json: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Top chunks from RRF fusion with scores",
    )

    reranked_chunks_json: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Top-N chunks after OpenAI reranking",
    )

    final_articles_json: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Aggregated article results with scores",
    )

    # Performance Metrics
    processing_time_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Total pipeline processing time in milliseconds",
    )

    stage_timings_json: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Breakdown of time spent in each pipeline stage",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    verification_request: Mapped["VerificationRequest"] = relationship(
        "VerificationRequest",
        back_populates="retrieval_result",
    )

    def __repr__(self) -> str:
        return f"RetrievalResult(id={self.id}, request_id={self.request_id}, processing_time_ms={self.processing_time_ms})"
