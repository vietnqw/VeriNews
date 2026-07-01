"""
Retrieval Orchestrator

Orchestrates the full two-stage hybrid retrieval pipeline.
"""

import time
from typing import Dict, List, Tuple

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.logging import get_logger
from app.services.content.embedding_service import generate_embeddings_batch
from app.services.retrieval.article_aggregation_service import (
    ArticleAggregationService,
)
from app.services.retrieval.article_reranker_service import ArticleRerankerService
from app.services.retrieval.confidence_scoring_service import (
    ConfidenceScoringService,
)
from app.services.retrieval.fusion_service import FusionService
from app.services.retrieval.hybrid_retrieval_service import HybridRetrievalService
from app.services.retrieval.query_extraction_service import QueryExtractionService
from app.services.retrieval.reranker_service import RerankerService

logger = get_logger(__name__)


class RetrievalOrchestrator:
    """
    Main orchestrator for the enhanced hybrid retrieval pipeline with article-level validation.

    Pipeline stages:
    1. Query Extraction: Extract clean query + claims from Facebook post
    2. Batch Embedding: Generate embeddings for all queries
    3. Multi-Query Hybrid Search: Run vector + BM25 for each query (parallel)
    4. RRF Fusion: Merge all result lists using Reciprocal Rank Fusion
    5. Chunk Reranking: Score top 100 chunks using LLM (batch-optimized)
    6. Aggregation: Convert chunks to article-level results with multi-threshold filtering
    7. Article Reranking: Score articles using LLM to validate main topic relevance (NEW)
    8. Confidence Scoring: Multi-signal validation to detect irrelevant results (NEW)
    9. Final Validation: Reject low-confidence results (NEW)

    Returns article-level results with timing breakdowns and confidence metrics.
    """

    def __init__(self, session: AsyncSession, on_stage_complete=None):
        self.session = session
        self.query_service = QueryExtractionService()
        self.hybrid_service = HybridRetrievalService(session)
        self.fusion_service = FusionService()
        self.reranker_service = RerankerService()
        self.aggregation_service = ArticleAggregationService(db=session)
        self.article_reranker_service = ArticleRerankerService()
        self.confidence_service = ConfidenceScoringService()
        self.on_stage_complete = (
            on_stage_complete  # Callback for stage completion events
        )

    async def _emit_stage(self, stage_name: str):
        """Emit a stage completion event if callback is registered."""
        if self.on_stage_complete:
            await self.on_stage_complete(stage_name)

    async def retrieve(self, post_text: str) -> Dict:
        """
        Execute the full retrieval pipeline.

        Args:
            post_text: Facebook post text to verify

        Returns:
            Dictionary with:
            - articles: List of ArticleResult objects
            - total_time_ms: Total pipeline time in milliseconds
            - stage_timings: Breakdown by stage
            - query_count: Number of queries processed
        """
        start_time = time.time()
        timings: Dict[str, float] = {}

        logger.info(f"Starting retrieval pipeline for post: {post_text[:100]}...")

        # Stage 1: Query Extraction (shared for strict + fallback)
        t1 = time.time()
        if settings.retrieval.query_extraction.enabled:
            extracted = await self.query_service.extract_queries(post_text)
            clean_query = extracted["clean_query"]
            claims = extracted["claims"]
            query_count = extracted["query_count"]
            factual_confidence = extracted.get("factual_confidence", 10.0)
            entities = extracted.get("entities", {})
        else:
            # Fallback: Use original post as single query
            clean_query = post_text.strip()
            claims = []
            query_count = 1
            factual_confidence = 10.0
            entities = {}

        timings["query_extraction"] = (time.time() - t1) * 1000
        logger.info(
            f"Query extraction: {query_count} queries, "
            f"confidence: {factual_confidence:.2f} ({timings['query_extraction']:.2f}ms)"
        )

        # Early exit for low-confidence posts (do not run fallback)
        min_confidence = settings.retrieval.query_extraction.min_factual_confidence
        if factual_confidence < min_confidence:
            total_time = (time.time() - start_time) * 1000
            logger.info(
                f"Early exit: factual_confidence {factual_confidence:.2f} < threshold {min_confidence:.2f}"
            )
            return {
                "articles": [],
                "total_time_ms": int(total_time),
                "stage_timings": timings,
                "query_count": query_count,
                "claims": claims,
                "factual_confidence": factual_confidence,
                "early_exit": True,
                "exit_reason": "LOW_CONFIDENCE",
                "message": "Post does not contain sufficient verifiable factual content",
            }

        # Stage 2: Batch Embedding
        t2 = time.time()
        query_texts = [clean_query] + claims
        embeddings = await generate_embeddings_batch(query_texts)

        # Optional: Filter redundant claims based on similarity
        if (
            settings.retrieval.query_extraction.enable_similarity_filter
            and len(claims) > 0
        ):
            filtered_texts, filtered_embeddings = self._filter_redundant_claims(
                query_texts, embeddings
            )
            logger.info(
                f"Similarity filtering: {len(query_texts)} → {len(filtered_texts)} queries "
                f"(removed {len(query_texts) - len(filtered_texts)} redundant claims)"
            )
            query_texts = filtered_texts
            embeddings = filtered_embeddings

        queries = list(zip(query_texts, embeddings))  # [(text, embedding), ...]

        timings["embedding"] = (time.time() - t2) * 1000
        logger.info(
            f"Batch embedding: {len(query_texts)} queries ({timings['embedding']:.2f}ms)"
        )

        # Emit: Stage 1 complete (Query Extraction)
        await self._emit_stage("query_extraction")

        # Pass 1: Strict (current behavior)
        strict_res = await self._run_retrieval_pass(
            post_text=post_text,
            queries=queries,
            entities=entities,
            timings=timings,
            pass_name="strict",
            enable_entity_filter=True,
            rerank_score_threshold=settings.retrieval.reranking.score_threshold,
            enable_article_rerank=True,
            apply_confidence_gate=True,
        )

        # Pass 2: Fallback "related" mode if strict yields empty
        fallback_used = False
        final_res = strict_res
        if not strict_res.get("articles"):
            fallback_used = True
            logger.info(
                "Strict retrieval returned no articles; running fallback related-mode retrieval"
            )
            final_res = await self._run_retrieval_pass(
                post_text=post_text,
                queries=queries,
                entities=entities,
                timings=timings,
                pass_name="fallback",
                enable_entity_filter=False,  # key: do not require entity overlap
                # allow broader related chunks
                rerank_score_threshold=settings.retrieval.fallback.rerank_score_threshold,
                enable_article_rerank=False,  # avoid strict 'different location/time' gating
                apply_confidence_gate=False,  # never hard-zero in fallback
            )

        total_time = (time.time() - start_time) * 1000
        confidence_metrics = final_res.get("confidence_metrics")
        articles = final_res.get("articles", [])

        # In fallback mode, always warn the user these are "related"
        low_confidence_warning = (
            bool(final_res.get("low_confidence_warning")) or fallback_used
        )
        message = None
        if fallback_used and articles:
            message = (
                "Không tìm thấy bài báo khớp chính xác với các chi tiết cụ thể trong bài đăng. "
                "Dưới đây là các bài báo LIÊN QUAN nhất để bạn tham khảo."
            )
        elif final_res.get("low_confidence_warning"):
            message = (
                "These articles may not be directly related to your specific claim. "
                "Results show the closest available matches."
            )

        # If strict failed and fallback still found nothing, keep the old behavior
        if fallback_used and not articles:
            logger.info("Fallback retrieval also returned no articles.")
            return {
                "articles": [],
                "total_time_ms": int(total_time),
                "stage_timings": timings,
                "query_count": query_count,
                "claims": claims,
                "factual_confidence": factual_confidence,
                "retrieval_confidence": (
                    confidence_metrics.overall_confidence if confidence_metrics else 0.0
                )
                if confidence_metrics
                else 0.0,
                "confidence_metrics": (
                    confidence_metrics.to_dict() if confidence_metrics else None
                ),
                "early_exit": True,
                "exit_reason": "NO_RELEVANT_ARTICLES",
                "message": "No articles found that match the specific claim in your post",
            }

        logger.info(
            f"Pipeline complete: {len(articles)} articles in {total_time:.2f}ms "
            f"(fallback_used={fallback_used})"
        )

        return {
            "articles": articles,
            "total_time_ms": int(total_time),
            "stage_timings": timings,
            "query_count": query_count,
            "claims": claims,
            "factual_confidence": factual_confidence,
            "retrieval_confidence": (
                confidence_metrics.overall_confidence if confidence_metrics else None
            ),
            "confidence_metrics": (
                confidence_metrics.to_dict() if confidence_metrics else None
            ),
            "low_confidence_warning": low_confidence_warning,
            "early_exit": False,
            "message": message,
        }

    async def _run_retrieval_pass(
        self,
        *,
        post_text: str,
        queries: List[Tuple[str, List[float]]],
        entities: Dict,
        timings: Dict[str, float],
        pass_name: str,
        enable_entity_filter: bool,
        rerank_score_threshold: int,
        enable_article_rerank: bool,
        apply_confidence_gate: bool,
    ) -> Dict:
        """
        Run a single retrieval pass (stages 3-9) with configurable strictness.

        This enables a fallback mode: if the strict pass returns no matches, the
        caller reruns a more recall-oriented pass and returns "related" articles.
        ``timings`` is mutated in place with per-stage timings keyed by pass name.
        """
        # Stage 3: Multi-Query Hybrid Search
        t3 = time.time()
        all_result_lists = await self.hybrid_service.search_multi_query(
            queries, top_k=100
        )
        timings[f"hybrid_search:{pass_name}"] = (time.time() - t3) * 1000

        # Stage 4: RRF Fusion
        t4 = time.time()
        fused_chunks = self.fusion_service.reciprocal_rank_fusion(all_result_lists)
        timings[f"fusion:{pass_name}"] = (time.time() - t4) * 1000

        # Stage 5: Reranking
        t5 = time.time()
        reranked_chunks = []
        if settings.retrieval.reranking.enabled and fused_chunks:
            top_chunks_for_reranking = fused_chunks[:100]
            reranked_chunks = await self.reranker_service.rerank(
                post_text,
                top_chunks_for_reranking,
                top_n=10,
                entities=entities,
                enable_entity_filter=enable_entity_filter,
                score_threshold=rerank_score_threshold,
            )
        timings[f"reranking:{pass_name}"] = (time.time() - t5) * 1000

        # Stage 6: Article Aggregation
        t6 = time.time()
        articles = await self.aggregation_service.aggregate_to_articles(reranked_chunks)
        timings[f"aggregation:{pass_name}"] = (time.time() - t6) * 1000

        # Stage 7: Article-level reranking (optional)
        t7 = time.time()
        if (
            enable_article_rerank
            and settings.retrieval.reranking.article_level.enabled
            and len(articles) > 0
        ):
            articles = await self.article_reranker_service.rerank_articles(
                query=post_text, articles=articles, top_n=10
            )
        timings[f"article_reranking:{pass_name}"] = (time.time() - t7) * 1000

        # Emit: Stage 2 complete (Search & Retrieval) once (first pass only)
        if pass_name == "strict":
            await self._emit_stage("search")

        # Stage 8: Confidence scoring
        t8 = time.time()
        confidence_metrics = None
        if settings.retrieval.confidence_scoring.enabled:
            confidence_metrics = await self.confidence_service.calculate_confidence(
                articles=articles, query_text=post_text, query_entities=entities
            )
        timings[f"confidence_scoring:{pass_name}"] = (time.time() - t8) * 1000

        # Stage 9: Optional final validation gate
        min_conf = settings.retrieval.confidence_scoring.min_confidence_threshold
        if (
            apply_confidence_gate
            and confidence_metrics
            and confidence_metrics.overall_confidence < min_conf
        ):
            return {
                "articles": [],
                "confidence_metrics": confidence_metrics,
                "retrieval_confidence": confidence_metrics.overall_confidence,
                "early_exit": True,
                "exit_reason": "NO_RELEVANT_ARTICLES",
            }

        low_confidence_warning = (
            confidence_metrics
            and confidence_metrics.confidence_tier in ["LOW", "MEDIUM"]
            and len(articles) > 0
        )

        return {
            "articles": articles,
            "confidence_metrics": confidence_metrics,
            "retrieval_confidence": (
                confidence_metrics.overall_confidence if confidence_metrics else None
            ),
            "low_confidence_warning": low_confidence_warning,
            "early_exit": False,
            "exit_reason": None,
        }

    def _filter_redundant_claims(
        self, query_texts: List[str], embeddings: List[List[float]]
    ) -> Tuple[List[str], List[List[float]]]:
        """
        Filter redundant claims based on cosine similarity to clean_query.

        Args:
            query_texts: List of [clean_query, claim1, claim2, ...]
            embeddings: Corresponding embeddings

        Returns:
            Tuple of (filtered_texts, filtered_embeddings) with redundant claims removed
        """
        if len(query_texts) <= 1:
            return query_texts, embeddings

        threshold = settings.retrieval.query_extraction.similarity_threshold

        # Always keep clean_query (first element)
        filtered_texts = [query_texts[0]]
        filtered_embeddings = [embeddings[0]]

        clean_query_embedding = np.array(embeddings[0])

        # Check each claim against clean_query
        for i in range(1, len(query_texts)):
            claim_text = query_texts[i]
            claim_embedding = np.array(embeddings[i])

            # Compute cosine similarity
            similarity = np.dot(clean_query_embedding, claim_embedding) / (
                np.linalg.norm(clean_query_embedding) * np.linalg.norm(claim_embedding)
            )

            if similarity < threshold:
                # Keep claim (not redundant)
                filtered_texts.append(claim_text)
                filtered_embeddings.append(embeddings[i])
            else:
                logger.debug(
                    f"Filtered redundant claim (similarity={similarity:.3f}): {claim_text[:100]}"
                )

        return filtered_texts, filtered_embeddings
