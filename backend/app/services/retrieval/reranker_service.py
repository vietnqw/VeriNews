"""
Reranking Service

Reranks retrieved chunks using OpenAI LLM for higher precision.
Uses batch scoring to minimize latency.
"""

import asyncio
import json
from typing import List

from app.config.settings import settings
from app.core.logging import get_logger
from app.services.ai.base import LLMMessage
from app.services.ai.factory import AIServiceFactory
from app.services.retrieval.bm25_search_service import ChunkSearchResult

logger = get_logger(__name__)


class RerankerService:
    """
    OpenAI-based reranking service with batch optimization.

    Reranks chunks by scoring their relevance to the original query using an LLM.
    Batches multiple chunks per API call to reduce latency and cost.
    """

    def __init__(self):
        self.llm = AIServiceFactory.get_llm_provider()
        self.model = settings.ai.llm_model
        self.top_n = settings.retrieval.reranking.top_n
        self.batch_size = settings.retrieval.reranking.batch_size
        self.score_range = settings.retrieval.reranking.score_range

    async def rerank(
        self,
        query: str,
        chunks: List[ChunkSearchResult],
        top_n: int | None = None,
    ) -> List[ChunkSearchResult]:
        """
        Rerank chunks using OpenAI LLM.

        Args:
            query: Original query (Facebook post or claim)
            chunks: List of chunks to rerank (typically top 100 from RRF)
            top_n: Number of top chunks to return (defaults to config value)

        Returns:
            Reranked list of chunks (top_n), sorted by LLM relevance score
        """
        if top_n is None:
            top_n = self.top_n

        if not chunks:
            return []

        logger.info(f"Reranking {len(chunks)} chunks (batch_size={self.batch_size})")

        # Split chunks into batches
        batches = [
            chunks[i : i + self.batch_size]
            for i in range(0, len(chunks), self.batch_size)
        ]

        # Score all batches in parallel
        all_scores_tasks = [self._score_batch(query, batch) for batch in batches]
        all_scores_lists = await asyncio.gather(*all_scores_tasks)

        # Flatten scores
        all_scores = []
        for scores_list in all_scores_lists:
            all_scores.extend(scores_list)

        # Normalize scores to 0-1 range
        min_score, max_score = self.score_range
        normalized_scores = [
            (score - min_score) / (max_score - min_score) for score in all_scores
        ]

        # Create reranked chunks with new scores
        reranked_chunks = []
        for chunk, score in zip(chunks, normalized_scores):
            reranked_chunk = ChunkSearchResult(
                chunk_id=chunk.chunk_id,
                chunk_text=chunk.chunk_text,
                chunk_index=chunk.chunk_index,
                article_id=chunk.article_id,
                article_title=chunk.article_title,
                source_name=chunk.source_name,
                score=score,  # Replace with normalized LLM score
            )
            reranked_chunks.append(reranked_chunk)

        # Sort by score (descending) and return top_n
        reranked_chunks.sort(key=lambda x: x.score, reverse=True)

        logger.info(
            f"Reranking complete: {len(reranked_chunks)} chunks → top {top_n} returned"
        )

        return reranked_chunks[:top_n]

    async def _score_batch(
        self, query: str, chunks: List[ChunkSearchResult]
    ) -> List[float]:
        """
        Score a batch of chunks in a single API call.

        Args:
            query: Original query
            chunks: Batch of chunks to score

        Returns:
            List of scores (one per chunk)
        """
        prompt = self._build_batch_scoring_prompt(query, chunks)

        try:
            # Call LLM with JSON mode for structured output
            messages = [LLMMessage(role="user", content=prompt)]
            response = await self.llm.generate_completion(
                messages=messages,
                model=self.model,
                temperature=0.1,  # Low temperature for consistent scoring
                response_format={"type": "json_object"},
            )

            # Parse JSON response
            result = json.loads(response.content)
            scores = result.get("scores", [])

            # Validate score count
            if len(scores) != len(chunks):
                logger.warning(
                    f"Expected {len(chunks)} scores, got {len(scores)}. Padding with zeros."
                )
                # Pad with zeros if needed
                while len(scores) < len(chunks):
                    scores.append(0)

            logger.debug(f"Scored batch of {len(chunks)} chunks")

            return scores

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse batch scoring response as JSON: {e}")
            # Return zeros as fallback
            return [0.0] * len(chunks)
        except Exception as e:
            logger.error(f"Error during batch scoring: {e}")
            # Return zeros as fallback
            return [0.0] * len(chunks)

    def _build_batch_scoring_prompt(
        self, query: str, chunks: List[ChunkSearchResult]
    ) -> str:
        """
        Build prompt for batch scoring.

        Args:
            query: Original query
            chunks: Batch of chunks to score

        Returns:
            Prompt string
        """
        min_score, max_score = self.score_range
        n_chunks = len(chunks)

        # Build chunk list for prompt
        chunk_list = []
        for i, chunk in enumerate(chunks):
            # Truncate long chunks to fit in context
            chunk_text = chunk.chunk_text[:500]  # Keep first 500 chars
            chunk_list.append(f"Chunk {i}: {chunk_text}")

        chunks_text = "\n\n".join(chunk_list)

        prompt = f"""You are a relevance scoring assistant for a news verification system.

Your task is to score how relevant each chunk is to the given query.

Query: "{query}"

Total chunks: {n_chunks}

Chunks to score:
{chunks_text}

Instructions:
- Score EACH AND EVERY chunk from {min_score} to {max_score} (inclusive) based on relevance to the query.
- The output MUST contain EXACTLY {n_chunks} scores, one for each chunk in order (Chunk 0 .. Chunk {n_chunks - 1}). Do not skip any chunk.
- If a chunk is not relevant or cannot be judged, still include a score using the minimum value {min_score}.
- Higher scores mean more relevant.
- Consider semantic similarity, topic match, and factual alignment.
- Be precise and consistent.
- Output STRICT JSON ONLY with no comments or trailing text.
- JSON must match these constraints (conceptual schema):
  {{
    "type": "object",
    "properties": {{
      "scores": {{
        "type": "array",
        "items": {{"type": "number"}},
        "minItems": {n_chunks},
        "maxItems": {n_chunks}
      }}
    }},
    "required": ["scores"],
    "additionalProperties": false
  }}
- Before returning, VERIFY that length(scores) == {n_chunks}. If not, add missing items with {min_score} at the end to reach EXACTLY {n_chunks} items.

Return your scores as a JSON object with a "scores" array (one score per chunk, in order):
{{
  "scores": [score_for_chunk_0, score_for_chunk_1, ..., score_for_chunk_{n_chunks - 1}]
}}
"""
        return prompt
