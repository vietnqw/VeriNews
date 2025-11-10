/**
 * Adapts VeriNews API response to MVP extension format
 * Handles missing fields and transforms data structure
 */
function adaptVeriNewsResponse(veriNewsData) {
  // Map articles to MVP format
  const matched_articles = (veriNewsData.articles || []).map(article => ({
    // Use article_id as fallback URL until backend adds url field
    url: article.url || `#article-${article.article_id}`,
    title: article.title || "Bài viết không có tiêu đề",
    source: article.source_name || "Nguồn không xác định",
    // Use the backend's normalized similarity_score directly
    similarity: article.similarity_score || 0
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
      ? "Đã truy xuất từ bộ nhớ đệm"
      : "Xác minh hoàn tất",

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
 * @param {boolean} cacheBypass - If true, bypass cache and force re-verification
 * @returns {Promise<Object>} Verification result in MVP format
 */
async function callVerifyAPI(content, cacheBypass = false) {
  try {
    const response = await fetch(`${CONFIG.BACKEND_BASE_URL}/api/v1/verify`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        text: content,  // VeriNews uses 'text' not 'content'
        cache_bypass: cacheBypass  // Add cache_bypass parameter
      }),
    });

    if (!response.ok) {
      // Try to get more info from the response body
      let errorDetails = "Không thể truy xuất chi tiết lỗi.";
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
        message: `Yêu cầu API thất bại với mã trạng thái ${response.status}. ${errorDetails}`,
      };
    }

    // Get VeriNews response and adapt to MVP format
    const veriNewsData = await response.json();
    return adaptVeriNewsResponse(veriNewsData);

  } catch (error) {
    console.error("Error calling VeriNews API:", error);
    let message = "Đã xảy ra lỗi không xác định.";
    if (error instanceof TypeError && error.message.includes("Failed to fetch")) {
      message =
        "Không thể kết nối đến máy chủ VeriNews. Vui lòng kiểm tra kết nối internet của bạn hoặc thử lại sau.";
    }
    return {
      error: true,
      message: message,
    };
  }
}
