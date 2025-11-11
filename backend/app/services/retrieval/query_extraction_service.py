"""
Query Extraction Service

Extracts clean queries and specific claims from noisy Facebook posts using LLM.
"""

import json
from typing import Dict

from app.config.settings import settings
from app.core.logging import get_logger
from app.services.ai.base import LLMMessage
from app.services.ai.factory import AIServiceFactory

logger = get_logger(__name__)


class QueryExtractionService:
    """
    LLM-based query extraction from Facebook posts.

    Converts noisy, unstructured Facebook posts into:
    1. A clean query (stripped of noise, keeping essential information)
    2. A list of specific, verifiable claims

    Uses structured JSON output for reliable parsing.
    """

    def __init__(self):
        self.llm = AIServiceFactory.get_llm_provider()
        self.model = settings.retrieval.query_extraction.model
        self.temperature = settings.retrieval.query_extraction.temperature
        self.max_claims = settings.retrieval.query_extraction.max_claims

    async def extract_queries(self, post_text: str) -> Dict[str, any]:
        """
        Extract clean query and claims from a Facebook post.

        Args:
            post_text: Original Facebook post text (noisy, with opinions, emojis, etc.)

        Returns:
            Dictionary with:
            - clean_query: Cleaned version of the post
            - claims: List of specific factual claims to verify
            - query_count: Total number of queries (1 clean_query + N claims)

        Example:
            Input: "VinTech xây nhà máy 5 tỷ USD ở Hà Nội!!! Tuyệt vời 🎉🎉"
            Output: {
                "clean_query": "VinTech xây dựng nhà máy trị giá 5 tỷ USD tại Hà Nội",
                "claims": [
                    "VinTech xây dựng nhà máy tại Hà Nội",
                    "Nhà máy có giá trị 5 tỷ USD"
                ],
                "query_count": 3
            }
        """
        prompt = self._build_extraction_prompt(post_text)

        try:
            # Call LLM with JSON mode for structured output
            messages = [LLMMessage(role="user", content=prompt)]
            response = await self.llm.generate_completion(
                messages=messages,
                model=self.model,
                temperature=self.temperature,
                response_format={"type": "json_object"},
            )

            # Parse JSON response
            result = json.loads(response.content)

            # Validate and clean result
            clean_query = result.get("clean_query", "").strip()
            claims = result.get("claims", [])
            factual_confidence = result.get("factual_confidence", 1.0)

            # Validate confidence is in range [0.0, 1.0]
            if not isinstance(factual_confidence, (int, float)):
                logger.warning(
                    f"Invalid factual_confidence type: {type(factual_confidence)}, defaulting to 1.0"
                )
                factual_confidence = 1.0
            factual_confidence = max(0.0, min(1.0, float(factual_confidence)))

            # Limit claims to max_claims
            if len(claims) > self.max_claims:
                claims = claims[: self.max_claims]
                logger.warning(
                    f"Truncated claims from {len(claims)} to {self.max_claims}"
                )

            # Filter out empty claims
            claims = [claim.strip() for claim in claims if claim.strip()]

            query_count = 1 + len(claims)  # 1 clean_query + N claims

            logger.info(
                f"Extracted {query_count} queries: 1 clean_query + {len(claims)} claims "
                f"(factual_confidence: {factual_confidence:.2f})"
            )

            return {
                "clean_query": clean_query,
                "claims": claims,
                "query_count": query_count,
                "factual_confidence": factual_confidence,
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            # Fallback: use original post as clean_query, assume verifiable (fail open)
            return {
                "clean_query": post_text.strip(),
                "claims": [],
                "query_count": 1,
                "factual_confidence": 1.0,  # Fail open: assume verifiable
            }
        except Exception as e:
            logger.error(f"Error during query extraction: {e}")
            # Fallback: use original post as clean_query, assume verifiable (fail open)
            return {
                "clean_query": post_text.strip(),
                "claims": [],
                "query_count": 1,
                "factual_confidence": 1.0,  # Fail open: assume verifiable
            }

    def _build_extraction_prompt(self, post_text: str) -> str:
        """
        Build the prompt for query extraction.

        Args:
            post_text: Original Facebook post

        Returns:
            Structured prompt for the LLM
        """
        prompt = f"""You are a query extraction assistant for a Vietnamese news verification system.

Your task: Analyze a Facebook post and extract structured queries for fact-checking.

**OUTPUT FORMAT:**
Return JSON with these fields:
1. "clean_query" (string): The main claim with noise removed
2. "claims" (array of strings): Distinct factual sub-claims (max {self.max_claims})
3. "factual_confidence" (float 0.0-1.0): Confidence this post contains verifiable facts

**RULES FOR clean_query:**
- Keep: Named entities, numbers, dates, locations, relationships, source attribution
- Remove: Emojis, excessive punctuation (keep periods), calls-to-action, subjective adjectives
- Reword: ONLY to remove noise or resolve pronouns when antecedent is clear
- Preserve: Causal relationships ("vì", "do"), temporal markers ("năm ngoái"), hearsay markers ("nghe nói")
- Output: Grammatically correct Vietnamese sentence

**RULES FOR claims:**
- Each claim must be:
  * A grammatically complete Vietnamese phrase
  * Factually distinct (different focus than other claims)
  * Verifiable against news articles
  * Minimally contextualized (resolve pronouns if clear, otherwise keep vague)
- Extract 1-{self.max_claims} claims maximum
- Order by importance (most newsworthy first)
- DO NOT add information not in original post
- DO NOT repeat information across claims (avoid redundancy)
- Each claim should be 1-2 sentences (15-20 words ideal, 30 words max)
- Each claim must include: subject + action + key detail (who/what/where/when/how much)

**RULES FOR factual_confidence:**
- High confidence (0.7-1.0): Named entities + specific events/numbers/dates
- Medium confidence (0.4-0.7): Vague claims, hearsay markers, opinions with embedded facts
- Low confidence (0.0-0.4): Pure opinion, only emojis, no verifiable facts, incoherent text

**VIETNAMESE LANGUAGE HANDLING:**
- Resolve "công ty đó", "ông ấy" if antecedent is in post
- Keep formal pronouns like "ông A", "bà B" as-is
- Preserve causal words: "vì", "do", "nên"
- Keep temporal phrases together: "năm ngoái", "tháng 6"
- Keep location phrases complete: "tại Hà Nội", "ở thành phố Hồ Chí Minh"

**EXAMPLES:**

Example 1 (high factual content):
Post: "VinTech xây nhà máy 5 tỷ USD ở Hà Nội!!! Tuyệt vời 🔥🔥🔥"
Output:
{{
  "clean_query": "VinTech xây nhà máy 5 tỷ USD ở Hà Nội",
  "claims": [
    "VinTech xây nhà máy ở Hà Nội",
    "Nhà máy trị giá 5 tỷ USD"
  ],
  "factual_confidence": 0.95
}}

Example 2 (medium factual content):
Post: "Nghe nói Bộ trưởng A từ chức vì bê bối. Chưa rõ sự thật."
Output:
{{
  "clean_query": "Nghe nói Bộ trưởng A từ chức vì bê bối",
  "claims": [
    "Bộ trưởng A từ chức",
    "Bê bối liên quan Bộ trưởng A"
  ],
  "factual_confidence": 0.6
}}

Example 3 (low factual content):
Post: "VinTech tuyệt vời quá!!! 🔥🔥🔥 Like và share nha!!!"
Output:
{{
  "clean_query": "VinTech",
  "claims": [],
  "factual_confidence": 0.2
}}

Example 4 (multi-sentence claim with context):
Post: "Bộ trưởng A tuyên bố VinTech sẽ xây nhà máy 5 tỷ USD tại Hà Nội vào tháng 6/2024"
Output:
{{
  "clean_query": "Bộ trưởng A tuyên bố VinTech xây nhà máy 5 tỷ USD tại Hà Nội tháng 6/2024",
  "claims": [
    "Bộ trưởng A tuyên bố về kế hoạch VinTech",
    "VinTech đầu tư 5 tỷ USD xây nhà máy",
    "Nhà máy tại Hà Nội khởi công tháng 6/2024"
  ],
  "factual_confidence": 0.9
}}

**NOW PROCESS THIS POST:**
\"\"\"
{post_text}
\"\"\"

Return ONLY valid JSON. No explanation."""
        return prompt
