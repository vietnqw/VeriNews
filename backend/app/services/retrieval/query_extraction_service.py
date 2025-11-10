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
                f"Extracted {query_count} queries: 1 clean_query + {len(claims)} claims"
            )

            return {
                "clean_query": clean_query,
                "claims": claims,
                "query_count": query_count,
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            # Fallback: use original post as clean_query
            return {
                "clean_query": post_text.strip(),
                "claims": [],
                "query_count": 1,
            }
        except Exception as e:
            logger.error(f"Error during query extraction: {e}")
            # Fallback: use original post as clean_query
            return {
                "clean_query": post_text.strip(),
                "claims": [],
                "query_count": 1,
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

Your task is to analyze a Facebook post and extract:
1. A "clean_query": The main topic/claim with noise removed (keep essential information, minimal rewording)
2. A list of "claims": Specific, factual, verifiable statements

Guidelines:
- Remove emojis, excessive punctuation, and emotional language
- Keep factual information (names, numbers, dates, locations)
- Do NOT add information not present in the original post
- For claims: Extract distinct factual statements that can be verified against news articles
- Return valid JSON with keys: "clean_query" (string) and "claims" (array of strings)
- Maximum {self.max_claims} claims

Facebook post:
\"\"\"
{post_text}
\"\"\"

Return your response as JSON in this format:
{{
  "clean_query": "cleaned version of the post",
  "claims": ["claim 1", "claim 2", ...]
}}
"""
        return prompt
