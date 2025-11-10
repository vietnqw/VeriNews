/**
 * Normalizes a relevance score to 0-1 range
 * VeriNews returns summed chunk scores (e.g., 2.45)
 * We normalize to approximate similarity
 */
function normalizeScore(score) {
  // Simple normalization: assume scores typically range 0-5
  // Cap at 1.0 for very high scores
  return Math.min(score / 5.0, 1.0);
}

/**
 * Adapts VeriNews API response to MVP extension format
 * Handles missing fields and transforms data structure
 */
function adaptVeriNewsResponse(veriNewsData) {
  // Map articles to MVP format
  const matched_articles = (veriNewsData.articles || []).map(article => ({
    // Use article_id as fallback URL until backend adds url field
    url: article.url || `#article-${article.article_id}`,
    title: article.title || "Untitled Article",
    source: article.source_name || "Unknown Source",
    // Normalize relevance_score to 0-1 range
    similarity: normalizeScore(article.relevance_score || 0)
  }));

  // Extract claims if available (currently not returned by VeriNews API)
  const claims = veriNewsData.claims || [];

  // Determine verdict based on available data
  // Since verification is not implemented, default to "Unverified"
  let overall_decision = "Unverified";
  let flag = "gray";
  let final_score = 0.0;

  // If verification is implemented in the future, use it
  if (veriNewsData.verification && veriNewsData.verification.verdict !== "NOT_IMPLEMENTED") {
    const verdict = veriNewsData.verification.verdict;
    const confidence = veriNewsData.verification.confidence || 0;

    // Map verdict to decision and flag
    if (verdict === "VERIFIED" || verdict === "TRUE") {
      overall_decision = "Verified";
      flag = "green";
      final_score = confidence;
    } else if (verdict === "FALSE" || verdict === "MISLEADING") {
      overall_decision = "Misleading/False";
      flag = "red";
      final_score = 1 - confidence;
    } else if (verdict === "OUT_OF_CONTEXT") {
      overall_decision = "Out of Context";
      flag = "yellow";
      final_score = confidence;
    }
  }

  // Build response in MVP format
  return {
    matched_articles,
    claims,
    overall_decision,
    flag,
    final_score,

    // Per-criterion scores not available in VeriNews yet
    per_criterion_scores: {
      content_similarity: 0.0,
      support_ratio: 0.0,
      contradiction_ratio: 0.0,
      not_mentioned_ratio: 0.0
    },

    // Contextual judgment not available
    contextual_judgment: null,

    error: false,
    message: veriNewsData.cache_hit
      ? "Retrieved from cache"
      : "Verification completed",

    // Pass through additional VeriNews metadata
    _veriNewsMetadata: {
      total_time_ms: veriNewsData.total_time_ms,
      stage_timings: veriNewsData.stage_timings,
      query_count: veriNewsData.query_count,
      cache_hit: veriNewsData.cache_hit
    }
  };
}

/**
 * Calls VeriNews verification API
 * @param {string} content - The text content to verify
 * @returns {Promise<Object>} Verification result in MVP format
 */
async function callVerifyAPI(content) {
  try {
    const response = await fetch(`${CONFIG.BACKEND_BASE_URL}/api/v1/verify`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        text: content  // VeriNews uses 'text' not 'content'
      }),
    });

    if (!response.ok) {
      // Try to get more info from the response body
      let errorDetails = "Could not retrieve error details.";
      try {
        const errorData = await response.json();
        if (errorData.detail) {
          errorDetails = errorData.detail;
        }
      } catch (e) {
        // response body is not json or empty
      }
      return {
        error: true,
        message: `API request failed with status ${response.status}. ${errorDetails}`,
      };
    }

    // Get VeriNews response and adapt to MVP format
    const veriNewsData = await response.json();
    return adaptVeriNewsResponse(veriNewsData);

  } catch (error) {
    console.error("Error calling VeriNews API:", error);
    let message = "An unknown error occurred.";
    if (error instanceof TypeError && error.message.includes("Failed to fetch")) {
      message =
        "Could not connect to the VeriNews server. Please check your internet connection or try again later.";
    }
    return {
      error: true,
      message: message,
    };
  }
}
