"""
Claim-Article Mapper Service

Maps extracted claims to retrieved articles for verification.
Creates N×M claim-article pairs (each claim verified against each article).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List
from uuid import UUID

from app.core.logging import get_logger
from app.services.retrieval.article_aggregation_service import ArticleResult

logger = get_logger(__name__)


@dataclass
class ArticleEvidence:
    """A full article for verifying a claim"""

    article_id: UUID
    article_title: str
    article_content: str
    source_name: str
    published_at: datetime | None
    url: str
    relevance_score: float  # Retrieval relevance score (0-10)


@dataclass
class ClaimArticleMapping:
    """Mapping of a claim to relevant full articles"""

    claim_text: str
    articles: List[ArticleEvidence]


class ClaimArticleMapper:
    """
    Maps claims to full articles for verification.

    Creates N×M claim-article pairs where:
    - N = number of claims extracted from the post
    - M = number of articles retrieved by the retrieval pipeline

    Each claim is verified against ALL retrieved articles (not a subset).
    The retrieval pipeline already filtered for relevance, so we use all of them.
    """

    def __init__(self):
        pass  # No configuration needed

    async def map_claims_to_articles(
        self,
        claims: List[str],
        articles: List[ArticleResult],
    ) -> List[ClaimArticleMapping]:
        """
        Map each claim to relevant full articles.

        Args:
            claims: List of extracted claims from the post
            articles: List of retrieved articles (already ranked by retrieval pipeline)

        Returns:
            List of ClaimArticleMapping objects, one per claim
        """
        if not claims or not articles:
            return []

        logger.info(
            f"Mapping {len(claims)} claims to {len(articles)} articles "
            f"({len(claims)} × {len(articles)} = {len(claims) * len(articles)} total pairs)"
        )

        # Convert all retrieved articles to ArticleEvidence
        article_evidence_list = []
        for article in articles:
            if article.content:  # Only include articles with content
                article_evidence_list.append(
                    ArticleEvidence(
                        article_id=article.article_id,
                        article_title=article.title,
                        article_content=article.content,
                        source_name=article.source_name,
                        published_at=article.published_at,
                        url=article.url,
                        relevance_score=article.relevance_score,
                    )
                )
            else:
                logger.warning(
                    f"Article {article.article_id} has no content, skipping for verification"
                )

        if not article_evidence_list:
            logger.warning("No articles with content available for claim verification")
            return [
                ClaimArticleMapping(claim_text=claim, articles=[]) for claim in claims
            ]

        # Create mappings: each claim gets the same set of top articles
        mappings = []
        for claim in claims:
            mappings.append(
                ClaimArticleMapping(
                    claim_text=claim, articles=article_evidence_list.copy()
                )
            )
            logger.debug(
                f"Claim '{claim[:50]}...' mapped to {len(article_evidence_list)} full articles"
            )

        total_articles = sum(len(m.articles) for m in mappings)
        logger.info(
            f"Article mapping complete: {len(claims)} claims → {total_articles} total article-claim pairs"
        )

        return mappings
