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
        claims: List[str] | None = None,
        factual_confidence: int | None = None,
        retrieval_confidence: float | None = None,
        confidence_metrics: Dict | None = None,
        low_confidence_warning: bool = False,
        early_exit: bool = False,
        exit_reason: str | None = None,
        message: str | None = None,
        verification_result: Dict | None = None,
    ) -> None:
        """
        Cache retrieval and verification result.

        Args:
            post_text: Original Facebook post text
            articles: List of ArticleResult objects
            total_time_ms: Total pipeline time
            stage_timings: Timing breakdown
            query_count: Number of queries processed
            claims: Extracted claims from post
            factual_confidence: Confidence in post containing verifiable facts (1-3 scale)
            retrieval_confidence: Confidence that articles are relevant (0-1 scale)
            confidence_metrics: Detailed confidence breakdown dictionary
            low_confidence_warning: Whether low confidence warning should be shown
            early_exit: Whether pipeline exited early
            exit_reason: Reason for early exit if applicable
            message: Human-readable message explaining result
            verification_result: Cached verification result as dictionary
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
                "claims": claims or [],
                "factual_confidence": factual_confidence,
                "retrieval_confidence": retrieval_confidence,
                "confidence_metrics": confidence_metrics,
                "low_confidence_warning": low_confidence_warning,
                "early_exit": early_exit,
                "exit_reason": exit_reason,
                "message": message,
                "verification_result": verification_result,
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
