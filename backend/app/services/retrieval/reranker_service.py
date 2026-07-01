"""
Reranking Service

Reranks retrieved chunks using OpenAI LLM for higher precision.
Uses parallel workers with round-robin batching for optimal performance.
Includes entity-based filtering to focus on relevant chunks.
"""

import asyncio
import json
import re
from typing import Dict, List

from app.config.settings import settings
from app.core.logging import get_logger
from app.services.ai.base import LLMMessage
from app.services.ai.factory import AIServiceFactory
from app.services.common import round_robin_batches, run_worker_batches
from app.services.common.parallel_workers import IndexedBatch
from app.services.retrieval.bm25_search_service import ChunkSearchResult

logger = get_logger(__name__)


class RerankerService:
    """
    OpenAI-based reranking service with parallel worker optimization.

    Reranks chunks by scoring their relevance to the original query using an LLM.
    Uses round-robin batching across parallel workers to reduce latency and improve quality.
    """

    def __init__(self):
        self.llm = AIServiceFactory.get_llm_provider()
        self.model = settings.ai.llm_model
        self.top_n = settings.retrieval.reranking.top_n
        self.num_workers = settings.retrieval.reranking.num_parallel_workers
        self.worker_timeout = settings.retrieval.reranking.worker_timeout_seconds
        self.max_concurrent = settings.retrieval.reranking.max_concurrent_calls
        self.score_threshold = settings.retrieval.reranking.score_threshold
        self.entity_filter_enabled = settings.retrieval.reranking.entity_filter.enabled
        self.min_entity_match_ratio = (
            settings.retrieval.reranking.entity_filter.min_entity_match_ratio
        )

    async def rerank(
        self,
        query: str,
        chunks: List[ChunkSearchResult],
        top_n: int | None = None,
        entities: Dict[str, List[str]] | None = None,
        *,
        score_threshold: int | None = None,
        enable_entity_filter: bool | None = None,
    ) -> List[ChunkSearchResult]:
        """
        Rerank chunks using parallel LLM workers with round-robin batching.

        Args:
            query: Original query (Facebook post or claim)
            chunks: List of chunks to rerank (typically top 100 from RRF)
            top_n: Number of top chunks to return (defaults to config value)
            entities: Dictionary of entities extracted from query (optional)
                     Format: {"persons": ["A", "B"], "organizations": ["X"]}

        Returns:
            Reranked list of chunks (top_n), sorted by LLM relevance score
        """
        if top_n is None:
            top_n = self.top_n

        if not chunks:
            return []

        effective_score_threshold = (
            int(score_threshold)
            if score_threshold is not None
            else self.score_threshold
        )
        effective_entity_filter_enabled = (
            bool(enable_entity_filter)
            if enable_entity_filter is not None
            else self.entity_filter_enabled
        )

        logger.info(
            f"Reranking {len(chunks)} chunks with {self.num_workers} parallel workers"
        )

        # Apply entity filtering if enabled and entities are provided
        if effective_entity_filter_enabled and entities:
            chunks = self._filter_chunks_by_entities(chunks, entities)
            logger.info(
                f"Entity filtering: {len(chunks)} chunks remaining after filtering"
            )

            if not chunks:
                logger.warning("No chunks passed entity filter. Returning empty list.")
                return []

        # Split chunks across workers (round-robin, original indices preserved so
        # scores merge back deterministically) and rate-limit concurrent calls.
        batches = round_robin_batches(chunks, self.num_workers)
        semaphore = asyncio.Semaphore(self.max_concurrent)

        worker_results = await run_worker_batches(
            batches,
            lambda worker_id, batch: self._score_worker_batch(
                query,
                batch,
                worker_id,
                semaphore,
                score_threshold=effective_score_threshold,
            ),
        )

        # Merge scores from all workers
        chunk_scores = self._merge_worker_scores(chunks, worker_results)

        # Filter by score threshold and normalize
        filtered_chunks = self._filter_and_normalize_scores(
            chunks, chunk_scores, score_threshold=effective_score_threshold
        )

        # Sort by score (descending) and return top_n
        filtered_chunks.sort(key=lambda x: x.score, reverse=True)

        logger.info(
            f"Reranking complete: {len(chunks)} → {len(filtered_chunks)} above threshold → top {top_n} returned"
        )

        return filtered_chunks[:top_n]

    async def _score_worker_batch(
        self,
        query: str,
        batch: IndexedBatch,
        worker_id: int,
        semaphore: asyncio.Semaphore,
        *,
        score_threshold: int,
    ) -> dict:
        """
        Score a batch of chunks assigned to one worker with timeout and rate limiting.

        Args:
            query: Original query
            batch: List of (global_index, chunk) tuples for this worker
            worker_id: Worker identifier for logging
            semaphore: Semaphore for rate limiting concurrent API calls

        Returns:
            Dict with the batch's global indices and scores (scores is None on
            timeout/error, signalling the merge step to keep fallback scores).
        """
        if not batch:
            return {"indices": [], "scores": []}

        indices = [idx for idx, _ in batch]
        chunks = [chunk for _, chunk in batch]

        try:
            async with semaphore:
                # Apply timeout to prevent long tail latency
                scores = await asyncio.wait_for(
                    self._score_batch(
                        query, chunks, worker_id, score_threshold=score_threshold
                    ),
                    timeout=self.worker_timeout,
                )

            logger.debug(f"Worker {worker_id} completed: {len(chunks)} chunks scored")

            return {"indices": indices, "scores": scores}

        except asyncio.TimeoutError:
            logger.warning(
                f"Worker {worker_id} timed out after {self.worker_timeout}s. "
                f"Will use fallback scores for {len(chunks)} chunks."
            )
            return {"indices": indices, "scores": None}  # Sentinel for timeout
        except Exception as e:
            logger.error(
                f"Worker {worker_id} failed with error: {e}. "
                f"Will use fallback scores for {len(chunks)} chunks."
            )
            return {"indices": indices, "scores": None}  # Sentinel for error

    async def _score_batch(
        self,
        query: str,
        chunks: List[ChunkSearchResult],
        worker_id: int,
        *,
        score_threshold: int,
    ) -> List[float]:
        """
        Score a batch of chunks in a single API call.

        Args:
            query: Original query
            chunks: Batch of chunks to score
            worker_id: Worker identifier for logging

        Returns:
            List of scores (one per chunk, or empty if all filtered)
        """
        prompt = self._build_parallel_scoring_prompt(
            query, chunks, score_threshold=score_threshold
        )

        try:
            # Call LLM with JSON mode for structured output
            messages = [LLMMessage(role="user", content=prompt)]
            response = await self.llm.generate_completion(
                messages=messages,
                model=self.model,
                temperature=0,  # Deterministic output
                response_format={"type": "json_object"},
            )

            # Parse JSON response
            result = json.loads(response.content)

            # Convert passage ID scores to list (handle sparse scores from threshold filtering)
            scores = []
            for i in range(len(chunks)):
                passage_id = f"id{i}"
                score = result.get(passage_id, None)
                scores.append(score if score is not None else 0.0)

            logger.debug(
                f"Worker {worker_id} scored {len(chunks)} chunks: "
                f"{sum(1 for s in scores if s >= score_threshold)} above threshold"
            )

            return scores

        except json.JSONDecodeError as e:
            logger.error(
                f"Worker {worker_id} failed to parse scoring response as JSON: {e}"
            )
            raise
        except Exception as e:
            logger.error(f"Worker {worker_id} error during scoring: {e}")
            raise

    def _merge_worker_scores(
        self, chunks: List[ChunkSearchResult], worker_results: List[dict]
    ) -> List[float]:
        """
        Merge scores from all workers, using fallback RRF scores for timeouts/errors.

        Args:
            chunks: Original list of all chunks
            worker_results: Results from each worker (each carrying the batch's
                global indices and scores), possibly including Exception objects
                for workers that raised.

        Returns:
            List of final scores (one per chunk, in original order)
        """
        # Initialize with fallback scores (use original RRF scores)
        final_scores = [chunk.score for chunk in chunks]

        # Merge scores from successful workers using each item's global index
        for result in worker_results:
            if isinstance(result, Exception):
                logger.debug(f"Worker raised, using fallback scores: {result}")
                continue

            indices = result["indices"]
            scores = result["scores"]

            if scores is None:
                # Worker timed out or failed - keep fallback scores
                logger.debug(f"Worker used fallback scores for {len(indices)} chunks")
                continue

            # Update with LLM scores (keep in 0-10 scale)
            for global_idx, score in zip(indices, scores):
                if global_idx < len(chunks):  # Safety check
                    final_scores[global_idx] = float(score)

        return final_scores

    def _filter_and_normalize_scores(
        self,
        chunks: List[ChunkSearchResult],
        scores: List[float],
        *,
        score_threshold: int,
    ) -> List[ChunkSearchResult]:
        """
        Filter chunks by score threshold and create new ChunkSearchResult objects.

        Args:
            chunks: Original chunks
            scores: LLM scores (0-10 scale)

        Returns:
            List of chunks with scores >= threshold
        """
        filtered_chunks = []
        for chunk, score in zip(chunks, scores):
            if score >= score_threshold:
                reranked_chunk = ChunkSearchResult(
                    chunk_id=chunk.chunk_id,
                    chunk_text=chunk.chunk_text,
                    chunk_index=chunk.chunk_index,
                    article_id=chunk.article_id,
                    article_title=chunk.article_title,
                    source_name=chunk.source_name,
                    score=score,  # Keep in 0-10 scale
                )
                filtered_chunks.append(reranked_chunk)

        return filtered_chunks

    def _build_parallel_scoring_prompt(
        self, query: str, chunks: List[ChunkSearchResult], *, score_threshold: int
    ) -> str:
        """
        Build prompt for parallel worker scoring with Intercom-style grading rubric.

        Based on Intercom's LLM reranker prompt optimized for quality and consistency.

        Args:
            query: Original query
            chunks: Batch of chunks to score

        Returns:
            Prompt string with detailed grading criteria
        """
        # Build passages in XML format for clarity
        passages = []
        for i, chunk in enumerate(chunks):
            # Truncate long chunks to fit in context
            chunk_text = chunk.chunk_text[:500]  # Keep first 500 chars
            passages.append(f"<passage id='id{i}'>{chunk_text}</passage>")

        passages_text = "\n".join(passages)

        prompt = f"""You are evaluating news article passages for a fact-checking system. Score how relevant each passage is for verifying the given social media post.

Evaluation Process:
1. Identify key elements in the query: people, organizations, topics, events
2. Check if each passage discusses related content that could help verify the claim
3. Score based on relevance and usefulness for fact-checking

Grading Criteria (0-10 scale):
<grading_scale>
10: PERFECT match - Passage directly addresses the EXACT claim/event in the query with all key details matching.

9: EXCELLENT - Discusses the same event/topic with most details matching. Highly useful for verification.

8: VERY GOOD - About the same topic/entity with substantial relevant information. Minor details may differ.

7: GOOD - Discusses the same general topic with useful context. May cover related aspects.

6: RELEVANT - About the same entity/topic but different specific aspect. Still useful background.

5: SOMEWHAT RELEVANT - Mentions same key entities with some useful context. Partially helpful.

4: MARGINALLY RELEVANT - Shares main entities but limited useful overlap. Minimal verification value.

3: WEAKLY RELATED - Mentions related concepts but mostly different topic.

2: BARELY RELATED - Shares some keywords but different context entirely.

1: NOT RELEVANT - No meaningful connection to the query topic.

0: COMPLETELY UNRELATED - No thematic connection whatsoever.
</grading_scale>

IMPORTANT GUIDELINES:
- Score based on USEFULNESS for fact-checking, not just keyword matching
- Passages about the SAME person/organization on RELATED topics should score 5-7
- Passages about the EXACT SAME event should score 8-10
- Only score 0-2 if truly unrelated (different people, different topics entirely)

Input Format:
<query>
{query}
</query>
<passages>
{passages_text}
</passages>

Output Format:
Return your response in a valid JSON (skip spaces):
{{"id0":score0,"id1":score1,...}}

Strict guidelines:
- Return ONLY a well-formed valid JSON with passage IDs as keys
- Each key must be a passage id in the format "idN"
- Each score must be an integer between {score_threshold} to 10. EXCLUDE passages that score below {score_threshold} (i.e. 0-{score_threshold - 1})
- Integer values only, no decimals
- Skip spaces in the JSON
- No additional text or formatting
- Maintain original passage ID order
- If no passages score {score_threshold}+, return empty JSON: {{}}"""

        return prompt

    def _filter_chunks_by_entities(
        self, chunks: List[ChunkSearchResult], entities: Dict[str, List[str]]
    ) -> List[ChunkSearchResult]:
        """
        Filter chunks based on entity matching at the article level.

        Groups chunks by article, checks if any chunk in the article contains
        the required entities, and keeps all chunks from articles that pass.
        This preserves full article context while filtering unrelated articles.

        Args:
            chunks: List of chunks to filter
            entities: Dictionary of entities from query extraction
                     Format: {"persons": ["A"], "organizations": ["X"], "locations": ["Y"]}

        Returns:
            Filtered list of chunks from articles that pass the entity matching threshold
        """
        if not entities:
            return chunks

        # Flatten all entities into a single list
        all_entities = []
        for entity_list in entities.values():
            all_entities.extend(entity_list)

        if not all_entities:
            return chunks

        logger.debug(
            f"Filtering chunks with {len(all_entities)} entities: {all_entities[:5]}..."
        )

        # Group chunks by article_id
        article_chunks: Dict[str, List[ChunkSearchResult]] = {}
        for chunk in chunks:
            article_key = chunk.article_id.hex
            if article_key not in article_chunks:
                article_chunks[article_key] = []
            article_chunks[article_key].append(chunk)

        # For each article, check if ANY chunk contains entities
        # If article passes, keep ALL its chunks
        filtered_chunks = []
        passed_articles = 0

        for article_key, article_chunk_list in article_chunks.items():
            # Combine all chunk texts for entity matching
            combined_text = " ".join(chunk.chunk_text for chunk in article_chunk_list)

            # Also include article title in matching (available in chunks)
            if article_chunk_list and article_chunk_list[0].article_title:
                combined_text = (
                    article_chunk_list[0].article_title + " " + combined_text
                )

            match_ratio = self._calculate_entity_match_ratio(
                combined_text, all_entities
            )

            if match_ratio >= self.min_entity_match_ratio:
                passed_articles += 1
                filtered_chunks.extend(article_chunk_list)
                logger.debug(
                    f"Article {article_key} ({article_chunk_list[0].article_title}) passed entity filter "
                    f"(ratio: {match_ratio:.1%}, chunks: {len(article_chunk_list)})"
                )

        logger.debug(
            f"Entity filter: {passed_articles}/{len(article_chunks)} articles passed, "
            f"{len(filtered_chunks)}/{len(chunks)} chunks kept "
            f"(threshold: {self.min_entity_match_ratio:.1%})"
        )

        return filtered_chunks

    def _calculate_entity_match_ratio(self, text: str, entities: List[str]) -> float:
        """
        Calculate the ratio of entities that appear in the text.

        Uses case-insensitive substring matching for Vietnamese compatibility.

        Args:
            text: Chunk text to search in
            entities: List of entity strings to search for

        Returns:
            Ratio of matched entities (0.0 to 1.0)
        """
        if not entities:
            return 1.0  # No entities = no filtering needed

        # Normalize text for matching (lowercase, remove extra whitespace)
        normalized_text = re.sub(r"\s+", " ", text.lower())

        matched_count = 0
        valid_entity_count = 0

        for entity in entities:
            # Normalize entity
            normalized_entity = entity.lower().strip()

            if not normalized_entity:
                continue

            valid_entity_count += 1

            # Use simple substring matching for Vietnamese compatibility
            # Word boundaries don't work well with Vietnamese text
            if normalized_entity in normalized_text:
                matched_count += 1

        if valid_entity_count == 0:
            return 1.0  # No valid entities = no filtering needed

        return matched_count / valid_entity_count
