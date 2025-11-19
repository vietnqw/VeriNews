/**
 * Displays a modal popup with the extracted content.
 * @param {string} content - The text content to display.
 * @param {object | null} apiResponse - The response from the API, or null for loading state.
 */
function showContentPopup(content, apiResponse) {
  // --- Create Popup Elements ---
  const overlay = document.createElement("div");
  overlay.className = "vn-modal-overlay";

  const modal = document.createElement("div");
  modal.className = "vn-modal-content";

  const closeButton = document.createElement("button");
    closeButton.className = "vn-modal-close";
    modal.appendChild(closeButton);

    // Helper for JS-based Tooltip (Fixed positioning to escape overflow)
    let activeTooltip = null;

    function showTooltip(target, text) {
      if (activeTooltip) activeTooltip.remove();

      const tooltip = document.createElement("div");
      tooltip.className = "vn-floating-tooltip";
      tooltip.innerText = text;
      document.body.appendChild(tooltip);
      activeTooltip = tooltip;

      const rect = target.getBoundingClientRect();
      const tooltipRect = tooltip.getBoundingClientRect();

      // Calculate position (centered above the element)
      let top = rect.top - tooltipRect.height - 10; // 10px gap
      let left = rect.left + (rect.width / 2) - (tooltipRect.width / 2);

      // Prevent going off-screen (left/right)
      if (left < 10) left = 10;
      if (left + tooltipRect.width > window.innerWidth - 10) {
        left = window.innerWidth - tooltipRect.width - 10;
      }

      // Prevent going off-screen (top) -> flip to bottom if needed
      if (top < 10) {
         top = rect.bottom + 10;
         tooltip.classList.add("bottom");
      }

      tooltip.style.top = `${top}px`;
      tooltip.style.left = `${left}px`;

      // Trigger animation
      requestAnimationFrame(() => {
        tooltip.classList.add("visible");
      });
    }

    function hideTooltip() {
      if (activeTooltip) {
        activeTooltip.classList.remove("visible");
        const tooltipToRemove = activeTooltip;
        activeTooltip = null;
        setTimeout(() => {
          if (tooltipToRemove.parentNode) tooltipToRemove.remove();
        }, 200); // Wait for fade out
      }
    }

    // Helper function to create consistent collapsible sections
  function createCollapsibleSection(title, contentElement, isCollapsed = true) {
    const section = document.createElement("div");
    section.className = "vn-collapsible-section";

    const toggle = document.createElement("button");
    toggle.className = "vn-collapsible-toggle";
    toggle.innerText = title;
    if (!isCollapsed) toggle.classList.add("expanded");

    const contentWrapper = document.createElement("div");
    contentWrapper.className = "vn-collapsible-content";
    if (isCollapsed) contentWrapper.classList.add("collapsed");

    contentWrapper.appendChild(contentElement);

    toggle.addEventListener("click", () => {
      contentWrapper.classList.toggle("collapsed");
      toggle.classList.toggle("expanded");
    });

    section.appendChild(toggle);
    section.appendChild(contentWrapper);
    return section;
  }

  if (!apiResponse) {
    // Loading state
    const loadingContainer = document.createElement("div");
    loadingContainer.className = "vn-loading-container";

    const spinnerWrapper = document.createElement("div");
    spinnerWrapper.className = "vn-loading-spinner-wrapper";

    const spinnerTrack = document.createElement("div");
    spinnerTrack.className = "vn-loading-spinner-track";

    const spinnerIndicator = document.createElement("div");
    spinnerIndicator.className = "vn-loading-spinner-indicator";

    spinnerWrapper.appendChild(spinnerTrack);
    spinnerWrapper.appendChild(spinnerIndicator);

    const loadingTitle = document.createElement("h1");
    loadingTitle.className = "vn-loading-title";
    loadingTitle.innerText = "Đang xác minh nội dung...";

    const loadingDescription = document.createElement("p");
    loadingDescription.className = "vn-loading-description";
    loadingDescription.innerText = "Vui lòng chờ trong giây lát. Quá trình này có thể mất một chút thời gian.";

    loadingContainer.appendChild(spinnerWrapper);
    loadingContainer.appendChild(loadingTitle);
    loadingContainer.appendChild(loadingDescription);
    modal.appendChild(loadingContainer);
  } else if (apiResponse.error) {
    // --- Error State ---
    const errorContainer = document.createElement("div");
    errorContainer.className = "vn-error-container";

    const errorTitle = document.createElement("h3");
    errorTitle.className = "vn-error-title";
    errorTitle.innerText = "Xác minh thất bại";

    const errorMessage = document.createElement("p");
    errorMessage.className = "vn-error-message";
    errorMessage.innerText = apiResponse.message;

    errorContainer.appendChild(errorTitle);
    errorContainer.appendChild(errorMessage);
    modal.appendChild(errorContainer);
  } else {
    // --- Overall Decision & Score Section (Header) ---
    const decisionContainer = document.createElement("div");
    decisionContainer.className = "vn-decision-container";

    // Circular Score Display
    const scoreCircle = document.createElement("div");
    scoreCircle.className = `vn-score-circle ${apiResponse.flag}`;

    const scorePercent = Math.round(apiResponse.final_score * 100);

    const scoreValue = document.createElement("span");
    scoreValue.className = `vn-score-value ${apiResponse.flag}`;
    scoreValue.innerText = `${scorePercent}%`;

    const scoreLabel = document.createElement("span");
    scoreLabel.className = "vn-score-label";
    scoreLabel.innerText = "Độ tin cậy";

    scoreCircle.appendChild(scoreValue);
    scoreCircle.appendChild(scoreLabel);

    // Decision Info
    const decisionInfo = document.createElement("div");
    decisionInfo.className = "vn-decision-info";

    const decisionBadge = document.createElement("div");
    decisionBadge.className = `vn-decision-badge ${apiResponse.flag}`;

    const decisionIcon = document.createElement("span");
    decisionIcon.className = "vn-decision-icon";
    const iconMap = { "green": "✓", "red": "✗", "yellow": "⚠", "gray": "?" };
    decisionIcon.innerText = iconMap[apiResponse.flag] || "?";

    const decisionText = document.createElement("span");
    decisionText.className = "vn-decision-text";
    const decisionMap = {
      "Fully Supported": "Hoàn toàn chính xác",
      "Partially Supported": "Đúng một phần",
      "Refuted": "Sai lệch/Giả mạo",
      "Not Enough Info": "Chưa đủ thông tin",
      "Verified": "Đã xác minh",
      "Misleading/False": "Sai lệch/Giả mạo",
      "Out of Context": "Sai ngữ cảnh",
      "Unverified": "Chưa xác minh"
    };
    decisionText.innerText = decisionMap[apiResponse.overall_decision] || "Không rõ";

    decisionBadge.appendChild(decisionIcon);
    decisionBadge.appendChild(decisionText);
    decisionInfo.appendChild(decisionBadge);

    if (apiResponse.explanation && apiResponse.explanation.trim() !== "") {
      const explanationText = document.createElement("p");
      explanationText.className = "vn-explanation-inline";
      explanationText.innerText = apiResponse.explanation;
      decisionInfo.appendChild(explanationText);
    }

    decisionContainer.appendChild(scoreCircle);
    decisionContainer.appendChild(decisionInfo);
    modal.appendChild(decisionContainer);

    // --- 1. Nội dung bài viết (Article Content) ---
    const contentDiv = document.createElement("div");
    contentDiv.className = "vn-article-content-text";
    const contentP = document.createElement("p");
    contentP.innerText = content;
    contentDiv.appendChild(contentP);

    modal.appendChild(createCollapsibleSection("Nội dung bài đăng", contentDiv, true));

    // --- 2. Bài báo liên quan (Related Articles) ---
    const articlesContainer = document.createElement("div");
    articlesContainer.className = "vn-articles-section";
    const hasArticles = apiResponse.matched_articles && apiResponse.matched_articles.length > 0;

    if (hasArticles) {
      const articlesList = document.createElement("ul");
      articlesList.className = "vn-articles-list";
      apiResponse.matched_articles.forEach((article) => {
        const listItem = document.createElement("li");

        const content = document.createElement("div");
        content.className = "vn-article-content";

        const link = document.createElement("a");
        link.href = article.url;
        link.target = "_blank";
        link.className = "vn-article-link";
        link.innerText = article.title;

        const meta = document.createElement("div");
        meta.className = "vn-article-meta";

        const sourceSpan = document.createElement("span");
        sourceSpan.className = "vn-article-source";
        sourceSpan.innerText = article.source;

        const separator = document.createElement("span");
        separator.innerText = " - ";

        const accuracySpan = document.createElement("span");
        const accuracy = Math.round(article.similarity * 100);
        let accuracyColor = "gray";
        if (accuracy >= 80) accuracyColor = "green";
        else if (accuracy >= 50) accuracyColor = "yellow";
        else if (accuracy > 0) accuracyColor = "red";
        accuracySpan.className = `vn-article-accuracy ${accuracyColor}`;
        accuracySpan.innerText = `Mức độ liên quan ${accuracy}%`;

        meta.appendChild(sourceSpan);
        meta.appendChild(separator);
        meta.appendChild(accuracySpan);

        content.appendChild(link);
        content.appendChild(meta);

        const arrow = document.createElement("span");
        arrow.className = "vn-article-arrow";
        arrow.innerText = "›";

        listItem.appendChild(content);
        listItem.appendChild(arrow);
        articlesList.appendChild(listItem);
      });
      articlesContainer.appendChild(articlesList);
    } else {
      const emptyMessage = document.createElement("p");
      emptyMessage.className = "vn-empty-message";
      emptyMessage.innerText = "Không tìm thấy bài báo liên quan.";
      articlesContainer.appendChild(emptyMessage);
    }

    modal.appendChild(createCollapsibleSection("Bài báo liên quan", articlesContainer, false)); // Default open? User didn't specify, but usually good to show

    // --- 3. Điểm chi tiết (Detailed Score) ---
    if (apiResponse.per_criterion_scores) {
      const scores = apiResponse.per_criterion_scores;
      const hasScores = scores.evidence_quality > 0 || scores.source_agreement > 0 ||
                       scores.claim_coverage > 0 || scores.stance_confidence > 0 ||
                       scores.temporal_relevance > 0;

      if (hasScores) {
        const criterionDetails = document.createElement("div");
        // criterionDetails.className = "vn-criterion-details"; // No longer needed, handled by generic

        const scoreItems = [
          { label: "Chất lượng bằng chứng", value: scores.evidence_quality, description: "Đo lường mức độ liên quan và độ mạnh của các bằng chứng tìm được. Điểm cao nghĩa là có trích dẫn trực tiếp hoặc dữ liệu cụ thể xác nhận nội dung." },
          { label: "Độ đồng thuận nguồn", value: scores.source_agreement, description: "Phản ánh mức độ thống nhất giữa các nguồn tin. Khi nhiều tờ báo uy tín cùng đưa tin giống nhau, độ tin cậy sẽ cao hơn." },
          { label: "Độ phủ tuyên bố", value: scores.claim_coverage, description: "Cho biết bao nhiêu phần trăm các ý chính trong bài viết đã được hệ thống tìm thấy và kiểm chứng đối chiếu với nguồn tin uy tín." },
          { label: "Độ tin cậy phân loại", value: scores.stance_confidence, description: "Thể hiện độ chắc chắn của hệ thống AI khi xác định xem thông tin là đúng hay sai dựa trên ngữ cảnh và bằng chứng." },
          { label: "Độ mới của bài báo", value: scores.temporal_relevance, description: "Đánh giá tính thời sự của nguồn tin. Các bài báo mới nhất thường phản ánh thông tin chính xác hơn cho các sự kiện đang diễn ra." }
        ];

        scoreItems.forEach(item => {
          const scoreRow = document.createElement("div");
          scoreRow.className = "vn-score-row";

          const scoreRowLabel = document.createElement("span");
          scoreRowLabel.className = "vn-score-row-label";
          scoreRowLabel.innerText = item.label;

          // JS Tooltip Events
          scoreRowLabel.addEventListener("mouseenter", () => showTooltip(scoreRowLabel, item.description));
          scoreRowLabel.addEventListener("mouseleave", hideTooltip);
          // Also handle click for touch devices or persistency
          scoreRowLabel.addEventListener("click", (e) => {
             e.stopPropagation(); // Prevent collapsing the section
             showTooltip(scoreRowLabel, item.description);
          });

          const scoreRowValue = document.createElement("span");
          scoreRowValue.className = "vn-score-row-value";
          scoreRowValue.innerText = `${Math.round(item.value * 100)}%`;

          scoreRow.appendChild(scoreRowLabel);
          scoreRow.appendChild(scoreRowValue);
          criterionDetails.appendChild(scoreRow);
        });

        modal.appendChild(createCollapsibleSection("Điểm chi tiết", criterionDetails, true));
      }
    }

    // --- 4. Điểm từng tuyên bố (Claim Verdicts) ---
    if (apiResponse.claim_verdicts && apiResponse.claim_verdicts.length > 0) {
      const claimVerdictsList = document.createElement("div");
      claimVerdictsList.className = "vn-claim-verdicts-list";

      const verdictInfo = {
        "SUPPORTED": { text: "Được hỗ trợ", color: "green", icon: "✓" },
        "REFUTED": { text: "Bị bác bỏ", color: "red", icon: "✗" },
        "NOT_ENOUGH_INFO": { text: "Chưa đủ thông tin", color: "gray", icon: "?" }
      };

      apiResponse.claim_verdicts.forEach((cv, index) => {
        const claimItem = document.createElement("div");
        claimItem.className = "vn-claim-verdict-item";

        const claimHeader = document.createElement("div");
        claimHeader.className = "vn-claim-header";

        const claimNumber = document.createElement("span");
        claimNumber.className = "vn-claim-number";
        claimNumber.innerText = `Nội dung thứ ${index + 1}:`;

        const claimVerdictBadge = document.createElement("span");
        const info = verdictInfo[cv.verdict] || { text: cv.verdict, color: "gray", icon: "?" };
        claimVerdictBadge.className = `vn-claim-verdict-badge ${info.color}`;
        claimVerdictBadge.innerHTML = `${info.icon} ${info.text} (${Math.round(cv.confidence * 100)}%)`;

        claimHeader.appendChild(claimNumber);
        claimHeader.appendChild(claimVerdictBadge);

        const claimText = document.createElement("p");
        claimText.className = "vn-claim-text";
        claimText.innerText = cv.claim_text;

        claimItem.appendChild(claimHeader);
        claimItem.appendChild(claimText);

        // Evidence
        if (cv.supporting_evidence && cv.supporting_evidence.length > 0) {
          const supportingContainer = document.createElement("div");
          supportingContainer.className = "vn-evidence-container supporting";
          const supportingTitle = document.createElement("h5");
          supportingTitle.className = "vn-evidence-title";
          supportingTitle.innerText = "📗 Bằng chứng hỗ trợ:";
          supportingContainer.appendChild(supportingTitle);
          cv.supporting_evidence.forEach(evidence => {
            const evidenceItem = document.createElement("div");
            evidenceItem.className = "vn-evidence-item";

            const evidenceQuote = document.createElement("p");
            evidenceQuote.className = "vn-evidence-quote";
            evidenceQuote.innerText = `"${evidence.key_quote}"`;

            const evidenceSource = document.createElement("span");
            evidenceSource.className = "vn-evidence-source";
            evidenceSource.innerText = `— ${evidence.source_name}`;

            evidenceItem.appendChild(evidenceQuote);
            evidenceItem.appendChild(evidenceSource);
            supportingContainer.appendChild(evidenceItem);
          });
          claimItem.appendChild(supportingContainer);
        }

        if (cv.refuting_evidence && cv.refuting_evidence.length > 0) {
          const refutingContainer = document.createElement("div");
          refutingContainer.className = "vn-evidence-container refuting";
          const refutingTitle = document.createElement("h5");
          refutingTitle.className = "vn-evidence-title";
          refutingTitle.innerText = "📕 Bằng chứng bác bỏ:";
          refutingContainer.appendChild(refutingTitle);
          cv.refuting_evidence.forEach(evidence => {
            const evidenceItem = document.createElement("div");
            evidenceItem.className = "vn-evidence-item";

            const evidenceQuote = document.createElement("p");
            evidenceQuote.className = "vn-evidence-quote";
            evidenceQuote.innerText = `"${evidence.key_quote}"`;

            const evidenceSource = document.createElement("span");
            evidenceSource.className = "vn-evidence-source";
            evidenceSource.innerText = `— ${evidence.source_name}`;

            evidenceItem.appendChild(evidenceQuote);
            evidenceItem.appendChild(evidenceSource);
            refutingContainer.appendChild(evidenceItem);
          });
          claimItem.appendChild(refutingContainer);
        }

        claimVerdictsList.appendChild(claimItem);
      });

      modal.appendChild(createCollapsibleSection("Phân tích chi tiết", claimVerdictsList, true));
    }

    // Contextual Judgment
    if (apiResponse.contextual_judgment && apiResponse.contextual_judgment.is_out_of_context) {
      const contextContainer = document.createElement("div");
      contextContainer.className = "vn-context-warning";
      const contextTitle = document.createElement("h4");
      contextTitle.className = "vn-context-title";
      contextTitle.innerText = "⚠ Cảnh báo ngữ cảnh";
      const contextReasoning = document.createElement("p");
      contextReasoning.className = "vn-context-reasoning";
      contextReasoning.innerText = apiResponse.contextual_judgment.reasoning;
      contextContainer.appendChild(contextTitle);
      contextContainer.appendChild(contextReasoning);
      modal.appendChild(contextContainer);
    }
  }

  // --- Footer ---
  if (apiResponse && !apiResponse.error && apiResponse._veriNewsMetadata) {
    const footer = document.createElement("div");
    footer.className = "vn-modal-footer";

    const footerInfo = document.createElement("div");
    footerInfo.className = "vn-footer-info";
    const timeSec = (apiResponse._veriNewsMetadata.total_time_ms / 1000).toFixed(2);
    footerInfo.innerHTML = `<strong>Thời gian:</strong> ${timeSec} giây`;
    footer.appendChild(footerInfo);

    const refreshButton = document.createElement("button");
    refreshButton.className = "vn-refresh-button";
    refreshButton.innerHTML = `<span class="vn-refresh-icon">↻</span> Xác minh lại`;

    refreshButton.addEventListener("click", async () => {
      refreshButton.disabled = true;
      refreshButton.innerText = "Đang xác minh...";
      try {
        const newApiResponse = await callVerifyAPI(content, true);
        document.querySelector(".vn-modal-overlay")?.remove();
        showContentPopup(content, newApiResponse);
      } catch (error) {
        console.error(error);
        refreshButton.disabled = false;
        refreshButton.innerText = "Thất bại - Thử lại";
      }
    });

    footer.appendChild(refreshButton);
    modal.appendChild(footer);
  }

  overlay.appendChild(modal);
  document.body.appendChild(overlay);

  const closeModal = () => document.body.removeChild(overlay);
  closeButton.addEventListener("click", closeModal);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) closeModal(); });
}

/**
 * Creates and attaches an overlay and extract button to a target element.
 * @param {HTMLElement} target - The element to overlay.
 * @param {string} type - The type of content ('post', 'comment', 'complementary').
 */
async function createOverlay(target, type) {
  target.setAttribute(PROCESSED_ATTR, "true");
  let preliminaryText;
  if (type === "post") preliminaryText = getTextFromPost(target);
  else if (type === "comment") preliminaryText = getTextFromComment(target);
  else if (type === "complementary") preliminaryText = getTextFromComplementary(target);

  if (!preliminaryText || preliminaryText.trim() === "" || preliminaryText.startsWith("No text found")) return;

  const button = document.createElement("button");
  button.className = "vn-extract-button";
  const buttonImg = document.createElement("img");
  buttonImg.src = chrome.runtime.getURL("src/assets/images/verify_button.png");
  buttonImg.alt = "Xác minh";
  buttonImg.className = `vn-verify-image ${type}`;
  button.appendChild(buttonImg);

  button.addEventListener("click", async (event) => {
    event.preventDefault();
    event.stopPropagation();
    buttonImg.alt = "Đang trích xuất...";
    button.disabled = true;
    showContentPopup("Đang trích xuất nội dung...", null);
    const extracted = await extractText(target, type);
    const apiResponse = await callVerifyAPI(extracted);
    document.querySelector(".vn-modal-overlay")?.remove();
    showContentPopup(extracted, apiResponse);
    buttonImg.alt = "Xác minh";
    button.disabled = false;
  });

  const overlay = document.createElement("div");
  overlay.className = `vn-overlay ${type}`;
  overlay.appendChild(button);
  target.appendChild(overlay);
}
