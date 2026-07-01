"""
Article-Level Reranking Service

Reranks articles (not chunks) using LLM to evaluate whether the article's main topic
matches the query. This prevents false positives where individual chunks match but the
full article is about a different topic/event.

Optimized for speed:
- 8 parallel workers (vs 4 for chunks)
- Simplified prompts (~300 tokens vs 1200)
- Article title + top chunk snippet (not full text)
- Early exit for single high-confidence article
"""

import asyncio
import json
from typing import Dict, List, Tuple

from app.config.settings import settings
from app.core.logging import get_logger
from app.services.ai.base import LLMMessage
from app.services.ai.factory import AIServiceFactory
from app.services.common import round_robin_batches, run_worker_batches
from app.services.retrieval.article_aggregation_service import ArticleResult

logger = get_logger(__name__)


class ArticleRerankerService:
    """
    Article-level reranking service with parallel LLM workers.

    Evaluates whether articles' main topics match the query to eliminate
    tangential mentions and improve precision.
    """

    def __init__(self):
        self.llm = AIServiceFactory.get_llm_provider()
        self.model = settings.ai.llm_model
        self.num_workers = (
            settings.retrieval.reranking.article_level.num_parallel_workers
        )
        self.worker_timeout = (
            settings.retrieval.reranking.article_level.worker_timeout_seconds
        )
        self.max_concurrent = (
            settings.retrieval.reranking.article_level.max_concurrent_calls
        )
        self.score_threshold = (
            settings.retrieval.reranking.article_level.score_threshold
        )
        self.min_items_for_split = (
            settings.retrieval.reranking.article_level.min_items_for_split
        )
        self.early_exit_score = (
            settings.retrieval.reranking.article_level.early_exit_score
        )

    async def rerank_articles(
        self,
        query: str,
        articles: List[ArticleResult],
        top_n: int = 10,
    ) -> List[ArticleResult]:
        """
        Rerank articles using parallel LLM evaluation.

        Args:
            query: Original query (social media post)
            articles: List of articles to rerank (typically 5-15 from aggregation)
            top_n: Number of top articles to return

        Returns:
            Reranked list of articles (top_n), sorted by article-level relevance score
            Returns empty list if no articles pass threshold
        """

        if not articles:
            return []

        # Early exit for single high-confidence article (score is 0-10 scale)
        if len(articles) == 1 and articles[0].relevance_score >= self.early_exit_score:
            logger.info(
                "Early exit: Single high-confidence article "
                f"(score={articles[0].relevance_score:.2f})"
            )
            return articles

        logger.info(
            f"Article-level reranking: {len(articles)} articles with "
            f"{self.num_workers} workers"
        )

        # Split articles across workers. Small sets go to a single worker so the
        # LLM can score them comparatively (listwise); larger sets round-robin.
        batches = round_robin_batches(
            articles,
            self.num_workers,
            min_items_for_single_batch=self.min_items_for_split,
        )
        semaphore = asyncio.Semaphore(self.max_concurrent)

        worker_results = await run_worker_batches(
            batches,
            lambda worker_id, batch: self._score_worker_batch(
                query, batch, worker_id, semaphore
            ),
        )

        # Filter out exceptions
        successful_results = [r for r in worker_results if not isinstance(r, Exception)]

        if len(successful_results) < len(worker_results):
            failed_count = len(worker_results) - len(successful_results)
            logger.warning(f"Article reranking: {failed_count} workers failed")

        if not successful_results:
            logger.error("All article reranking workers failed")
            return []

        # Merge scores from all workers
        article_scores = self._merge_worker_scores(articles, successful_results)

        # Apply scores and filter by threshold
        scored_articles = []
        for article, score in zip(articles, article_scores):
            if score >= self.score_threshold:
                # Keep score in 0-10 scale
                article.relevance_score = score
                scored_articles.append(article)

        # Sort by score (descending)
        scored_articles.sort(key=lambda x: x.relevance_score, reverse=True)

        logger.info(
            f"Article reranking complete: {len(articles)} input → "
            f"{len(scored_articles)} passed threshold (≥{self.score_threshold})"
        )

        return scored_articles[:top_n]

    async def _score_worker_batch(
        self,
        query: str,
        batch: List[Tuple[int, ArticleResult]],
        worker_id: int,
        semaphore: asyncio.Semaphore,
    ) -> Dict[str, float]:
        """
        Score a batch of articles using LLM (single worker).

        Args:
            query: Original query
            batch: Batch of (original_index, article) tuples for this worker
            worker_id: Worker identifier
            semaphore: Semaphore for rate limiting

        Returns:
            Dict mapping article index (as "id{index}") to score (0-10)
        """
        if not batch:
            return {}

        async with semaphore:
            try:
                # Build prompt using original indices
                prompt = self._build_article_scoring_prompt(query, batch)

                # Create message
                messages = [LLMMessage(role="user", content=prompt)]

                # Call LLM with timeout
                try:
                    response = await asyncio.wait_for(
                        self.llm.generate_completion(
                            messages=messages,
                            model=self.model,
                            temperature=0,  # Deterministic output
                            response_format={"type": "json_object"},
                        ),
                        timeout=self.worker_timeout,
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        f"Worker {worker_id} timed out after {self.worker_timeout}s "
                        f"({len(batch)} articles)"
                    )
                    return {}

                # Parse JSON response - extract content from LLMResponse
                try:
                    response_text = (
                        response.content
                        if hasattr(response, "content")
                        else str(response)
                    )
                    scores = json.loads(response_text)
                except json.JSONDecodeError as e:
                    logger.error(
                        f"Worker {worker_id} failed to parse JSON: {e}. "
                        f"Response: {response_text[:200] if response_text else 'empty'}"
                    )
                    return {}

                # Validate scores
                validated_scores = {}
                for article_id_str, score in scores.items():
                    if isinstance(score, (int, float)) and 0 <= score <= 10:
                        validated_scores[article_id_str] = float(score)
                    else:
                        logger.warning(
                            f"Worker {worker_id}: Invalid score {score} "
                            f"for {article_id_str}"
                        )

                logger.debug(
                    f"Worker {worker_id} scored {len(validated_scores)}/{len(batch)} "
                    f"articles"
                )

                return validated_scores

            except Exception as e:
                logger.error(
                    f"Worker {worker_id} encountered error: {e}", exc_info=True
                )
                return {}

    def _build_article_scoring_prompt(
        self, query: str, batch: List[Tuple[int, ArticleResult]]
    ) -> str:
        """
        Build simplified prompt for article-level relevance scoring.

        Uses article title + source + top chunk snippet (not full text)
        to minimize tokens and improve speed.

        Target: ~300 tokens (vs 1200 for chunk reranking)
        """
        # Build article entries using original indices
        article_entries = []
        for original_idx, article in batch:
            # Get top chunk snippet (200 chars max)
            top_chunk = article.relevant_chunks[0] if article.relevant_chunks else None
            snippet = top_chunk.chunk_text[:200] if top_chunk else "(no content)"

            article_entries.append(
                f"<article id='id{original_idx}'>\n"
                f"  <title>{article.title}</title>\n"
                f"  <source>{article.source_name}</source>\n"
                f"  <snippet>{snippet}</snippet>\n"
                f"</article>"
            )

        articles_xml = "\n\n".join(article_entries)

        prompt = f"""Score each article's relevance to the query (0-10 scale).

Query: {query}

Articles:
{articles_xml}

SCORING CRITERIA (0-10):
10: Article's MAIN TOPIC is the SAME specific event/claim as query. All key details match.
7-9: Article discusses query topic substantially but includes other topics or minor detail differences.
5-6: Article mentions query entities but DIFFERENT main topic or event.
0-4: Article about COMPLETELY DIFFERENT topic (different event/time/location/amount).

CRITICAL RULES:
- If an article shares entities but discusses a DIFFERENT event, score 0-4 (NOT 5+)
- Article MAIN TOPIC must match, not just passing mentions
- Different time periods = different events (e.g., "2025" vs "2023")
- Different locations = different events (e.g., "Hà Nội" vs "Đà Nẵng")
- If NO articles match the query's specific event, return empty JSON: {{}}

Output Format:
Return ONLY valid JSON (no spaces):
{{"id0":score,"id1":score,...}}

Include only scores ≥5. If no articles score ≥5, return {{}}."""

        return prompt

    def _merge_worker_scores(
        self, articles: List[ArticleResult], worker_results: List[Dict[str, float]]
    ) -> List[float]:
        """
        Merge scores from all workers back into article order.

        Args:
            articles: Original article list (in order)
            worker_results: List of score dicts from each worker

        Returns:
            List of scores (same order as articles)
            Unscored articles get 0.0
        """
        # Combine all worker scores into single dict
        all_scores: Dict[str, float] = {}
        for worker_result in worker_results:
            all_scores.update(worker_result)

        # Map scores back to articles
        article_scores = []
        for i, article in enumerate(articles):
            # Try to find score using multiple key formats
            article_id_str = str(article.article_id)
            score_key = f"id{i}"

            if score_key in all_scores:
                score = all_scores[score_key]
            elif article_id_str in all_scores:
                score = all_scores[article_id_str]
            else:
                # Article was not scored (below threshold or error)
                score = 0.0
                logger.debug(
                    f"Article {i} ({article.title[:50]}) received no score, "
                    "defaulting to 0.0"
                )

            article_scores.append(score)

        return article_scores
