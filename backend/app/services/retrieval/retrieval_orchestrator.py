"""
Retrieval Orchestrator

Orchestrates the full two-stage hybrid retrieval pipeline.
"""

import time
from typing import Dict

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.logging import get_logger
from app.services.content.embedding_service import generate_embeddings_batch
from app.services.retrieval.article_aggregation_service import (
    ArticleAggregationService,
)
from app.services.retrieval.fusion_service import FusionService
from app.services.retrieval.hybrid_retrieval_service import HybridRetrievalService
from app.services.retrieval.query_extraction_service import QueryExtractionService
from app.services.retrieval.reranker_service import RerankerService

logger = get_logger(__name__)


class RetrievalOrchestrator:
    """
    Main orchestrator for the two-stage hybrid retrieval pipeline.

    Pipeline stages:
    1. Query Extraction: Extract clean query + claims from Facebook post
    2. Batch Embedding: Generate embeddings for all queries
    3. Multi-Query Hybrid Search: Run vector + BM25 for each query (parallel)
    4. RRF Fusion: Merge all result lists using Reciprocal Rank Fusion
    5. Reranking: Score top 100 chunks using LLM (batch-optimized)
    6. Aggregation: Convert chunks to article-level results

    Returns article-level results with timing breakdowns.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.query_service = QueryExtractionService()
        self.hybrid_service = HybridRetrievalService(session)
        self.fusion_service = FusionService()
        self.reranker_service = RerankerService()
        self.aggregation_service = ArticleAggregationService()

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
        timings = {}

        logger.info(f"Starting retrieval pipeline for post: {post_text[:100]}...")

        # Stage 1: Query Extraction
        t1 = time.time()
        if settings.retrieval.query_extraction.enabled:
            extracted = await self.query_service.extract_queries(post_text)
            clean_query = extracted["clean_query"]
            claims = extracted["claims"]
            query_count = extracted["query_count"]
        else:
            # Fallback: Use original post as single query
            clean_query = post_text.strip()
            claims = []
            query_count = 1

        timings["query_extraction"] = (time.time() - t1) * 1000
        logger.info(
            f"Query extraction: {query_count} queries ({timings['query_extraction']:.2f}ms)"
        )

        # Stage 2: Batch Embedding
        t2 = time.time()
        query_texts = [clean_query] + claims
        embeddings = await generate_embeddings_batch(query_texts)
        queries = list(zip(query_texts, embeddings))  # [(text, embedding), ...]

        timings["embedding"] = (time.time() - t2) * 1000
        logger.info(
            f"Batch embedding: {len(query_texts)} queries ({timings['embedding']:.2f}ms)"
        )

        # Stage 3: Multi-Query Hybrid Search
        t3 = time.time()
        all_result_lists = await self.hybrid_service.search_multi_query(
            queries, top_k=100
        )

        timings["hybrid_search"] = (time.time() - t3) * 1000
        logger.info(
            f"Hybrid search: {len(all_result_lists)} result lists ({timings['hybrid_search']:.2f}ms)"
        )

        # Stage 4: RRF Fusion
        t4 = time.time()
        fused_chunks = self.fusion_service.reciprocal_rank_fusion(all_result_lists)

        timings["fusion"] = (time.time() - t4) * 1000
        logger.info(
            f"RRF fusion: {len(fused_chunks)} unique chunks ({timings['fusion']:.2f}ms)"
        )

        # Stage 5: Reranking (if enabled)
        t5 = time.time()
        if settings.retrieval.reranking.enabled and fused_chunks:
            # Rerank top 100 chunks
            top_chunks_for_reranking = fused_chunks[:100]
            reranked_chunks = await self.reranker_service.rerank(
                post_text, top_chunks_for_reranking, top_n=10
            )
        else:
            # Skip reranking, use top 10 from fusion
            reranked_chunks = fused_chunks[:10]

        timings["reranking"] = (time.time() - t5) * 1000
        logger.info(
            f"Reranking: {len(reranked_chunks)} final chunks ({timings['reranking']:.2f}ms)"
        )

        # Stage 6: Article Aggregation
        t6 = time.time()
        articles = self.aggregation_service.aggregate_to_articles(reranked_chunks)

        timings["aggregation"] = (time.time() - t6) * 1000
        logger.info(
            f"Aggregation: {len(articles)} articles ({timings['aggregation']:.2f}ms)"
        )

        total_time = (time.time() - start_time) * 1000

        logger.info(
            f"Pipeline complete: {len(articles)} articles in {total_time:.2f}ms"
        )

        return {
            "articles": articles,
            "total_time_ms": int(total_time),
            "stage_timings": timings,
            "query_count": query_count,
        }
