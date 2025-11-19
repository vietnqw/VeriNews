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
    // Normalize relevance_score from 0-10 scale to 0-1 for UI display
    similarity: (article.relevance_score || 0) / 10
  }));

  // Extract claims if available
  const claims = veriNewsData.claims || [];

  // Determine verdict based on verification result
  let overall_decision = "Unverified";
  let flag = "gray";
  let final_score = 0.0;
  let claim_verdicts = [];
  let confidence_metrics = null;
  let explanation = "";
  let sources_used = [];

  // Check if verification result exists
  if (veriNewsData.verification) {
    const verification = veriNewsData.verification;
    const verdict = verification.verdict;
    final_score = verification.confidence || 0;

    // Map verdict to decision and flag
    if (verdict === "FULLY_SUPPORTED") {
      overall_decision = "Fully Supported";
      flag = "green";
    } else if (verdict === "PARTIALLY_SUPPORTED") {
      overall_decision = "Partially Supported";
      flag = "yellow";
    } else if (verdict === "REFUTED") {
      overall_decision = "Refuted";
      flag = "red";
    } else if (verdict === "NOT_ENOUGH_INFO") {
      overall_decision = "Not Enough Info";
      flag = "gray";
    }

    // Extract claim verdicts
    claim_verdicts = (verification.claim_verdicts || []).map(cv => ({
      claim_text: cv.claim_text,
      verdict: cv.verdict,
      confidence: cv.confidence,
      supporting_evidence: cv.supporting_evidence || [],
      refuting_evidence: cv.refuting_evidence || []
    }));

    // Extract confidence metrics
    if (verification.confidence_metrics) {
      const metrics = verification.confidence_metrics;
      confidence_metrics = {
        overall_confidence: metrics.overall_confidence,
        confidence_tier: metrics.confidence_tier,
        evidence_quality: metrics.evidence_quality,
        source_agreement: metrics.source_agreement,
        claim_coverage: metrics.claim_coverage,
        stance_confidence: metrics.stance_confidence,
        temporal_relevance: metrics.temporal_relevance
      };
    }

    // Extract explanation and sources
    explanation = verification.explanation || "";
    sources_used = verification.sources_used || [];
  }

  // Build response in MVP format
  return {
    matched_articles,
    claims,
    overall_decision,
    flag,
    final_score,

    // Claim-level verdicts with evidence
    claim_verdicts,

    // Confidence metrics breakdown
    confidence_metrics,

    // Vietnamese explanation
    explanation,

    // Sources used for verification
    sources_used,

    // Per-criterion scores mapped from confidence metrics
    per_criterion_scores: confidence_metrics ? {
      evidence_quality: confidence_metrics.evidence_quality || 0,
      source_agreement: confidence_metrics.source_agreement || 0,
      claim_coverage: confidence_metrics.claim_coverage || 0,
      stance_confidence: confidence_metrics.stance_confidence || 0,
      temporal_relevance: confidence_metrics.temporal_relevance || 0
    } : null,

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
      cache_hit: veriNewsData.cache_hit,
      factual_confidence: veriNewsData.factual_confidence,
      retrieval_confidence: veriNewsData.retrieval_confidence,
      early_exit: veriNewsData.early_exit,
      exit_reason: veriNewsData.exit_reason
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
