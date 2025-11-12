"""
Query Extraction Service

Extracts clean queries and specific claims from noisy Facebook posts using LLM.
"""

import json
import re
from typing import Dict, List

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
        self.model = settings.ai.llm_model
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
            - claims: List of claim texts (simple strings)
            - entities: Dict of entities grouped by type (e.g., {"persons": ["A"], "organizations": ["X"]})
            - query_count: Total number of queries (1 clean_query + N claims)
            - factual_confidence: Confidence score (1-3)
            - rationale: LLM's reasoning (for debugging)

        Example:
            Input: "VinTech xây nhà máy 5 tỷ USD ở Hà Nội!!! Tuyệt vời 🎉🎉"
            Output: {
                "clean_query": "VinTech xây dựng nhà máy trị giá 5 tỷ USD tại Hà Nội",
                "claims": [
                    "VinTech xây dựng nhà máy tại Hà Nội",
                    "Nhà máy có giá trị 5 tỷ USD"
                ],
                "entities": {
                    "organizations": ["VinTech"],
                    "locations": ["Hà Nội"]
                },
                "query_count": 3,
                "factual_confidence": 3,
                "rationale": "..."
            }
        """
        prompt = self._build_extraction_prompt(post_text)

        try:
            # Call LLM - allow free text for CoT reasoning before JSON
            messages = [LLMMessage(role="user", content=prompt)]
            response = await self.llm.generate_completion(
                messages=messages,
                model=self.model,
                temperature=self.temperature,
            )

            # Parse RATIONALE and JSON from two-step output
            rationale_text = ""
            json_string = ""

            print("--------------------------------")
            print(response.content)
            print("--------------------------------")

            # Split by **JSON:** delimiter
            if "**JSON:**" in response.content:
                split_response = response.content.split("**JSON:**", 1)
                rationale_text = split_response[0].replace("**RATIONALE:**", "").strip()
                json_block = split_response[1].strip()

                # Remove markdown code fence if present (```json ... ```)
                json_block = re.sub(r"^```json\s*", "", json_block)
                json_block = re.sub(r"\s*```$", "", json_block)

                # Extract JSON object robustly (find first { and last })
                first_brace = json_block.find("{")
                last_brace = json_block.rfind("}")

                if first_brace == -1 or last_brace == -1:
                    logger.error("No JSON object found after **JSON:** marker")
                    logger.debug(f"JSON block: {json_block[:500]}...")
                    raise json.JSONDecodeError("No JSON object found", json_block, 0)

                json_string = json_block[first_brace : last_brace + 1]
            else:
                # Fallback: try to find any JSON block
                json_match = re.search(r"\{.*\}", response.content, re.DOTALL)
                if not json_match:
                    logger.error("No JSON block found in LLM response")
                    logger.debug(f"Full LLM response: {response.content[:500]}...")
                    raise json.JSONDecodeError(
                        "No JSON block found", response.content, 0
                    )
                json_string = json_match.group(0)
                rationale_text = response.content[
                    : response.content.find(json_string)
                ].strip()

            result = json.loads(json_string)

            # Validate and clean result
            clean_query = result.get("clean_query", "").strip()
            raw_claims = result.get("claims", [])
            raw_entities = result.get("entities", {}) or {}
            factual_confidence = result.get("factual_confidence", 3)

            # Extract claims (simple strings from LLM)
            claims: List[str] = []
            if isinstance(raw_claims, list):
                for item in raw_claims:
                    if isinstance(item, str):
                        text = item.strip()
                        if text:
                            claims.append(text)

            # Extract entities (already grouped by type from LLM)
            entities: Dict[str, List[str]] = {}
            if isinstance(raw_entities, dict):
                for entity_type, entity_list in raw_entities.items():
                    if isinstance(entity_list, list) and entity_list:
                        # Clean and deduplicate entities
                        clean_entities = []
                        for entity_text in entity_list:
                            if isinstance(entity_text, str) and entity_text.strip():
                                entity_clean = entity_text.strip()
                                if entity_clean not in clean_entities:
                                    clean_entities.append(entity_clean)

                        # Only add type if we have entities
                        if clean_entities:
                            entities[entity_type] = clean_entities

            # Validate confidence is in range [1, 2, 3]
            try:
                factual_confidence = int(factual_confidence)
                if factual_confidence not in [1, 2, 3]:
                    logger.warning(
                        f"Invalid factual_confidence value: {factual_confidence}, must be 1, 2, or 3. Defaulting to 3."
                    )
                    factual_confidence = 3
            except (ValueError, TypeError):
                logger.warning(
                    f"Invalid factual_confidence type: {type(factual_confidence)}, defaulting to 3."
                )
                factual_confidence = 3

            # Limit claims to max_claims
            if len(claims) > self.max_claims:
                claims = claims[: self.max_claims]
                logger.warning(
                    f"Truncated claims from {len(claims)} to {self.max_claims}"
                )

            query_count = 1 + len(claims)  # 1 clean_query + N claims

            entity_count = sum(len(v) for v in entities.values())
            logger.info(
                f"Extracted {query_count} queries: 1 clean_query + {len(claims)} claims "
                f"(factual_confidence: {factual_confidence}), {entity_count} entities"
            )
            logger.debug(
                f"LLM Rationale: {rationale_text[:200]}..."
            )  # Log first 200 chars

            return {
                "clean_query": clean_query,
                "claims": claims,
                "entities": entities,
                "query_count": query_count,
                "factual_confidence": factual_confidence,
                "rationale": rationale_text,
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            # Fallback: use original post as clean_query, assume verifiable (fail open)
            return {
                "clean_query": post_text.strip(),
                "claims": [],
                "entities": {},
                "query_count": 1,
                "factual_confidence": 3,  # Fail open: assume verifiable
            }
        except Exception as e:
            logger.error(f"Error during query extraction: {e}")
            # Fallback: use original post as clean_query, assume verifiable (fail open)
            return {
                "clean_query": post_text.strip(),
                "claims": [],
                "entities": {},
                "query_count": 1,
                "factual_confidence": 3,  # Fail open: assume verifiable
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

Your task is to analyze a Facebook post and extract structured queries for fact-checking.

You MUST follow this **TWO-STEP PROCESS**:

**STEP 1 - RATIONALE:**
First, provide a step-by-step rationale explaining:
- Why you chose the clean_query formulation
- How you segmented the post into claims (by topic)
- What entities you identified in each claim
- Why you assigned the specific factual_confidence score (reference the 1-3 rubric)

**STEP 2 - JSON:**
Second, output the final JSON object in the specified format.

**OUTPUT FORMAT (STRICT JSON):**
Return a JSON object with EXACTLY these keys:
1. "clean_query": string
2. "claims": array of strings (max {self.max_claims}) - simple claim text only
3. "entities": object with keys for each entity type found (only include types with entities):
   - "decision_ids": string[] (if any decision IDs found in the post)
   - "persons": string[] (if any person names found in the post)
   - "organizations": string[] (if any organization names found in the post)
   - "locations": string[] (if any locations found in the post)
   - "products_topics": string[] (if any products/brands/medical terms found in the post)

   **CRITICAL ENTITY EXTRACTION RULES:**
   - **Focus on DISCRIMINATIVE entities**: Only extract entities that help identify the MAIN TOPIC of the post
   - **Avoid GENERIC terms**: DO NOT extract common words like "nội dung", "thông tin", "vấn đề", "sự việc", "chuyện", "điều", "việc", "cái"
   - **Persons must be IDENTIFIABLE**: Only extract persons if they meet ONE of these criteria:
     * Full name, first name, or last name (e.g., "Nguyễn Văn A", "Phạm Cẩm Phương", "ông Dương")
     * Well-known position/title (e.g., "Thủ tướng", "Bộ trưởng Bộ Y tế", "Giám đốc Sở")
     * Name WITH title (e.g., "PGS.TS Phạm Cẩm Phương", "Bà Nguyễn Thị B")
     DO NOT extract:
     * General pronouns or vague references: "ông cháu", "bạn ấy", "anh ta", "chị ấy", "người này", "ai đó"
     * Generic roles without names: "bệnh nhân", "khách hàng", "người dùng", "sinh viên"
   - **Distinguish MAIN TOPICS from SUPPORTING DETAILS**:
     * For rental/sale posts: Extract property type + location (e.g., "phòng cho thuê", "Cầu Giấy"), NOT individual amenities (giường, tủ lạnh, máy giặt, etc.)
     * For news events: Extract key persons/organizations/locations, NOT evidence details (bộ xương, vết máu, áo blouse, etc.)
     * For announcements: Extract main organizations + key persons + core topics, NOT every action verb or noun mentioned
   - **Limit products_topics to 3-5 most relevant items**: Avoid listing every noun. Focus on what someone would SEARCH for.

   **Examples of GOOD vs BAD entity extraction:**

   **Generic terms:**
   ❌ BAD: "nội dung" (too generic, no discriminative value)
   ✅ GOOD: "Tuyển dụng", "Hướng nghiệp" (specific topics)

   **Supporting details vs main topics:**
   ❌ BAD: "giường, tủ lạnh, máy giặt, điều hòa" for rental post (just features, not searchable)
   ✅ GOOD: "phòng cho thuê" (what people search for)

   ❌ BAD: "bộ xương, áo blouse màu hồng" for missing persons case (evidence details)
   ✅ GOOD: "Ethan Morrison", "Alice Patterson", "sa mạc Chihuahua" (main entities)

   **Person entities (must be identifiable):**
   ❌ BAD: "ông cháu", "bạn ấy", "người này" (vague references, not identifiable)
   ❌ BAD: "bệnh nhân", "khách hàng" (generic roles, not identifiable)
   ✅ GOOD: "Nguyễn Đức Dương" (full name)
   ✅ GOOD: "PGS.TS Phạm Cẩm Phương" (name with title)
   ✅ GOOD: "Thủ tướng", "Bộ trưởng Bộ Y tế" (well-known positions)
   ✅ GOOD: "ông Dương" (last name with pronoun gives clue to identity)

   Entities MUST be exact surface forms present in the post text.
   Extract ALL entities from the ENTIRE post, not per-claim. Deduplicate if same entity appears multiple times.
   Only include entity type keys if you found entities of that type. Do NOT include empty arrays.
4. "factual_confidence": integer (1, 2, or 3 only)

**RULES FOR clean_query:**
- Purpose: Summarize and clean the post's full factual content, integrating all related facts into a natural sentence while preserving key entities
- Approach: Create a comprehensive, cleaned version of the ENTIRE post, removing noise and clarifying vague phrases
- ALWAYS KEEP (preserve exactly as-is):
  * ALL named entities (people, organizations, locations)
  * ALL decision/official identifiers (e.g., 628/QĐ-QLD, 15/2020/NĐ-CP)
  * ALL quotes from officials or sources
  * ALL medical/technical terms and specifications
  * ALL relationships, attributions, and source citations
  * Factual adjectives that describe properties (e.g., "đậm đặc", "không tế bào nhỏ")
- REMOVE AND CLARIFY:
  * Emojis and emoji sequences (🔥, ❤️, etc.)
  * Excessive punctuation (!!!, ..., ---) → replace with single punctuation
  * Pure marketing phrases with no factual content ("Tuyệt vời quá", "Like và share nha")
  * Call-to-action without information ("Đặt hàng ngay", if no context)
  * Vague emotive phrases → convert to factual statements where possible (e.g., "Có vẻ quy mô lớn lắm!" → "với quy mô lớn")
- ALLOWED REWORDING:
  * Fix obvious typos or grammar errors
  * Resolve pronouns ONLY if antecedent is 100% clear in the same post
  * Convert bullet points or lists into flowing sentences if needed
  * Summarize vague or repetitive phrasing into concise factual statements
- Length: Multiple sentences or paragraphs - preserve ALL factual sentences from original
- Output: Clean, grammatically correct Vietnamese text that reads naturally

**RULES FOR claims:**
- Purpose: Each claim is a search query to retrieve relevant news articles
- Extract 1-{self.max_claims} claims maximum
- Preserve ALL factual information from the post across all claims
- Claims are simple strings - just the claim text

**Segmentation Strategy - Split by TOPIC:**
- Each claim focuses on ONE main subject (one entity, one event, one official statement, one specification)
- Topic-based segmentation examples:
  * Administrative/regulatory decisions (approvals, laws, policies)
  * Product/entity specifications (technical details, properties, ingredients)
  * Events/announcements (what happened, when, where)
  * Medical/scientific info (indications, mechanisms, effects)
  * Official statements (quotes with attribution - one claim per official/source)
  * Economic info (prices, costs, discounts, offers)
  * Location/contact info (addresses, phone numbers, facilities)
- If facts are about the SAME topic/entity → combine into one claim
- If facts are about DIFFERENT topics/entities → create separate claims
- DO NOT split by arbitrary length - split by topic boundaries

**Self-Contained Principle:**
- Include ALL context needed to understand that specific topic
- Reader should understand without needing other claims or original post
- Preserve source attribution ("Theo X...", "Ông Y cho biết...", "Quyết định số...")
- Keep technical terms and specifications that help article matching
- Use natural, flowing language like news article excerpts

**Retrieval Optimization:**
- Rich context enables better semantic matching (vector search)
- Key details enable better keyword matching (BM25 search)
- Each claim should independently retrieve articles about its topic

**RULES FOR factual_confidence (1-3 scale ONLY):**
- **Score 1 (Opinion/Satire):** Pure opinion, satire, rhetorical questions, greetings, or incoherent text. Contains NO verifiable factual claims. Examples: "Tuyệt vời quá!", "Ai đồng ý với tôi?", "😂😂😂"
- **Score 2 (Vague/Mixed):** Mix of opinion and fact, OR vague/generalized claims, OR hearsay markers ("nghe nói", "có thể"). Contains some factual elements but not fully verifiable. Examples: "Công ty X làm ăn tốt", "Nghe nói giá sẽ tăng"
- **Score 3 (High-Verifiable):** Specific, objective, verifiable claims with named entities, dates, numbers, official identifiers, or attributions. Examples: Posts with decision IDs, person names, organization names, specific locations, dates, statistics, quotes from officials.

**VIETNAMESE LANGUAGE HANDLING:**
- Resolve "công ty đó", "ông ấy" if antecedent is in post
- Keep formal pronouns like "ông A", "bà B" as-is
- Preserve causal words: "vì", "do", "nên"
- Keep temporal phrases together: "năm ngoái", "tháng 6"
- Keep location phrases complete: "tại Hà Nội", "ở thành phố Hồ Chí Minh"

**EXAMPLE 1 (High-Verifiable - Score 3):**
**Post:** "Cấp đăng ký thuốc Pembroria. Quyết định 628/QĐ-QLD ngày 31/10 do Cục Quản lý Dược cấp. PGS.TS Phạm Cẩm Phương: 'Bệnh nhân có thêm lựa chọn.'"

**RATIONALE:**
This post contains high-value factual information. The clean_query preserves all entities, official identifiers (628/QĐ-QLD), and the attributed quote. I segment into two claims by topic: (1) the regulatory decision about Pembroria by Cục Quản lý Dược, and (2) the expert statement by PGS.TS Phạm Cẩm Phương.

For entity extraction, I focus on DISCRIMINATIVE entities that identify the main topic:
- Decision ID: "628/QĐ-QLD" (unique identifier)
- Organization: "Cục Quản lý Dược" (key organization)
- Person: "PGS.TS Phạm Cẩm Phương" (IDENTIFIABLE: name with title, not vague reference)
- Product: "Pembroria" (specific drug name, main topic)

I do NOT extract:
- "thuốc" (too generic)
- "bệnh nhân" (generic role without identity - not an identifiable person)

Both claims are specific, objective, and verifiable. Score: 3 (High-Verifiable).

**JSON:**
{{
  "clean_query": "Cấp đăng ký thuốc Pembroria. Quyết định 628/QĐ-QLD ngày 31/10 do Cục Quản lý Dược cấp. PGS.TS Phạm Cẩm Phương: 'Bệnh nhân có thêm lựa chọn.'",
  "claims": [
    "Theo Quyết định 628/QĐ-QLD, Cục Quản lý Dược cấp phép lưu hành Pembroria",
    "PGS.TS Phạm Cẩm Phương cho biết bệnh nhân có thêm lựa chọn điều trị"
  ],
  "entities": {{
    "decision_ids": ["628/QĐ-QLD"],
    "persons": ["PGS.TS Phạm Cẩm Phương"],
    "organizations": ["Cục Quản lý Dược"],
    "products_topics": ["Pembroria"]
  }},
  "factual_confidence": 3
}}

**EXAMPLE 2 (Vague/Mixed - Score 2):**
**Post:** "Nghe nói công ty VinTech sắp mở nhà máy mới ở đâu đó miền Bắc. Có vẻ quy mô lớn lắm! 🔥"

**RATIONALE:**
This post contains factual elements (company name "VinTech", general location "miền Bắc") but uses hearsay marker "nghe nói" and vague phrases ("đâu đó", "có vẻ", "lớn lắm"). The clean_query removes emoji and marketing tone. I create one claim covering the main topic (factory expansion). I extract entities: organization "VinTech" and location "miền Bắc". The claim is too vague to be fully verifiable. Score: 2 (Vague/Mixed).

**JSON:**
{{
  "clean_query": "Nghe nói công ty VinTech sắp mở nhà máy mới ở miền Bắc với quy mô lớn.",
  "claims": [
    "Công ty VinTech có kế hoạch mở nhà máy mới ở miền Bắc"
  ],
  "entities": {{
    "organizations": ["VinTech"],
    "locations": ["miền Bắc"]
  }},
  "factual_confidence": 2
}}

**EXAMPLE 3 (Opinion/Satire - Score 1):**
**Post:** "Chính phủ nên làm gì đó với vấn đề này! Ai đồng ý thì like nhé 👍👍👍"

**RATIONALE:**
This post is purely rhetorical and opinion-based. It contains no specific claims, no named entities, no verifiable facts. The clean_query removes emojis and call-to-action, but the content remains a vague opinion. No specific claims can be extracted, and no entities can be identified. Score: 1 (Opinion/Satire).

**JSON:**
{{
  "clean_query": "Chính phủ nên làm gì đó với vấn đề này.",
  "claims": [],
  "entities": {{}},
  "factual_confidence": 1
}}

**EXAMPLE 4 (Rental Post - Correct Entity Extraction):**
**Post:** "Ngõ 79 Cầu Giấy gần các trường ĐH. Phòng khép kín cho thuê. Nội thất: giường, tủ quần áo, bàn bếp, tủ bếp, tủ lạnh, điều hòa, nóng lạnh, máy giặt, máy sấy chung. Phí: 4K/số điện, 100k/người nước, 200k/người dịch vụ (wifi, vệ sinh, máy giặt, máy sấy), xe free. Liên hệ: 0988.085.497."

**RATIONALE:**
This is a rental advertisement. The clean_query summarizes all key information. I create one main claim about the rental property.

For entity extraction, I focus on what people would SEARCH for (the MAIN TOPIC):
- Location: "Ngõ 79 Cầu Giấy" (specific location people search for)
- Product: "phòng cho thuê" (what people search for)

I do NOT extract individual amenities (giường, tủ lạnh, máy giặt, điều hòa, etc.) because:
- These are SUPPORTING DETAILS, not the main topic
- Nobody searches for "tủ lạnh" to find rental housing
- They clutter the entity list with non-discriminative terms
- The main topic is "rental housing in Cầu Giấy", not "refrigerators"

Score: 3 (High-Verifiable) - contains specific location, contact info, and concrete pricing.

**JSON:**
{{
  "clean_query": "Ngõ 79 Cầu Giấy gần các trường Đại Học có phòng khép kín cho thuê với đầy đủ nội thất. Phí dịch vụ: 4K/số điện, 100k/người nước, 200k/người dịch vụ (wifi, vệ sinh, máy giặt, máy sấy), xe miễn phí. Liên hệ: 0988.085.497.",
  "claims": [
    "Phòng khép kín cho thuê tại Ngõ 79 Cầu Giấy gần các trường Đại Học với đầy đủ nội thất"
  ],
  "entities": {{
    "locations": ["Ngõ 79 Cầu Giấy"],
    "products_topics": ["phòng cho thuê"]
  }},
  "factual_confidence": 3
}}

**EXAMPLE 5 (Person Entity Extraction):**
**Post:** "Ông cháu 2k7 vừa tròn 18 tuổi có tuổi nghề 6 năm. Thu nhập mỗi tháng của anh ấy cao hơn cả văn phòng. Bộ trưởng Bộ Lao động cho biết sẽ hỗ trợ công nhân lành nghề."

**RATIONALE:**
This post mentions several person references. I must carefully evaluate which are IDENTIFIABLE persons:

Person references in the post:
- "Ông cháu 2k7": Casual/colloquial reference, NOT identifiable → DO NOT EXTRACT
- "anh ấy": Pronoun reference, NOT identifiable → DO NOT EXTRACT
- "Bộ trưởng Bộ Lao động": Well-known government position, IDENTIFIABLE → EXTRACT
- "công nhân lành nghề": Generic role without name, NOT identifiable → DO NOT EXTRACT

Only "Bộ trưởng Bộ Lao động" is extracted because it's a well-known position that identifies a specific person by their official role.

**JSON:**
{{
  "clean_query": "Người trẻ sinh năm 2007 vừa tròn 18 tuổi có 6 năm kinh nghiệm làm xây dựng với thu nhập cao. Bộ trưởng Bộ Lao động cho biết sẽ hỗ trợ công nhân lành nghề.",
  "claims": [
    "Người trẻ sinh năm 2007 làm nghề xây dựng từ 12 tuổi với thu nhập cao",
    "Bộ trưởng Bộ Lao động cho biết sẽ hỗ trợ công nhân lành nghề"
  ],
  "entities": {{
    "persons": ["Bộ trưởng Bộ Lao động"]
  }},
  "factual_confidence": 2
}}

**NOW PROCESS THIS POST:**
\"\"\"
{post_text}
\"\"\"

Remember: Provide RATIONALE first, then JSON."""
        return prompt
