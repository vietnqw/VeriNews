"""
Stance Classifier Service

LLM-based Natural Language Inference (NLI) service that classifies
the stance of evidence towards claims (SUPPORTS, REFUTES, NOT_ENOUGH_INFO).
"""

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from typing import List
from uuid import UUID

from app.config.settings import settings
from app.core.logging import get_logger
from app.services.ai.base import LLMMessage
from app.services.ai.factory import AIServiceFactory
from app.services.verification.claim_evidence_mapper import (
    ClaimEvidenceMapping,
    EvidenceChunk,
)

logger = get_logger(__name__)


@dataclass
class StanceResult:
    """Result of stance classification for a claim-evidence pair"""

    claim_text: str
    evidence_chunk_id: UUID
    evidence_text: str
    source_name: str
    published_at: datetime | None
    stance: str  # SUPPORTS, REFUTES, NOT_ENOUGH_INFO
    confidence: float
    key_quote: str
    reasoning: str
    similarity_score: float  # From evidence mapping


class StanceClassifier:
    """
    LLM-based stance classifier using Natural Language Inference.

    Determines whether evidence supports, refutes, or is neutral to a claim.
    Uses parallel workers for efficient processing of multiple claim-evidence pairs.
    """

    def __init__(self):
        self.llm = AIServiceFactory.get_llm_provider()
        self.model = settings.ai.llm_model
        self.num_workers = (
            settings.verification.stance_classification.num_parallel_workers
        )
        self.worker_timeout = (
            settings.verification.stance_classification.worker_timeout_seconds
        )
        self.min_confidence = settings.verification.stance_classification.min_confidence

    async def classify_stances(
        self,
        claim_evidence_mappings: List[ClaimEvidenceMapping],
    ) -> List[StanceResult]:
        """
        Classify stances for all claim-evidence pairs.

        Args:
            claim_evidence_mappings: List of claims with their evidence chunks

        Returns:
            List of StanceResult objects for all pairs
        """
        # Flatten all claim-evidence pairs
        pairs = []
        for mapping in claim_evidence_mappings:
            for evidence in mapping.evidence_chunks:
                pairs.append((mapping.claim_text, evidence))

        if not pairs:
            logger.warning("No claim-evidence pairs to classify")
            return []

        logger.info(
            f"Classifying {len(pairs)} claim-evidence pairs with {self.num_workers} workers"
        )

        # Create round-robin batches for parallel workers
        worker_batches = self._create_round_robin_batches(pairs)

        # Create semaphore for rate limiting
        semaphore = asyncio.Semaphore(self.num_workers)

        # Process all batches in parallel
        worker_tasks = [
            self._process_worker_batch(batch, worker_id, semaphore)
            for worker_id, batch in enumerate(worker_batches)
        ]

        # Wait for all workers
        worker_results = await asyncio.gather(*worker_tasks, return_exceptions=True)

        # Merge results from all workers
        all_results = []
        for result in worker_results:
            if isinstance(result, Exception):
                logger.error(f"Worker failed with exception: {result}")
                continue
            all_results.extend(result)

        logger.info(
            f"Stance classification complete: {len(all_results)} results from {len(pairs)} pairs"
        )

        return all_results

    def _create_round_robin_batches(self, pairs: List[tuple]) -> List[List[tuple]]:
        """
        Split pairs into round-robin batches for parallel workers.

        Args:
            pairs: List of (claim, evidence) tuples

        Returns:
            List of batches (one per worker)
        """
        worker_batches = [[] for _ in range(self.num_workers)]

        for i, pair in enumerate(pairs):
            worker_id = i % self.num_workers
            worker_batches[worker_id].append(pair)

        return worker_batches

    async def _process_worker_batch(
        self,
        batch: List[tuple],
        worker_id: int,
        semaphore: asyncio.Semaphore,
    ) -> List[StanceResult]:
        """
        Process a batch of claim-evidence pairs in one worker.

        Args:
            batch: List of (claim, evidence) tuples
            worker_id: Worker identifier
            semaphore: Semaphore for rate limiting

        Returns:
            List of StanceResult objects
        """
        if not batch:
            return []

        results = []

        for claim, evidence in batch:
            try:
                async with semaphore:
                    result = await asyncio.wait_for(
                        self._classify_single_pair(claim, evidence),
                        timeout=self.worker_timeout,
                    )
                    if result:
                        results.append(result)
            except asyncio.TimeoutError:
                logger.warning(
                    f"Worker {worker_id} timed out on pair. "
                    f"Claim: '{claim[:30]}...', Evidence chunk: {evidence.chunk_id}"
                )
                # Create a default NOT_ENOUGH_INFO result
                results.append(
                    StanceResult(
                        claim_text=claim,
                        evidence_chunk_id=evidence.chunk_id,
                        evidence_text=evidence.chunk_text,
                        source_name=evidence.source_name,
                        published_at=evidence.published_at,
                        stance="NOT_ENOUGH_INFO",
                        confidence=0.0,
                        key_quote="",
                        reasoning="Timeout during classification",
                        similarity_score=evidence.similarity_score,
                    )
                )
            except Exception as e:
                logger.error(
                    f"Worker {worker_id} error: {e}. "
                    f"Claim: '{claim[:30]}...', Evidence: {evidence.chunk_id}"
                )
                # Create a default NOT_ENOUGH_INFO result
                results.append(
                    StanceResult(
                        claim_text=claim,
                        evidence_chunk_id=evidence.chunk_id,
                        evidence_text=evidence.chunk_text,
                        source_name=evidence.source_name,
                        published_at=evidence.published_at,
                        stance="NOT_ENOUGH_INFO",
                        confidence=0.0,
                        key_quote="",
                        reasoning=f"Error: {str(e)}",
                        similarity_score=evidence.similarity_score,
                    )
                )

        logger.debug(f"Worker {worker_id} completed {len(results)} classifications")
        return results

    async def _classify_single_pair(
        self, claim: str, evidence: EvidenceChunk
    ) -> StanceResult | None:
        """
        Classify stance for a single claim-evidence pair using LLM.

        Args:
            claim: The claim text
            evidence: The evidence chunk

        Returns:
            StanceResult or None if classification fails
        """
        prompt = self._build_stance_prompt(claim, evidence)

        try:
            messages = [LLMMessage(role="user", content=prompt)]
            response = await self.llm.generate_completion(
                messages=messages,
                model=self.model,
                temperature=0,
                response_format={"type": "json_object"},
            )

            # Parse JSON response
            result = json.loads(response.content)

            stance = result.get("stance", "NOT_ENOUGH_INFO")
            confidence = float(result.get("confidence", 0.5))
            key_quote = result.get("key_quote", "")
            reasoning = result.get("reasoning", "")

            # Validate stance
            if stance not in ["SUPPORTS", "REFUTES", "NOT_ENOUGH_INFO"]:
                logger.warning(
                    f"Invalid stance '{stance}', defaulting to NOT_ENOUGH_INFO"
                )
                stance = "NOT_ENOUGH_INFO"

            return StanceResult(
                claim_text=claim,
                evidence_chunk_id=evidence.chunk_id,
                evidence_text=evidence.chunk_text,
                source_name=evidence.source_name,
                published_at=evidence.published_at,
                stance=stance,
                confidence=confidence,
                key_quote=key_quote,
                reasoning=reasoning,
                similarity_score=evidence.similarity_score,
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse stance classification response: {e}")
            return None
        except Exception as e:
            logger.error(f"Stance classification error: {e}")
            raise

    def _build_stance_prompt(self, claim: str, evidence: EvidenceChunk) -> str:
        """
        Build prompt for stance classification.

        Args:
            claim: The claim to verify
            evidence: The evidence chunk

        Returns:
            Prompt string
        """
        # Format publication date
        pub_date = ""
        if evidence.published_at:
            pub_date = evidence.published_at.strftime("%Y-%m-%d")

        prompt = f"""Bạn là một trợ lý kiểm chứng thông tin. Phân tích xem BẰNG CHỨNG có ủng hộ hay bác bỏ TUYÊN BỐ hay không.

TUYÊN BỐ:
"{claim}"

BẰNG CHỨNG (từ {evidence.source_name}, đăng ngày {pub_date}):
"{evidence.chunk_text}"

Phân loại mối quan hệ:
- SUPPORTS: Bằng chứng trực tiếp xác nhận tuyên bố là đúng
- REFUTES: Bằng chứng trực tiếp chứng minh tuyên bố là sai
- NOT_ENOUGH_INFO: Bằng chứng liên quan nhưng không đủ để xác nhận hoặc bác bỏ

Hướng dẫn đánh giá:
1. SUPPORTS: Bằng chứng phải khẳng định CÙNG thông tin với tuyên bố (cùng số liệu, cùng sự kiện, cùng chi tiết)
2. REFUTES: Bằng chứng phải ĐƯA RA thông tin TRÁI NGƯỢC (số liệu khác, phủ nhận sự kiện, chi tiết mâu thuẫn)
3. NOT_ENOUGH_INFO: Bằng chứng nói về chủ đề liên quan nhưng không trực tiếp xác nhận/bác bỏ tuyên bố cụ thể

Lưu ý quan trọng:
- Chỉ chọn SUPPORTS hoặc REFUTES khi bằng chứng RÕ RÀNG và TRỰC TIẾP
- Nếu không chắc chắn, chọn NOT_ENOUGH_INFO
- Trích dẫn chính xác câu/cụm từ quan trọng từ bằng chứng

Trả lời dưới dạng JSON:
{{
    "stance": "SUPPORTS|REFUTES|NOT_ENOUGH_INFO",
    "confidence": 0.0-1.0,
    "key_quote": "trích dẫn chính xác từ bằng chứng",
    "reasoning": "giải thích ngắn gọn bằng tiếng Việt"
}}"""

        return prompt
