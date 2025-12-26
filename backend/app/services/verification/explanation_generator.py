"""
Explanation Generator Service

Generates human-readable explanations for verification results in Vietnamese.
"""

import json

from app.config.settings import settings
from app.core.logging import get_logger
from app.services.ai.base import LLMMessage
from app.services.ai.factory import AIServiceFactory
from app.services.verification.verdict_aggregator import OverallVerdict

logger = get_logger(__name__)


class ExplanationGenerator:
    """
    Generates human-readable explanations for verification results.

    Uses LLM to create clear, concise summaries of the verification
    outcome with supporting evidence in Vietnamese.
    """

    def __init__(self):
        self.llm = AIServiceFactory.get_llm_provider()
        self.model = settings.ai.llm_model
        self.language = settings.verification.explanation.language
        self.max_length = settings.verification.explanation.max_length

    async def generate_explanation(
        self,
        verdict: OverallVerdict,
        original_post: str,
    ) -> str:
        """
        Generate a human-readable explanation for the verification result.

        Args:
            verdict: The overall verification verdict
            original_post: The original Facebook post text

        Returns:
            Human-readable explanation string in Vietnamese
        """
        logger.info(f"Generating explanation for verdict: {verdict.verdict}")

        # For simple cases, generate rule-based explanation
        if verdict.verdict == "NOT_ENOUGH_INFO" and verdict.total_claims == 0:
            return self._generate_no_claims_explanation()

        if not verdict.claim_verdicts:
            return self._generate_no_evidence_explanation()

        # For complex cases, use LLM
        try:
            explanation = await self._generate_llm_explanation(verdict, original_post)
            return explanation
        except Exception as e:
            logger.error(f"Failed to generate LLM explanation: {e}")
            # Fall back to rule-based
            return self._generate_fallback_explanation(verdict)

    async def _generate_llm_explanation(
        self,
        verdict: OverallVerdict,
        original_post: str,
    ) -> str:
        """
        Generate explanation using LLM.

        Args:
            verdict: The overall verdict
            original_post: Original post text

        Returns:
            Generated explanation
        """
        prompt = self._build_explanation_prompt(verdict, original_post)

        messages = [LLMMessage(role="user", content=prompt)]
        response = await self.llm.generate_completion(
            messages=messages,
            model=self.model,
            temperature=0.3,  # Slight creativity for natural language
            response_format={"type": "json_object"},
        )

        result = json.loads(response.content)
        explanation = result.get("explanation", "")

        # Truncate if too long
        if len(explanation) > self.max_length:
            explanation = explanation[: self.max_length - 3] + "..."

        return explanation

    def _build_explanation_prompt(
        self,
        verdict: OverallVerdict,
        original_post: str,
    ) -> str:
        """
        Build prompt for explanation generation.

        Args:
            verdict: The overall verdict
            original_post: Original post text

        Returns:
            Prompt string
        """
        # Prepare claim verdicts summary
        claim_summaries = []
        for cv in verdict.claim_verdicts:
            sources = []
            if cv.supporting_evidence:
                sources = [e.source_name for e in cv.supporting_evidence[:2]]
            elif cv.refuting_evidence:
                sources = [e.source_name for e in cv.refuting_evidence[:2]]

            claim_summaries.append(
                {
                    "claim": cv.claim_text[:100],
                    "verdict": cv.verdict,
                    "sources": sources,
                }
            )

        # Map verdict to Vietnamese
        verdict_map = {
            "FULLY_SUPPORTED": "ĐÁNG TIN CẬY",
            "PARTIALLY_SUPPORTED": "ĐÚNG MỘT PHẦN",
            "REFUTED": "SAI SỰ THẬT",
            "NOT_ENOUGH_INFO": "CHƯA ĐỦ BẰNG CHỨNG",
        }
        verdict_vn = verdict_map.get(verdict.verdict, verdict.verdict)

        # Format confidence safely
        confidence_str = (
            f"{verdict.confidence:.0%}"
            if verdict.confidence is not None
            else "Không xác định"
        )

        prompt = f"""Bạn là trợ lý tạo giải thích cho kết quả kiểm chứng thông tin.

BÀI ĐĂNG GỐC:
"{original_post[:300]}"

KẾT QUẢ KIỂM CHỨNG:
- Kết luận: {verdict_vn}
- Độ tin cậy: {confidence_str}
- Số luận điểm được xác nhận: {verdict.supported_claims}/{verdict.total_claims}
- Số luận điểm bị bác bỏ: {verdict.refuted_claims}/{verdict.total_claims}

CHI TIẾT TỪNG LUẬN ĐIỂM:
{json.dumps(claim_summaries, ensure_ascii=False, indent=2)}

NGUỒN TIN SỬ DỤNG:
{", ".join(verdict.sources_used)}

Viết một đoạn giải thích ngắn gọn (tối đa {self.max_length} ký tự) bằng tiếng Việt:
1. Tóm tắt kết quả kiểm chứng
2. Nêu rõ những luận điểm nào đúng/sai
3. Trích dẫn nguồn tin đáng tin cậy
4. Giọng văn khách quan, dễ hiểu

Trả lời dưới dạng JSON:
{{
    "explanation": "nội dung giải thích"
}}"""

        return prompt

    def _generate_no_claims_explanation(self) -> str:
        """Generate explanation when no claims were extracted."""
        return (
            "Không thể xác minh bài đăng này vì không tìm thấy luận điểm cụ thể nào "
            "cần kiểm chứng. Bài đăng có thể chỉ chứa ý kiến cá nhân hoặc thông tin "
            "quá chung chung để có thể xác minh."
        )

    def _generate_no_evidence_explanation(self) -> str:
        """Generate explanation when no evidence was found."""
        return (
            "Không tìm thấy bằng chứng từ các nguồn tin đáng tin cậy để xác minh "
            "bài đăng này. Điều này có thể do thông tin quá mới, quá cũ, hoặc "
            "chưa được các báo chính thống đưa tin."
        )

    def _generate_fallback_explanation(self, verdict: OverallVerdict) -> str:
        """
        Generate a rule-based fallback explanation.

        Args:
            verdict: The overall verdict

        Returns:
            Explanation string
        """
        if verdict.verdict == "FULLY_SUPPORTED":
            return (
                f"Bài đăng này ĐÁNG TIN CẬY. Tất cả {verdict.total_claims} "
                f"luận điểm trong bài đăng đều được xác nhận bởi các nguồn tin "
                f"đáng tin cậy: {', '.join(verdict.sources_used[:3])}."
            )

        elif verdict.verdict == "PARTIALLY_SUPPORTED":
            return (
                f"Bài đăng này ĐÚNG MỘT PHẦN. {verdict.supported_claims}/{verdict.total_claims} "
                f"luận điểm được xác nhận, còn lại chưa đủ bằng chứng. "
                f"Nguồn: {', '.join(verdict.sources_used[:3])}."
            )

        elif verdict.verdict == "REFUTED":
            return (
                f"Bài đăng này CHỨA THÔNG TIN SAI. {verdict.refuted_claims}/{verdict.total_claims} "
                f"luận điểm bị bác bỏ bởi bằng chứng từ các nguồn tin đáng tin cậy: "
                f"{', '.join(verdict.sources_used[:3])}."
            )

        else:  # NOT_ENOUGH_INFO
            return (
                f"CHƯA ĐỦ BẰNG CHỨNG để xác minh bài đăng này. Đã kiểm tra "
                f"{verdict.total_claims} luận điểm nhưng không tìm thấy đủ thông tin "
                f"từ các nguồn tin để đưa ra kết luận chắc chắn."
            )
