"""
Service Layer

Organized service modules for business logic and data access.
"""

# Base classes and exceptions
from app.services.base import BaseService
from app.services.exceptions import (
    ServiceError,
    NotFoundError,
    DuplicateError,
    ValidationError,
    ProcessingError,
    ExternalServiceError,
)

# Repository layer
from app.services.repository import NewsSourceRepository, RssFeedRepository

# Crawler services
from app.services.crawler import fetch_rss_feed, scrape_article_content, process_article

# Content processing services
from app.services.content import chunk_text, generate_embedding

# Database utilities
from app.services.database import get_async_session

__all__ = [
    # Base classes and exceptions
    "BaseService",
    "ServiceError",
    "NotFoundError",
    "DuplicateError",
    "ValidationError",
    "ProcessingError",
    "ExternalServiceError",
    # Repository layer
    "NewsSourceRepository",
    "RssFeedRepository",
    # Crawler services
    "fetch_rss_feed",
    "scrape_article_content",
    "process_article",
    # Content processing
    "chunk_text",
    "generate_embedding",
    # Database
    "get_async_session",
]
