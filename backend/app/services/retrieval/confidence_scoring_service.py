"""
Confidence Scoring Service

Calculates multi-signal confidence metrics to determine whether retrieved articles
truly match the user's query. Helps detect when NO relevant articles exist and
prevents returning low-quality results.

Uses multiple signals:
- Top article score (quality)
- Score gap between #1 and #2 (distinctiveness)
- Entity coverage (completeness)
- Temporal/spatial alignment (specificity)
- Title-query similarity (topicality)
"""

from dataclasses import dataclass
from typing import Dict, List

import numpy as np

from app.config.settings import settings
from app.core.logging import get_logger
from app.services.ai.factory import AIServiceFactory
from app.services.retrieval.article_aggregation_service import ArticleResult

logger = get_logger(__name__)


@dataclass
class ConfidenceMetrics:
    """Multi-signal confidence metrics for retrieval quality"""

    overall_confidence: float  # 0-1 scale, weighted combination
    confidence_tier: str  # "HIGH", "MEDIUM", "LOW", or "NONE"
    top_article_score: float  # Relevance score of best article
    score_gap_ratio: float  # Gap between #1 and #2 (0-1)
    entity_coverage_ratio: float  # % of query entities in top article
    temporal_alignment: bool  # Do time entities match?
    spatial_alignment: bool  # Do location entities match?
    title_similarity: float  # Cosine similarity: query vs title
    total_qualifying_chunks: int  # Sum of chunks across articles
    article_count: int  # Number of articles returned

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "overall_confidence": self.overall_confidence,
            "confidence_tier": self.confidence_tier,
            "top_article_score": self.top_article_score,
            "score_gap_ratio": self.score_gap_ratio,
            "entity_coverage_ratio": self.entity_coverage_ratio,
            "temporal_alignment": self.temporal_alignment,
            "spatial_alignment": self.spatial_alignment,
            "title_similarity": self.title_similarity,
            "total_qualifying_chunks": self.total_qualifying_chunks,
            "article_count": self.article_count,
        }


class ConfidenceScoringService:
    """Calculate confidence that retrieved articles match the query"""

    def __init__(self):
        self.embedding_service = AIServiceFactory.get_embedding_provider()
        self.weights = settings.retrieval.confidence_scoring.weights
        self.thresholds = settings.retrieval.confidence_scoring.thresholds

    async def calculate_confidence(
        self,
        articles: List[ArticleResult],
        query_text: str,
        query_entities: Dict[str, List[str]] | None = None,
    ) -> ConfidenceMetrics:
        """
        Calculate multi-signal confidence score.

        Args:
            articles: List of retrieved articles (sorted by relevance)
            query_text: Original query text
            query_entities: Extracted entities from query
                           Format: {"persons": [...], "organizations": [...], ...}

        Returns:
            ConfidenceMetrics with overall score and component scores
        """
        if not articles:
            return ConfidenceMetrics(
                overall_confidence=0.0,
                confidence_tier="NONE",
                top_article_score=0.0,
                score_gap_ratio=0.0,
                entity_coverage_ratio=0.0,
                temporal_alignment=False,
                spatial_alignment=False,
                title_similarity=0.0,
                total_qualifying_chunks=0,
                article_count=0,
            )

        # Signal 1: Top article score (35% weight)
        # Normalize from 0-10 scale to 0-1 for weighted calculation
        top_score = articles[0].relevance_score / 10.0

        # Signal 2: Score gap ratio (25% weight)
        # How much better is #1 vs #2? (indicates clear winner)
        if len(articles) > 1 and articles[0].relevance_score > 0:
            score_diff = articles[0].relevance_score - articles[1].relevance_score
            gap_ratio = min(score_diff / articles[0].relevance_score, 1.0)
        else:
            gap_ratio = 1.0  # Only one article = perfect gap

        # Signal 3: Entity coverage (20% weight)
        entity_coverage = self._calculate_entity_coverage(articles[0], query_entities)

        # Signal 4: Temporal alignment (10% weight)
        temporal_alignment = self._check_temporal_alignment(articles[0], query_entities)

        # Signal 5: Spatial alignment (optional, included in entity coverage)
        spatial_alignment = self._check_spatial_alignment(articles[0], query_entities)

        # Signal 6: Title similarity (10% weight)
        title_similarity = await self._calculate_title_similarity(
            query_text, articles[0].title
        )

        # Calculate weighted confidence
        confidence = (
            self.weights.top_article_score * top_score
            + self.weights.score_gap_ratio * gap_ratio
            + self.weights.entity_coverage * entity_coverage
            + self.weights.temporal_alignment * (1.0 if temporal_alignment else 0.0)
            + self.weights.title_similarity * title_similarity
        )

        # Determine confidence tier
        if confidence >= self.thresholds.high:
            tier = "HIGH"
        elif confidence >= self.thresholds.medium:
            tier = "MEDIUM"
        elif confidence >= self.thresholds.low:
            tier = "LOW"
        else:
            tier = "NONE"

        # Calculate total chunks
        total_chunks = sum(len(a.relevant_chunks) for a in articles)

        logger.info(
            f"Confidence scoring: {confidence:.2f} ({tier}) - "
            f"top_score={top_score:.2f}, gap={gap_ratio:.2f}, "
            f"entities={entity_coverage:.2f}, title_sim={title_similarity:.2f}"
        )

        return ConfidenceMetrics(
            overall_confidence=confidence,
            confidence_tier=tier,
            top_article_score=top_score,
            score_gap_ratio=gap_ratio,
            entity_coverage_ratio=entity_coverage,
            temporal_alignment=temporal_alignment,
            spatial_alignment=spatial_alignment,
            title_similarity=title_similarity,
            total_qualifying_chunks=total_chunks,
            article_count=len(articles),
        )

    def _calculate_entity_coverage(
        self, article: ArticleResult, query_entities: Dict[str, List[str]] | None
    ) -> float:
        """
        Calculate what % of query entities appear in the article.

        Args:
            article: Top article
            query_entities: Entities extracted from query

        Returns:
            Ratio 0-1 of query entities found in article
        """
        if not query_entities:
            return 0.5  # No entities = neutral score

        # Collect all entities from query
        all_query_entities = []
        for entity_type, entities in query_entities.items():
            all_query_entities.extend(entities)

        if not all_query_entities:
            return 0.5  # No entities = neutral score

        # Check how many appear in article title + chunks
        article_text = article.title.lower()
        for chunk in article.relevant_chunks:
            article_text += " " + chunk.chunk_text.lower()

        matched_count = 0
        for entity in all_query_entities:
            if entity.lower() in article_text:
                matched_count += 1

        coverage = matched_count / len(all_query_entities)

        logger.debug(
            f"Entity coverage: {matched_count}/{len(all_query_entities)} "
            f"({coverage:.2f})"
        )

        return coverage

    def _check_temporal_alignment(
        self, article: ArticleResult, query_entities: Dict[str, List[str]] | None
    ) -> bool:
        """
        Check if temporal entities (dates, years) match between query and article.

        Args:
            article: Top article
            query_entities: Entities extracted from query

        Returns:
            True if temporal entities align, False otherwise
        """
        if not query_entities:
            return True  # No temporal entities = assume alignment

        # Check for date/time entities in query
        date_entities = query_entities.get("dates", []) + query_entities.get(
            "times", []
        )

        if not date_entities:
            return True  # No temporal constraint

        # Check if any date entity appears in article
        article_text = article.title.lower()
        for chunk in article.relevant_chunks:
            article_text += " " + chunk.chunk_text.lower()

        for date_entity in date_entities:
            if date_entity.lower() in article_text:
                logger.debug(f"Temporal alignment: Found '{date_entity}' in article")
                return True

        logger.debug(
            f"Temporal misalignment: Query dates {date_entities} not in article"
        )
        return False

    def _check_spatial_alignment(
        self, article: ArticleResult, query_entities: Dict[str, List[str]] | None
    ) -> bool:
        """
        Check if spatial entities (locations) match between query and article.

        Args:
            article: Top article
            query_entities: Entities extracted from query

        Returns:
            True if spatial entities align, False otherwise
        """
        if not query_entities:
            return True  # No spatial entities = assume alignment

        # Check for location entities in query
        location_entities = query_entities.get("locations", []) + query_entities.get(
            "places", []
        )

        if not location_entities:
            return True  # No spatial constraint

        # Check if any location entity appears in article
        article_text = article.title.lower()
        for chunk in article.relevant_chunks:
            article_text += " " + chunk.chunk_text.lower()

        for location in location_entities:
            if location.lower() in article_text:
                logger.debug(f"Spatial alignment: Found '{location}' in article")
                return True

        logger.debug(
            f"Spatial misalignment: Query locations {location_entities} not in article"
        )
        return False

    async def _calculate_title_similarity(
        self, query_text: str, article_title: str
    ) -> float:
        """
        Calculate cosine similarity between query and article title.

        High similarity indicates article's main topic matches query.

        Args:
            query_text: Original query
            article_title: Title of top article

        Returns:
            Cosine similarity score 0-1
        """
        try:
            # Generate embeddings
            embedding_responses = (
                await self.embedding_service.generate_embeddings_batch(
                    [query_text, article_title]
                )
            )

            # Extract actual embedding arrays from EmbeddingResponse objects
            query_embedding = np.array(embedding_responses[0].embedding)
            title_embedding = np.array(embedding_responses[1].embedding)

            # Calculate cosine similarity
            dot_product = np.dot(query_embedding, title_embedding)
            norm_query = np.linalg.norm(query_embedding)
            norm_title = np.linalg.norm(title_embedding)

            if norm_query == 0 or norm_title == 0:
                return 0.0

            similarity = dot_product / (norm_query * norm_title)

            # Ensure 0-1 range (cosine can be -1 to 1)
            similarity = max(0.0, min(1.0, similarity))

            logger.debug(f"Title similarity: {similarity:.3f}")

            return similarity

        except Exception as e:
            logger.error(f"Error calculating title similarity: {e}", exc_info=True)
            return 0.5  # Neutral score on error
