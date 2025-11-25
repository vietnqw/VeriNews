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
  let reason = null;

  // Check if verification result exists
  if (veriNewsData.verification) {
    const verification = veriNewsData.verification;
    const verdict = verification.verdict;
    // Confidence can be null for NOT_ENOUGH_INFO verdicts
    final_score = verification.confidence !== null && verification.confidence !== undefined
      ? verification.confidence
      : 0;

    // Extract reason for NOT_ENOUGH_INFO verdicts
    reason = verification.reason || null;

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

    // Extract confidence metrics (null for NOT_ENOUGH_INFO)
    if (verification.confidence_metrics) {
      const metrics = verification.confidence_metrics;
      confidence_metrics = {
        overall_confidence: metrics.overall_confidence,
        evidence_quality: metrics.evidence_quality,
        source_agreement: metrics.source_agreement,
        source_quantity: metrics.source_quantity,
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

    // Reason for NOT_ENOUGH_INFO verdicts
    reason,

    // Per-criterion scores mapped from confidence metrics
    per_criterion_scores: confidence_metrics ? {
      evidence_quality: confidence_metrics.evidence_quality || 0,
      source_agreement: confidence_metrics.source_agreement || 0,
      source_quantity: confidence_metrics.source_quantity || 0,
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
 * Calls VeriNews verification API with progress tracking (SSE streaming)
 * @param {string} content - The text content to verify
 * @param {boolean} cacheBypass - If true, bypass cache and force re-verification
 * @param {Function} onStageUpdate - Callback for stage updates
 * @param {Function} onProgressUpdate - Callback for progress updates
 * @param {Function} onError - Callback for errors
 * @returns {Promise<Object>} Verification result in MVP format
 */
async function callVerifyAPIWithProgress(
  content,
  cacheBypass = false,
  onStageUpdate,
  onProgressUpdate,
  onError
) {
  try {
    const response = await fetch(`${CONFIG.BACKEND_BASE_URL}/api/v1/verify?stream=true`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        text: content,
        cache_bypass: cacheBypass,
      }),
    });

    if (!response.ok) {
      let errorDetails = "Không thể truy xuất chi tiết lỗi.";
      try {
        const errorData = await response.json();
        if (errorData.detail) {
          errorDetails = errorData.detail;
        }
      } catch (e) {
        // response body is not json or empty
      }
      onError?.({
        message: `Yêu cầu API thất bại với mã trạng thái ${response.status}. ${errorDetails}`,
      });
      return { error: true, message: "API request failed" };
    }

    // Handle SSE stream
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalResult = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Process complete SSE messages
      const lines = buffer.split("\n");
      buffer = lines.pop(); // Keep incomplete line in buffer

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const eventData = JSON.parse(line.slice(6));
            if (eventData.type === "stage_update") {
              onStageUpdate?.(eventData);
              onProgressUpdate?.(eventData);
            } else if (eventData.type === "result") {
              finalResult = adaptVeriNewsResponse(eventData.data);
            } else if (eventData.type === "error") {
              onError?.({ message: eventData.message });
            }
          } catch (e) {
            console.error("Failed to parse SSE event:", line, e);
          }
        }
      }
    }

    return finalResult || { error: true, message: "No response received" };
  } catch (error) {
    console.error("Error calling VeriNews API with progress:", error);
    let message = "Đã xảy ra lỗi không xác định.";
    if (error instanceof TypeError && error.message.includes("Failed to fetch")) {
      message =
        "Không thể kết nối đến máy chủ VeriNews. Vui lòng kiểm tra kết nối internet của bạn hoặc thử lại sau.";
    }
    onError?.({ message });
    return { error: true, message };
  }
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
