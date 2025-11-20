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
from app.services.verification.claim_article_mapper import (
    ArticleEvidence,
    ClaimArticleMapping,
)

logger = get_logger(__name__)


@dataclass
class EvidenceSpan:
    """Extracted evidence span from article"""

    text: str
    reasoning: str


@dataclass
class StanceResult:
    """Result of stance classification for a claim-article pair"""

    claim_text: str
    article_id: UUID
    article_title: str
    article_url: str
    source_name: str
    published_at: datetime | None
    stance: str  # SUPPORTS, REFUTES, NOT_ENOUGH_INFO
    confidence: float
    evidence_spans: List[EvidenceSpan]  # Exact quotes extracted from article
    overall_reasoning: str  # Comprehensive explanation


class StanceClassifier:
    """
    LLM-based stance classifier using Natural Language Inference.

    Determines whether a full article supports, refutes, or is neutral to a claim.
    Extracts precise evidence spans (quotes) from the article to support the stance.
    Uses parallel workers for efficient processing of multiple claim-article pairs.
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
        claim_article_mappings: List[ClaimArticleMapping],
    ) -> List[StanceResult]:
        """
        Classify stances for all claim-article pairs.

        Args:
            claim_article_mappings: List of claims with their full articles

        Returns:
            List of StanceResult objects for all pairs
        """
        # Flatten all claim-article pairs
        pairs = []
        for mapping in claim_article_mappings:
            for article in mapping.articles:
                pairs.append((mapping.claim_text, article))

        if not pairs:
            logger.warning("No claim-article pairs to classify")
            return []

        logger.info(
            f"Classifying {len(pairs)} claim-article pairs with {self.num_workers} workers"
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
            pairs: List of (claim, article) tuples

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
        Process a batch of claim-article pairs in one worker.

        Args:
            batch: List of (claim, article) tuples
            worker_id: Worker identifier
            semaphore: Semaphore for rate limiting

        Returns:
            List of StanceResult objects
        """
        if not batch:
            return []

        results = []

        for claim, article in batch:
            try:
                async with semaphore:
                    result = await asyncio.wait_for(
                        self._classify_single_pair(claim, article),
                        timeout=self.worker_timeout,
                    )
                    if result:
                        results.append(result)
            except asyncio.TimeoutError:
                logger.warning(
                    f"Worker {worker_id} timed out on pair. "
                    f"Claim: '{claim[:30]}...', Article: {article.article_id}"
                )
                # Create a default NOT_ENOUGH_INFO result
                results.append(
                    StanceResult(
                        claim_text=claim,
                        article_id=article.article_id,
                        article_title=article.article_title,
                        article_url=article.url,
                        source_name=article.source_name,
                        published_at=article.published_at,
                        stance="NOT_ENOUGH_INFO",
                        confidence=0.0,
                        evidence_spans=[],
                        overall_reasoning="Timeout during classification",
                    )
                )
            except Exception as e:
                logger.error(
                    f"Worker {worker_id} error: {e}. "
                    f"Claim: '{claim[:30]}...', Article: {article.article_id}"
                )
                # Create a default NOT_ENOUGH_INFO result
                results.append(
                    StanceResult(
                        claim_text=claim,
                        article_id=article.article_id,
                        article_title=article.article_title,
                        article_url=article.url,
                        source_name=article.source_name,
                        published_at=article.published_at,
                        stance="NOT_ENOUGH_INFO",
                        confidence=0.0,
                        evidence_spans=[],
                        overall_reasoning=f"Error: {str(e)}",
                    )
                )

        logger.debug(f"Worker {worker_id} completed {len(results)} classifications")
        return results

    async def _classify_single_pair(
        self, claim: str, article: ArticleEvidence
    ) -> StanceResult | None:
        """
        Classify stance for a single claim-article pair using LLM.

        Args:
            claim: The claim text
            article: The full article

        Returns:
            StanceResult or None if classification fails
        """
        prompt = self._build_stance_prompt(claim, article)

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
            evidence_spans_raw = result.get("evidence_spans", [])
            overall_reasoning = result.get("overall_reasoning", "")

            # Validate stance
            if stance not in ["SUPPORTS", "REFUTES", "NOT_ENOUGH_INFO"]:
                logger.warning(
                    f"Invalid stance '{stance}', defaulting to NOT_ENOUGH_INFO"
                )
                stance = "NOT_ENOUGH_INFO"

            # Parse evidence spans
            evidence_spans = []
            for span_data in evidence_spans_raw:
                if isinstance(span_data, dict):
                    evidence_spans.append(
                        EvidenceSpan(
                            text=span_data.get("text", ""),
                            reasoning=span_data.get("reasoning", ""),
                        )
                    )

            return StanceResult(
                claim_text=claim,
                article_id=article.article_id,
                article_title=article.article_title,
                article_url=article.url,
                source_name=article.source_name,
                published_at=article.published_at,
                stance=stance,
                confidence=confidence,
                evidence_spans=evidence_spans,
                overall_reasoning=overall_reasoning,
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse stance classification response: {e}")
            return None
        except Exception as e:
            logger.error(f"Stance classification error: {e}")
            raise

    def _build_stance_prompt(self, claim: str, article: ArticleEvidence) -> str:
        """
        Build prompt for stance classification.

        Args:
            claim: The claim to verify
            article: The full article

        Returns:
            Prompt string
        """
        # Format publication date
        pub_date = ""
        if article.published_at:
            pub_date = article.published_at.strftime("%Y-%m-%d")

        # Truncate article content if too long (keep first 8000 chars to avoid token limits)
        article_content = article.article_content
        if len(article_content) > 8000:
            article_content = (
                article_content[:8000] + "\n\n[...bài viết còn tiếp, đã cắt ngắn...]"
            )

        prompt = f"""Bạn là một trợ lý kiểm chứng thông tin. Phân tích xem BÀI BÁO có ủng hộ hay bác bỏ TUYÊN BỐ hay không.

TUYÊN BỐ:
"{claim}"

BÀI BÁO (từ {article.source_name}, đăng ngày {pub_date}):
Tiêu đề: {article.article_title}

Nội dung:
{article_content}

---

Nhiệm vụ của bạn:
1. Đọc toàn bộ bài báo để hiểu ngữ cảnh đầy đủ
2. Xác định xem bài báo có ủng hộ (SUPPORTS), bác bỏ (REFUTES), hay không đủ thông tin (NOT_ENOUGH_INFO) về tuyên bố
3. Trích xuất các đoạn văn bản CHÍNH XÁC từ bài báo làm bằng chứng

Phân loại mối quan hệ:
- SUPPORTS: Bài báo trực tiếp xác nhận tuyên bố là đúng
- REFUTES: Bài báo trực tiếp chứng minh tuyên bố là sai
- NOT_ENOUGH_INFO: Bài báo liên quan nhưng không đủ để xác nhận hoặc bác bỏ

Hướng dẫn đánh giá:
1. SUPPORTS: Bài báo phải khẳng định CÙNG thông tin với tuyên bố (cùng số liệu, cùng sự kiện, cùng chi tiết)
2. REFUTES: Bài báo phải ĐƯA RA thông tin TRÁI NGƯỢC (số liệu khác, phủ nhận sự kiện, chi tiết mâu thuẫn)
3. NOT_ENOUGH_INFO: Bài báo nói về chủ đề liên quan nhưng không trực tiếp xác nhận/bác bỏ tuyên bố cụ thể

Lưu ý quan trọng:
- Chỉ chọn SUPPORTS hoặc REFUTES khi bằng chứng RÕ RÀNG và TRỰC TIẾP
- Nếu không chắc chắn, chọn NOT_ENOUGH_INFO
- Trích dẫn CHÍNH XÁC các câu/đoạn văn từ bài báo (không được tóm tắt hay diễn giải)
- Có thể trích nhiều đoạn nếu cần thiết

Trả lời dưới dạng JSON:
{{
    "stance": "SUPPORTS|REFUTES|NOT_ENOUGH_INFO",
    "confidence": 0.0-1.0,
    "evidence_spans": [
        {{
            "text": "trích dẫn chính xác từ bài báo",
            "reasoning": "giải thích tại sao đoạn này ủng hộ/bác bỏ tuyên bố"
        }},
        {{
            "text": "trích dẫn khác nếu cần",
            "reasoning": "giải thích cho trích dẫn này"
        }}
    ],
    "overall_reasoning": "tổng hợp giải thích toàn diện về stance classification (2-3 câu)"
}}"""

        return prompt
