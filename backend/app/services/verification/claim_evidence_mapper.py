"""
Claim-Evidence Mapper Service

Maps extracted claims to the most relevant article chunks
using semantic similarity for evidence retrieval.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List
from uuid import UUID

import numpy as np

from app.config.settings import settings
from app.core.logging import get_logger
from app.services.ai.factory import AIServiceFactory
from app.services.retrieval.article_aggregation_service import ArticleResult

logger = get_logger(__name__)


@dataclass
class EvidenceChunk:
    """A chunk of evidence for a claim"""

    chunk_id: UUID
    chunk_text: str
    chunk_index: int
    article_id: UUID
    article_title: str
    source_name: str
    published_at: datetime | None
    url: str
    similarity_score: float


@dataclass
class ClaimEvidenceMapping:
    """Mapping of a claim to its evidence chunks"""

    claim_text: str
    evidence_chunks: List[EvidenceChunk]


class ClaimEvidenceMapper:
    """
    Maps claims to relevant evidence chunks using embedding similarity.

    For each claim, finds the most semantically similar chunks from
    the retrieved articles to use as evidence for verification.
    """

    def __init__(self):
        self.embedding_provider = AIServiceFactory.get_embedding_provider()
        self.model = settings.ai.embedding_model
        self.top_k = settings.verification.claim_evidence_mapping.top_k_chunks_per_claim
        self.min_similarity = (
            settings.verification.claim_evidence_mapping.min_similarity_threshold
        )

    async def map_claims_to_evidence(
        self,
        claims: List[str],
        articles: List[ArticleResult],
    ) -> List[ClaimEvidenceMapping]:
        """
        Map each claim to its most relevant evidence chunks.

        Args:
            claims: List of extracted claims from the post
            articles: List of retrieved articles with chunks

        Returns:
            List of ClaimEvidenceMapping objects, one per claim
        """
        if not claims or not articles:
            return []

        logger.info(
            f"Mapping {len(claims)} claims to evidence from {len(articles)} articles"
        )

        # Collect all chunks from articles
        all_chunks = self._collect_all_chunks(articles)

        if not all_chunks:
            logger.warning("No chunks available for evidence mapping")
            return [
                ClaimEvidenceMapping(claim_text=claim, evidence_chunks=[])
                for claim in claims
            ]

        # Generate embeddings for claims
        claim_embeddings = await self._generate_claim_embeddings(claims)

        # Generate embeddings for chunks (or use cached if available)
        chunk_embeddings = await self._generate_chunk_embeddings(all_chunks)

        # Map each claim to top-k most similar chunks
        mappings = []
        for i, claim in enumerate(claims):
            claim_embedding = claim_embeddings[i]
            evidence = self._find_top_k_evidence(
                claim, claim_embedding, all_chunks, chunk_embeddings
            )
            mappings.append(
                ClaimEvidenceMapping(claim_text=claim, evidence_chunks=evidence)
            )

            logger.debug(
                f"Claim '{claim[:50]}...' mapped to {len(evidence)} evidence chunks"
            )

        total_evidence = sum(len(m.evidence_chunks) for m in mappings)
        logger.info(
            f"Evidence mapping complete: {len(claims)} claims → {total_evidence} total evidence pieces"
        )

        return mappings

    def _collect_all_chunks(self, articles: List[ArticleResult]) -> List[EvidenceChunk]:
        """
        Collect all chunks from articles into a flat list with metadata.

        Args:
            articles: List of articles with chunks

        Returns:
            List of EvidenceChunk objects
        """
        all_chunks = []
        for article in articles:
            for chunk in article.relevant_chunks:
                evidence_chunk = EvidenceChunk(
                    chunk_id=chunk.chunk_id,
                    chunk_text=chunk.chunk_text,
                    chunk_index=chunk.chunk_index,
                    article_id=article.article_id,
                    article_title=article.title,
                    source_name=article.source_name,
                    published_at=article.published_at,
                    url=article.url,
                    similarity_score=0.0,  # Will be computed later
                )
                all_chunks.append(evidence_chunk)

        return all_chunks

    async def _generate_claim_embeddings(self, claims: List[str]) -> List[List[float]]:
        """
        Generate embeddings for all claims.

        Args:
            claims: List of claim texts

        Returns:
            List of embedding vectors
        """
        try:
            responses = await self.embedding_provider.generate_embeddings_batch(
                texts=claims, model=self.model
            )
            # Extract embedding vectors from EmbeddingResponse objects
            return [response.embedding for response in responses]
        except Exception as e:
            logger.error(f"Failed to generate claim embeddings: {e}")
            raise

    async def _generate_chunk_embeddings(
        self, chunks: List[EvidenceChunk]
    ) -> List[List[float]]:
        """
        Generate embeddings for all chunks.

        Args:
            chunks: List of evidence chunks

        Returns:
            List of embedding vectors
        """
        chunk_texts = [chunk.chunk_text for chunk in chunks]

        try:
            responses = await self.embedding_provider.generate_embeddings_batch(
                texts=chunk_texts, model=self.model
            )
            # Extract embedding vectors from EmbeddingResponse objects
            return [response.embedding for response in responses]
        except Exception as e:
            logger.error(f"Failed to generate chunk embeddings: {e}")
            raise

    def _find_top_k_evidence(
        self,
        claim: str,
        claim_embedding: List[float],
        chunks: List[EvidenceChunk],
        chunk_embeddings: List[List[float]],
    ) -> List[EvidenceChunk]:
        """
        Find top-k most similar chunks to the claim.

        Args:
            claim: The claim text
            claim_embedding: Embedding vector for the claim
            chunks: List of all evidence chunks
            chunk_embeddings: Embedding vectors for all chunks

        Returns:
            List of top-k EvidenceChunk objects sorted by similarity
        """
        # Calculate cosine similarity for all chunks
        claim_vec = np.array(claim_embedding)
        similarities = []

        for i, chunk_embedding in enumerate(chunk_embeddings):
            chunk_vec = np.array(chunk_embedding)
            similarity = self._cosine_similarity(claim_vec, chunk_vec)
            similarities.append((i, similarity))

        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)

        # Filter by threshold and take top-k
        evidence_chunks = []
        for idx, similarity in similarities[: self.top_k]:
            if similarity >= self.min_similarity:
                chunk = chunks[idx]
                # Create new EvidenceChunk with similarity score
                evidence_chunk = EvidenceChunk(
                    chunk_id=chunk.chunk_id,
                    chunk_text=chunk.chunk_text,
                    chunk_index=chunk.chunk_index,
                    article_id=chunk.article_id,
                    article_title=chunk.article_title,
                    source_name=chunk.source_name,
                    published_at=chunk.published_at,
                    url=chunk.url,
                    similarity_score=similarity,
                )
                evidence_chunks.append(evidence_chunk)

        return evidence_chunks

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score (0-1)
        """
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(np.dot(vec1, vec2) / (norm1 * norm2))
