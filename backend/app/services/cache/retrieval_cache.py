"""
Retrieval Cache Service

Redis-based caching for retrieval results using exact-match (hash-based) keys.
"""

import hashlib
import json
from typing import Dict, List

import redis.asyncio as redis

from app.config.settings import settings
from app.core.logging import get_logger
from app.services.retrieval.article_aggregation_service import ArticleResult

logger = get_logger(__name__)


class RetrievalCache:
    """
    Redis cache for retrieval results.

    Uses SHA256 hash of post text as cache key for exact-match caching.
    """

    def __init__(self):
        self.redis_client: redis.Redis | None = None
        self.enabled = settings.retrieval.cache.enabled
        self.ttl_seconds = settings.retrieval.cache.ttl_seconds
        self.key_prefix = settings.retrieval.cache.redis_key_prefix

    async def _get_client(self) -> redis.Redis:
        """Get or create Redis client"""
        if self.redis_client is None:
            self.redis_client = await redis.from_url(
                f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}",
                encoding="utf-8",
                decode_responses=True,
            )
        return self.redis_client

    def _generate_key(self, post_text: str) -> str:
        """
        Generate cache key from post text using SHA256 hash.

        Args:
            post_text: Original Facebook post text

        Returns:
            Cache key in format: "{prefix}{hash}"
        """
        text_hash = hashlib.sha256(post_text.encode()).hexdigest()
        return f"{self.key_prefix}{text_hash}"

    async def get(self, post_text: str) -> Dict | None:
        """
        Get cached retrieval result.

        Args:
            post_text: Original Facebook post text

        Returns:
            Cached result dictionary or None if not found
        """
        if not self.enabled:
            return None

        try:
            client = await self._get_client()
            key = self._generate_key(post_text)

            cached_value = await client.get(key)

            if cached_value:
                logger.info(f"Cache HIT for key: {key[:32]}...")
                result = json.loads(cached_value)
                return result
            else:
                logger.info(f"Cache MISS for key: {key[:32]}...")
                return None

        except Exception as e:
            logger.error(f"Error getting from cache: {e}")
            return None

    async def set(
        self,
        post_text: str,
        articles: List[ArticleResult],
        total_time_ms: int,
        stage_timings: Dict,
        query_count: int,
    ) -> None:
        """
        Cache retrieval result.

        Args:
            post_text: Original Facebook post text
            articles: List of ArticleResult objects
            total_time_ms: Total pipeline time
            stage_timings: Timing breakdown
            query_count: Number of queries processed
        """
        if not self.enabled:
            return

        try:
            client = await self._get_client()
            key = self._generate_key(post_text)

            # Serialize result
            cache_value = {
                "articles": [article.to_dict() for article in articles],
                "total_time_ms": total_time_ms,
                "stage_timings": stage_timings,
                "query_count": query_count,
            }

            # Store with TTL
            await client.setex(key, self.ttl_seconds, json.dumps(cache_value))

            logger.info(
                f"Cached result for key: {key[:32]}... (TTL: {self.ttl_seconds}s)"
            )

        except Exception as e:
            logger.error(f"Error setting cache: {e}")

    async def clear_all(self) -> int:
        """
        Clear all retrieval cache entries.

        Returns:
            Number of keys deleted
        """
        if not self.enabled:
            return 0

        try:
            client = await self._get_client()

            # Find all keys with our prefix
            pattern = f"{self.key_prefix}*"
            keys = []
            async for key in client.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                deleted = await client.delete(*keys)
                logger.info(f"Cleared {deleted} cache entries")
                return deleted
            else:
                logger.info("No cache entries to clear")
                return 0

        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return 0

    async def close(self) -> None:
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
